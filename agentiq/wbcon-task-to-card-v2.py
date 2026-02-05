#!/usr/bin/env python3
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

WINDOW_DAYS = 30

COLOR_WORDS = (
    "красн", "син", "сер", "черн", "бел", "зел", "желт", "роз",
    "фиолет", "голуб", "оранж", "беж", "хаки", "бордо", "коричн",
    "сереб", "золот"
)
NON_COLOR_HINTS = ("шт", "м", "мм", "см", "л", "мл", "люм", "кг", "гр", "набор", "комплект")

# Автодетект категории по названию товара
CATEGORY_KEYWORDS = {
    "flashlight": ["фонар", "налобн", "свет", "лампа", "прожектор", "светодиод"],
    "clothing": ["платье", "куртка", "брюки", "футболк", "одежд", "размер", "джинс", "пальто", "свитер"],
    "electronics": ["наушник", "колонк", "зарядк", "кабель", "смартфон", "планшет", "часы", "bluetooth"],
    "pet_food": ["корм", "кошк", "собак", "питом", "животн", "лакомств", "вкус"],
}

# ─────────────────────────────────────────────────────────────
# REASONS: гибридная система (универсальные + категорийные)
# ─────────────────────────────────────────────────────────────

# Универсальные причины — работают для любых товаров
UNIVERSAL_REASONS = {
    "defect": {
        "label": "Брак / дефект",
        "emoji": "🔧",
        "patterns": ["брак", "дефект", "сломал", "сломан", "не работа", "неисправ"],
    },
    "mismatch": {
        "label": "Не соответствует описанию",
        "emoji": "📋",
        "patterns": ["не соответств", "описани", "ожидал", "думал", "на фото", "по факту"],
    },
    "delivery": {
        "label": "Повреждение при доставке",
        "emoji": "📦",
        "patterns": ["доставк", "помят", "упаковк", "повреж", "пришл", "курьер"],
    },
}

# Категорийные пресеты — добавляются сверху для конкретных ниш
CATEGORY_PRESETS = {
    "flashlight": {
        "brightness": {
            "label": "Светит слабее, чем ожидали",
            "emoji": "💡",
            "patterns": ["свет", "ярк", "туск", "слаб", "люмен", "темн"],
        },
        "battery": {
            "label": "Быстро садится аккумулятор",
            "emoji": "🔋",
            "patterns": ["аккум", "заряд", "садит", "разряд", "батар", "держ"],
        },
        "waterproof": {
            "label": "Не держит воду / влагу",
            "emoji": "💧",
            "patterns": ["вод", "влаг", "промок", "залил", "герметич"],
        },
        "build": {
            "label": "Качество сборки",
            "emoji": "🔩",
            "patterns": ["сборк", "люфт", "скрип", "болтает", "хлипк", "пластик"],
        },
    },
    "clothing": {
        "size": {
            "label": "Не соответствует размеру",
            "emoji": "📏",
            "patterns": ["размер", "мал", "велик", "узк", "широк", "коротк", "длинн"],
        },
        "fabric": {
            "label": "Качество ткани",
            "emoji": "🧵",
            "patterns": ["ткань", "материал", "тонк", "просвеч", "линяет", "катыш"],
        },
        "color_mismatch": {
            "label": "Цвет не как на фото",
            "emoji": "🎨",
            "patterns": ["цвет", "оттенок", "фото", "картинк", "темнее", "светлее"],
        },
        "smell": {
            "label": "Неприятный запах",
            "emoji": "👃",
            "patterns": ["запах", "воняет", "пахнет", "химия", "вонь"],
        },
    },
    "electronics": {
        "battery": {
            "label": "Проблемы с батареей",
            "emoji": "🔋",
            "patterns": ["аккум", "заряд", "батар", "разряд", "держ"],
        },
        "connectivity": {
            "label": "Проблемы с подключением",
            "emoji": "📶",
            "patterns": ["подключ", "bluetooth", "wifi", "связь", "сопряж", "отключ"],
        },
        "sound": {
            "label": "Проблемы со звуком",
            "emoji": "🔊",
            "patterns": ["звук", "громк", "тих", "хрип", "шум", "динамик"],
        },
    },
    "pet_food": {
        "flavor_mismatch": {
            "label": "Прислали не тот вкус",
            "emoji": "🔄",
            "patterns": ["не тот", "другой вкус", "перепутал", "заказывал", "вместо", "ожидал", "прислали"],
        },
        "pet_rejection": {
            "label": "Питомец не ест",
            "emoji": "🐱",
            "patterns": ["не ест", "не стал", "отказ", "не нрав", "выплев", "понюхал"],
        },
        "packaging": {
            "label": "Проблемы с упаковкой",
            "emoji": "📦",
            "patterns": ["упаков", "порван", "рваный", "открыт", "помят", "просып"],
        },
        "freshness": {
            "label": "Качество / свежесть",
            "emoji": "🕐",
            "patterns": ["срок", "просроч", "запах", "плесен", "испорч", "старый"],
        },
        "composition": {
            "label": "Состав не устраивает",
            "emoji": "📋",
            "patterns": ["состав", "ингредиент", "добавк", "краситель", "химия"],
        },
    },
}

