#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

KEYWORDS = {
    "протек": "Крышка протекает",
    "подте": "Крышка протекает",
    "запах": "Запах/аромат",
    "вон": "Запах/аромат",
    "царап": "Царапины",
    "брак": "Брак",
    "слом": "Ломается",
    "не работает": "Не работает",
    "не включ": "Не включается",
    "мал": "Маломерит",
    "больш": "Большемерит",
}


def load_payload(path: str | None):
    if path:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    if isinstance(data, list) and data:
        return data[0]
    return data


def pick_variant(item):
    return item.get("color") or item.get("size") or "Остальные"


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    payload = load_payload(path)
    feedbacks = payload.get("feedbacks", []) if isinstance(payload, dict) else []

    stats = {
        "feedback_count": payload.get("feedback_count", len(feedbacks)),
        "rating": payload.get("rating"),
        "unanswered_count": 0,
        "unanswered_in_signal": 0,
    }

    issue_counts = defaultdict(int)
    issue_dates = defaultdict(list)
    variant_stats = defaultdict(lambda: {"count": 0, "sum": 0.0, "issues": 0})

    for f in feedbacks:
        text = (f.get("fb_text") or "").lower()
        rating = float(f.get("valuation") or 0)
        variant = pick_variant(f)

        variant_stats[variant]["count"] += 1
        variant_stats[variant]["sum"] += rating

        has_answer = bool(f.get("answer_text"))
        if not has_answer:
            stats["unanswered_count"] += 1

        matched_issue = None
        for key, label in KEYWORDS.items():
            if key in text:
                issue_counts[label] += 1
                matched_issue = label
                break

        if matched_issue:
            variant_stats[variant]["issues"] += 1
            if not has_answer:
                stats["unanswered_in_signal"] += 1
            dt = parse_date(f.get("fb_created_at") or "")
            if dt:
                issue_dates[matched_issue].append(dt)

    top_issue = None
    if issue_counts:
        top_issue = max(issue_counts.items(), key=lambda x: x[1])

    signal = {
        "title": "Сигнал не найден",
        "text": "Явных повторяющихся проблем не обнаружено.",
        "source": f"{stats['feedback_count']} отзывов",
    }

    if top_issue and top_issue[1] >= 3:
        label, count = top_issue
        days = None
        if issue_dates.get(label):
            oldest = min(issue_dates[label])
            days = (datetime.now(timezone.utc) - oldest).days
        signal = {
            "title": f"{label} — {count} раз",
            "text": "Повторяется у покупателей, стоит проверить.",
            "source": f"{count} отзывов{'' if days is None else f', за {days} дней'}",
        }

    variants = []
    for name, v in variant_stats.items():
        if v["count"] == 0:
            continue
        avg = round(v["sum"] / v["count"], 2)
        status = "problem" if v["issues"] >= 2 or avg <= 4.2 else "ok"
        variants.append({
            "name": name,
            "rating": avg,
            "count": v["count"],
            "status": status,
        })

    variants.sort(key=lambda x: (-x["count"], x["name"]))

    decision_text = "Проверить проблемные варианты и обновить описание."
    if top_issue and top_issue[1] >= 3:
        decision_text = "Проверить партии с проблемой и ответить на негатив."

    result = {
        "product": {
            "title": payload.get("title") or payload.get("nm_title") or "Товар",
            "article": str(payload.get("article") or payload.get("nm_id") or ""),
            "platform": "Wildberries",
        },
        "stats": stats,
        "signal": signal,
        "variants": variants[:3],
        "decision": {
            "text": decision_text,
            "actions": [
                "Проверить проблемные партии",
                "Обновить описание/ожидания",
                "Ответить на новые отзывы",
            ],
        },
        "reply_draft": "Спасибо за отзыв. Мы проверяем товар и уточним информацию.",
    }

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
