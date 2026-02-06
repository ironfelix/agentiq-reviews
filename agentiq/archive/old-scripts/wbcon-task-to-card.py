#!/usr/bin/env python3
import json
import re
import sys
from collections import Counter, defaultdict
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta

STOPWORDS = {"очень", "вообще", "просто", "пока", "тоже", "так", "как", "что", "это"}
POSITIVE_HINTS = ("хорош", "отлич", "нрав", "класс", "рекоменд", "супер")
NEGATIVE_HINTS = ("плох", "брак", "слом", "не ", "не-", "не_", "проблем", "недостат")
WINDOW_DAYS = 30


def load_payload(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and data:
        return data[0]
    return data


def parse_json_list(value: str):
    if not value or value == "[]":
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_issue(text: str):
    text = text.strip().lower()
    text = re.sub(r"[^a-zа-я0-9\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in STOPWORDS:
        return None
    if any(h in text for h in POSITIVE_HINTS):
        return None
    return text


def build_signal(issue_counts: Counter, recent_issue_counts: Counter, issue_dates: dict, total: int, recent_total: int, recent_low: int, variant_alert: Optional[Dict]):
    if recent_issue_counts:
        label, count = recent_issue_counts.most_common(1)[0]
        if count >= 2:
            return {
                "title": f"{label.capitalize()} — {count} раз за {WINDOW_DAYS} дней",
                "text": "Локальный паттерн в свежих отзывах — стоит проверить.",
                "source": f"{recent_total} отзывов за {WINDOW_DAYS} дней",
            }

    if variant_alert:
        name = variant_alert["name"]
        avg = variant_alert["avg"]
        overall = variant_alert["overall"]
        return {
            "title": f"Вариант «{name}» хуже среднего",
            "text": f"Средняя оценка {avg} против {overall} по товару.",
            "source": f"{variant_alert['count']} отзывов по варианту",
        }

    if recent_total:
        return {
            "title": "Сильного сигнала нет",
            "text": f"За {WINDOW_DAYS} дней {recent_low} отзывов с оценкой 3–4★ — держать под наблюдением.",
            "source": f"{recent_total} отзывов за {WINDOW_DAYS} дней",
        }

    return {
        "title": "Явных проблем не видно",
        "text": "Повторяющихся негативных причин не обнаружено.",
        "source": f"{total} отзывов",
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: wbcon-task-to-card.py <task-json> <output-json>")
        sys.exit(1)

    src_path = sys.argv[1]
    out_path = sys.argv[2]

    payload = load_payload(src_path)
    feedbacks = payload.get("feedbacks", []) if isinstance(payload, dict) else []

    # Stats
    counts = {
        5: payload.get("five_valuation_distr", 0),
        4: payload.get("four_valuation_distr", 0),
        3: payload.get("three_valuation_distr", 0),
        2: payload.get("two_valuation_distr", 0),
        1: payload.get("one_valuation_distr", 0),
    }
    total = len(feedbacks)
    total_reported = payload.get("feedback_count") or total
    rating = payload.get("rating") or 0
    if not rating:
        dist_total = sum(counts.values())
        denom = dist_total or total or 1
        rating = round(sum(k * v for k, v in counts.items()) / denom, 2)

    unanswered = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    recent_total = 0
    recent_low = 0

    issue_counts = Counter()
    recent_issue_counts = Counter()
    issue_dates = defaultdict(list)

    variant_stats = defaultdict(lambda: {"count": 0, "sum": 0.0, "issues": 0, "low": 0})

    for f in feedbacks:
        rating_val = float(f.get("valuation") or 0)
        variant = f.get("color") or f.get("size") or "Остальные"
        variant_stats[variant]["count"] += 1
        variant_stats[variant]["sum"] += rating_val
        if rating_val <= 3:
            variant_stats[variant]["low"] += 1

        has_answer = bool(f.get("answer_text"))
        if not has_answer:
            unanswered += 1

        # Date window
        dt = parse_date(f.get("fb_created_at") or "")
        if dt and dt >= cutoff:
            recent_total += 1
            if 3 <= rating_val <= 4:
                recent_low += 1

        # Disadvantages text
        disadv = f.get("disadvantages") or ""
        if disadv:
            label = normalize_issue(disadv)
            if label:
                issue_counts[label] += 1
                if dt:
                    issue_dates[label].append(dt)
                    if dt >= cutoff:
                        recent_issue_counts[label] += 1

        # Problems list — учитываем только в негативном контексте
        fb_text = (f.get("fb_text") or "").lower()
        is_negative_context = (
            rating_val <= 3
            or bool(disadv)
            or any(h in fb_text for h in NEGATIVE_HINTS)
        )
        if is_negative_context:
            problems = parse_json_list(f.get("problems") or "")
            for p in problems:
                label = normalize_issue(p)
                if not label:
                    continue
                issue_counts[label] += 1
                if dt:
                    issue_dates[label].append(dt)
                    if dt >= cutoff:
                        recent_issue_counts[label] += 1

    # Variant-based alert: worst variant significantly below overall
    variant_alert = None
    if variant_stats:
        worst = None
        for name, v in variant_stats.items():
            if v["count"] < 10:
                continue
            avg = round(v["sum"] / v["count"], 2) if v["count"] else 0
            if worst is None or avg < worst["avg"]:
                worst = {"name": name, "avg": avg, "count": v["count"]}
        if worst and rating and worst["avg"] <= rating - 0.4:
            variant_alert = {"name": worst["name"], "avg": worst["avg"], "overall": rating, "count": worst["count"]}

    signal = build_signal(issue_counts, recent_issue_counts, issue_dates, total, recent_total, recent_low, variant_alert)

    variants = []
    for name, v in variant_stats.items():
        if v["count"] == 0:
            continue
        avg = round(v["sum"] / v["count"], 2)
        low_share = v["low"] / v["count"] if v["count"] else 0
        status = "problem" if v["issues"] >= 2 or (low_share >= 0.2 and v["count"] >= 5) else "ok"
        variants.append({
            "name": name,
            "rating": avg,
            "count": v["count"],
            "status": status,
        })

    variants.sort(key=lambda x: (-x["count"], x["name"]))
    max_count = max((v["count"] for v in variants), default=1)
    for v in variants:
        v["bar"] = int(round(v["count"] / max_count * 100))
    variants = variants[:3]

    decision_text = "Проверить проблемные варианты и обновить описание."
    if variant_alert:
        decision_text = f"Проверить вариант «{variant_alert['name']}» — он заметно хуже среднего."
    if signal["title"].startswith("Сильного"):
        decision_text = f"Пока без срочных действий, но держать под наблюдением {WINDOW_DAYS} дней."
    if signal["title"].startswith("Явных"):
        decision_text = "Срочных действий нет. Можно улучшить описание/FAQ и ждать."

    article = None
    if feedbacks:
        article = feedbacks[0].get("article")

    result = {
        "product": {
            "title": f"Артикул {article or ''}".strip() or "Товар",
            "article": str(article or ""),
            "platform": "Wildberries",
        },
        "stats": {
            "feedback_count": total,
            "feedback_total": total_reported,
            "rating": rating,
            "unanswered_count": unanswered,
            "unanswered_in_signal": None,
            "recent_count": recent_total,
            "recent_low": recent_low,
        },
        "signal": {
            "title": signal["title"],
            "text": signal["text"],
            "source": signal["source"],
        },
        "variants": variants,
        "decision": {
            "text": decision_text,
            "actions": [
                "Проверить проблемные партии",
                "Обновить описание/ожидания",
                "Ответить на новые отзывы",
            ],
        },
        "reply_draft": "Спасибо за отзыв. Мы проверяем информацию и уточним детали.",
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