# Текущая категория (можно передавать как аргумент или определять автоматически)
CURRENT_CATEGORY = "flashlight"

# Собираем итоговый словарь: универсальные + категорийные
def get_reasons(category: str = None) -> dict:
    reasons = dict(UNIVERSAL_REASONS)
    if category and category in CATEGORY_PRESETS:
        reasons.update(CATEGORY_PRESETS[category])
    return reasons

REASONS = get_reasons(CURRENT_CATEGORY)

POSITIVE_HINTS = ("хорош", "отлич", "нрав", "класс", "рекоменд", "супер")


def detect_category(product_name: str = None, feedbacks: list = None) -> str:
    """Автоматически определяет категорию товара по названию или текстам отзывов."""
    # 1. Пробуем по названию товара
    if product_name:
        name_lower = product_name.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in name_lower:
                    return category

    # 2. Пробуем по текстам отзывов (первые 20)
    if feedbacks:
        category_scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for fb in feedbacks[:20]:
            text = " ".join([
                fb.get("fb_text") or "",
                fb.get("advantages") or "",
                fb.get("disadvantages") or "",
            ]).lower()
            for category, keywords in CATEGORY_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        category_scores[category] += 1
                        break
        # Выбираем категорию с максимальным счётом
        best = max(category_scores.items(), key=lambda x: x[1])
        if best[1] >= 2:  # минимум 2 совпадения
            return best[0]

    return "flashlight"  # default fallback


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-zа-я0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_color_variant(label: str) -> bool:
    t = normalize_text(label)
    if not t:
        return False
    if any(h in t for h in NON_COLOR_HINTS):
        return False
    if any(c in t for c in COLOR_WORDS):
        return True
    return False


def load_payload(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and data:
        return data[0]
    return data


def get_actions(category: str, target_variant: str) -> list:
    """Возвращает список рекомендаций в зависимости от категории."""
    base_actions = {
        "flashlight": [
            f"Проверить партии режима «{target_variant}» за последние 30 дней" if target_variant and target_variant != "Один товар" else "Проверить партии товара за последние 30 дней",
            "Сверить заявленную яркость с фактической",
            "Обновить описание: ожидания по яркости и автономности",
            "Ответить на негативные отзывы по шаблону (ниже)",
        ],
        "clothing": [
            "Проверить соответствие размерной сетки",
            "Сверить фото товара с реальным цветом",
            "Обновить описание: точные замеры и состав ткани",
            "Ответить на негативные отзывы по шаблону (ниже)",
        ],
        "electronics": [
            "Проверить партии товара за последние 30 дней",
            "Сверить заявленные характеристики с фактическими",
            "Обновить описание: время работы от батареи",
            "Ответить на негативные отзывы по шаблону (ниже)",
        ],
        "pet_food": [
            "Проверить логистику: часто путают вкусы при комплектации",
            "Связаться со складом WB по пересортице",
            "Обновить описание: чётко указать вкус и состав",
            "Ответить на негативные отзывы по шаблону (ниже)",
        ],
    }
    return base_actions.get(category, base_actions["flashlight"])


def get_reply_template(category: str, main_reason: str) -> str:
    """Возвращает шаблон ответа в зависимости от категории и причины."""
    templates = {
        "flashlight": "Спасибо за отзыв. Нам важно ваше замечание по яркости и времени работы. Мы уже проверяем информацию и уточним характеристики товара.",
        "clothing": "Благодарим за отзыв! Приносим извинения за несоответствие. Мы обновим информацию о размерах и цветах в карточке товара.",
        "electronics": "Спасибо за отзыв. Мы проверим информацию о времени работы батареи и обновим характеристики.",
        "pet_food": "Благодарим за отзыв! Очень жаль, что возникла такая ситуация. Мы проверим комплектацию на складе. Если прислали не тот вкус — напишите нам, поможем с обменом.",
    }
    # Специальные шаблоны для конкретных причин
    if category == "pet_food" and main_reason == "Прислали не тот вкус":
        return "Благодарим за отзыв! Приносим извинения за путаницу с вкусом. Это ошибка комплектации на складе. Напишите нам — поможем с обменом на нужный вкус."
    if category == "pet_food" and main_reason == "Питомец не ест":
        return "Благодарим за отзыв! Понимаем, что питомцы бывают привередливы. Этот корм подходит не всем — рекомендуем попробовать с небольшой упаковки. Если не подошёл — напишите нам."
    return templates.get(category, templates["flashlight"])


def classify_reasons(text: str, is_disadvantage: bool = False) -> list:
    """
    Классифицирует текст по причинам (multi-label).
    Возвращает список найденных причин.
    """
    t = normalize_text(text)
    if not t:
        return []
    # Для fb_text фильтруем позитив, для disadvantages — нет
    if not is_disadvantage and any(h in t for h in POSITIVE_HINTS):
        return []

    found = []
    for key, meta in REASONS.items():
        for p in meta["patterns"]:
            if p in t:
                found.append(key)
                break  # Один паттерн на причину достаточно

    return found if found else ["other"]


def main():
    if len(sys.argv) < 3:
        print("Usage: wbcon-task-to-card-v2.py <task-json> <output-json> [variant_name] [category]")
        print("Categories: flashlight, clothing, electronics, pet_food (auto-detected if not specified)")
        sys.exit(1)

    src_path = sys.argv[1]
    out_path = sys.argv[2]
    target_variant = sys.argv[3] if len(sys.argv) > 3 else None
    category_arg = sys.argv[4] if len(sys.argv) > 4 else None

    payload = load_payload(src_path)

    # Получаем название товара для автодетекта
    feedbacks = payload.get("feedbacks", []) if isinstance(payload, dict) else []
    product_name = payload.get("product_name") or ""
    if not product_name and feedbacks:
        # Попробуем взять из первого отзыва
        product_name = feedbacks[0].get("product_name") or feedbacks[0].get("name") or ""

    # Автодетект категории если не указана
    category = category_arg or detect_category(product_name, feedbacks)
    print(f"Category: {category} (auto-detected: {category_arg is None})")

    # Пересобираем REASONS под выбранную категорию
    global REASONS
    REASONS = get_reasons(category)
    feedbacks = payload.get("feedbacks", []) if isinstance(payload, dict) else []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    cutoff_prev = now - timedelta(days=WINDOW_DAYS * 2)  # Предыдущий период для тренда

    # Stats by variant
    variant_stats = defaultdict(lambda: {"count": 0, "sum": 0.0})
    variant_recent = defaultdict(lambda: {"count": 0, "sum": 0.0})
    variant_prev = defaultdict(lambda: {"count": 0, "sum": 0.0})  # Предыдущий период
    variant_reason_counts = defaultdict(lambda: Counter())
    variant_reason_recent = defaultdict(lambda: Counter())

    for f in feedbacks:
        variant_raw = f.get("color") or f.get("size") or "Остальные"
        variant = variant_raw.strip()
        if not is_color_variant(variant):
            variant = "Один товар"
        rating_val = float(f.get("valuation") or 0)
        dt = parse_date(f.get("fb_created_at") or "")

        variant_stats[variant]["count"] += 1
        variant_stats[variant]["sum"] += rating_val

        if dt and dt >= cutoff:
            variant_recent[variant]["count"] += 1
            variant_recent[variant]["sum"] += rating_val
        elif dt and dt >= cutoff_prev:
            # Предыдущий период (30-60 дней назад)
            variant_prev[variant]["count"] += 1
            variant_prev[variant]["sum"] += rating_val

        # Reasons: use disadvantages + advantages (негативный контекст) + fb_text
        disadvantages = f.get("disadvantages") or ""
        advantages = f.get("advantages") or ""
        fb_text = f.get("fb_text") or ""

        # Собираем все причины (multi-label)
        reasons_found = set()

        # 1. disadvantages — точно негатив
        if disadvantages:
            reasons_found.update(classify_reasons(disadvantages, is_disadvantage=True))

        # 2. advantages с негативным контекстом (люди пишут жалобы в advantages)
        if advantages and rating_val <= 3:
            reasons_found.update(classify_reasons(advantages, is_disadvantage=True))

        # 3. fb_text — только если не нашли в других полях
        if not reasons_found and fb_text:
            reasons_found.update(classify_reasons(fb_text, is_disadvantage=False))

        # Записываем все найденные причины
        for reason in reasons_found:
            variant_reason_counts[variant][reason] += 1
            if dt and dt >= cutoff:
                variant_reason_recent[variant][reason] += 1

    # Overall rating
    total = payload.get("feedback_count", len(feedbacks)) or 0
    rating = payload.get("rating") or 0
    if not rating:
        counts = {
            5: payload.get("five_valuation_distr", 0),
            4: payload.get("four_valuation_distr", 0),
            3: payload.get("three_valuation_distr", 0),
            2: payload.get("two_valuation_distr", 0),
            1: payload.get("one_valuation_distr", 0),
        }
        dist_total = sum(counts.values()) or total or 1
        rating = round(sum(k * v for k, v in counts.items()) / dist_total, 2)

    # Variant ratings
    def avg(stats):
        return round(stats["sum"] / stats["count"], 2) if stats["count"] else 0

    valid_colors = [v for v in variant_stats.keys() if v != "Один товар"]

    # Автовыбор варианта: худший по рейтингу (если есть варианты с достаточным кол-вом отзывов)
    if target_variant is None or target_variant not in variant_stats:
        if valid_colors:
            # Выбираем вариант с худшим рейтингом (минимум 3 отзыва)
            candidates = [v for v in valid_colors if variant_stats[v]["count"] >= 3]
            if candidates:
                target_variant = min(candidates, key=lambda k: avg(variant_stats[k]))
            else:
                target_variant = max(valid_colors, key=lambda k: variant_stats[k]["count"])
        else:
            target_variant = "Один товар"
    elif target_variant not in valid_colors and valid_colors:
        target_variant = max(valid_colors, key=lambda k: variant_stats[k]["count"])

    target_stats = variant_stats.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})
    target_avg = avg(target_stats)

    # Тренд: сравнение текущего периода с предыдущим
    target_recent = variant_recent.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})
    target_prev = variant_prev.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})
    recent_avg = avg(target_recent)
    prev_avg = avg(target_prev)

    trend = None
    trend_delta = 0
    if target_recent["count"] >= 3 and target_prev["count"] >= 3:
        trend_delta = round(recent_avg - prev_avg, 2)
        if trend_delta > 0.1:
            trend = "up"
        elif trend_delta < -0.1:
            trend = "down"
        else:
            trend = "stable"

    # Reasons for target variant (recent window)
    recent_total = variant_recent.get(target_variant, {"count": 0})["count"]
    recent_reasons = variant_reason_recent.get(target_variant, Counter())
    total_reasons = variant_reason_counts.get(target_variant, Counter())

    # Choose window: if recent has enough data, use recent; else fallback to all
    use_recent = recent_total >= 8
    reason_counts = recent_reasons if use_recent else total_reasons
    reason_total = sum(reason_counts.values()) or 0

    reason_rows = []
    if reason_total:
        for key, cnt in reason_counts.most_common():
            if key == "other":
                label = "Прочее"
                emoji = "❓"
            else:
                label = REASONS[key]["label"]
                emoji = REASONS[key]["emoji"]
            reason_rows.append({
                "label": label,
                "emoji": emoji,
                "count": cnt,
                "share": round(cnt / reason_total * 100),
            })

    # Comparison with other variants for same reasons
    compare_variants = [v for v in valid_colors if v != target_variant]
    compare_variants = sorted(compare_variants, key=lambda k: variant_stats[k]["count"], reverse=True)[:2]
    compare_rows = []
    for v in compare_variants:
        v_total = variant_recent[v]["count"] if use_recent else variant_stats[v]["count"]
        if v_total == 0:
            compare_rows.append({"name": v, "share": None})
            continue
        v_reasons = variant_reason_recent[v] if use_recent else variant_reason_counts[v]
        v_reason_total = sum(v_reasons.values()) or 0
        share = round(v_reason_total / max(v_total, 1) * 100) if v_reason_total else 0
        compare_rows.append({"name": v, "share": share})

    article = None
    if feedbacks:
        article = feedbacks[0].get("article")

    data_window = f"{WINDOW_DAYS} дней" if use_recent else "весь период"
    signal_title = f"⚠ Проблема в режиме: {target_variant} спектр" if target_variant and target_variant != "Один товар" else "⚠ Проблема в товаре"

    main_reason = None
    if reason_rows:
        main_reason = reason_rows[0]["label"]

    if target_variant and target_variant != "Один товар":
        summary_lines = [
            "Рейтинг ниже остальных режимов",
        ]
        if main_reason:
            summary_lines.append(f"Причина: {main_reason}")
        summary_lines.append("Риск падения рейтинга карточки")
        signal_summary = "\n".join(summary_lines)
    else:
        signal_summary = "Повторяющаяся причина, не случайность"

    # Категорийно-зависимые тексты
    category_labels = {
        "flashlight": {"type": "режиму", "item": "режима"},
        "clothing": {"type": "варианту", "item": "варианта"},
        "electronics": {"type": "варианту", "item": "варианта"},
        "pet_food": {"type": "товару", "item": "товара"},
    }
    cat_label = category_labels.get(category, {"type": "варианту", "item": "варианта"})

    result = {
        "header": {
            "title": f"Артикул {article or ''} · Риск по {cat_label['type']}",
            "subtitle": f"WB · {total} отзывов · рейтинг {rating} · данные за {data_window}",
            "rating": rating,
        },
        "signal": {
            "title": signal_title,
            "summary": signal_summary,
            "scores": [
                {
                    "label": f"{target_variant or 'товар'}",
                    "value": target_avg,
                    "trend": trend,
                    "trend_delta": trend_delta,
                    "prev_value": prev_avg if trend else None,
                },
                {"label": compare_variants[0] if len(compare_variants) > 0 else "—", "value": avg(variant_stats.get(compare_variants[0], {"count":0,"sum":0.0})) if len(compare_variants) > 0 else 0},
                {"label": compare_variants[1] if len(compare_variants) > 1 else "—", "value": avg(variant_stats.get(compare_variants[1], {"count":0,"sum":0.0})) if len(compare_variants) > 1 else 0},
            ],
            "meta": f"{target_stats['count']} отзывов, доверие: среднее",
            "trend_info": f"За {WINDOW_DAYS} дн: {'+' if trend_delta > 0 else ''}{trend_delta}" if trend else None,
        },
        "reasons": {
            "title": f"Почему именно этот {cat_label['type'].replace('у', '')} проседает" if target_variant and target_variant != "Один товар" else "Причины негативных отзывов",
            "items": reason_rows,
            "cta": f"Показать отзывы ({target_stats['count']})",
        },
        "compare": {
            "title": "Это аномалия или норма",
            "rows": compare_rows,
            "conclusion": f"Проблема специфична для режима «{target_variant}»" if target_variant and target_variant != "Один товар" else "Проблема относится ко всему товару",
        },
        "risk": {
            "title": "Потенциальный риск",
            "items": [
                "Вероятное падение конверсии: –3–6%",
                "Рост негатива в рекламе",
                "Риск падения рейтинга карточки",
            ],
            "note": "Оценка на основе исторических данных по WB",
        },
        "actions": {
            "title": "Что делать сейчас",
            "items": get_actions(category, target_variant),
            "status": "⏳ Под наблюдением, пересчет сигнала через 7 дней",
        },
        "reply": {
            "title": "Черновик ответа (авто)",
            "text": get_reply_template(category, main_reason),
            "note": "Ответ не снижает проблему, но снижает повторный негатив.",
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
