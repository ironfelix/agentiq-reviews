#!/usr/bin/env python3
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from dotenv import load_dotenv
    # Load .env from apps/reviews (where credentials live)
    _env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "apps",
        "reviews",
        ".env",
    )
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

try:
    from llm_analyzer import llm_classify_reasons, llm_get_actions, llm_get_reply_template, llm_deep_analysis, llm_analyze_communication
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

WINDOW_DAYS = 30
MIN_REVIEWS_FOR_SIGNAL = 5   # Minimum reviews per variant to consider it for signal
MIN_GAP_FOR_SIGNAL = 0.3     # Minimum rating gap vs others to trigger signal


# ─── WB card description API ────────────────────────────────
def _wb_basket_num(nm_id: int) -> str:
    """Determine WB basket server number from nmId."""
    vol = nm_id // 100000
    ranges = [
        (143, "01"), (287, "02"), (431, "03"), (719, "04"),
        (1007, "05"), (1061, "06"), (1115, "07"), (1169, "08"),
        (1313, "09"), (1601, "10"), (1655, "11"), (1919, "12"),
        (2045, "13"), (2189, "14"), (2405, "15"), (2621, "16"),
        (2837, "17"), (3053, "18"), (3269, "19"), (3485, "20"),
        (3701, "21"), (3917, "22"), (4133, "23"), (4349, "24"),
        (4565, "25"),
    ]
    for threshold, num in ranges:
        if vol <= threshold:
            return num
    return "26"


def fetch_wb_card_info(nm_id: int):
    """Fetch product card from WB public API (no auth needed).

    Returns dict with keys: imt_name, description, options, subj_name
    or None on any error.
    """
    try:
        nm_id = int(nm_id)
    except (TypeError, ValueError):
        return None

    vol = nm_id // 100000
    part = nm_id // 1000
    basket = _wb_basket_num(nm_id)
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, OSError) as e:
        print(f"[WB card] Failed to fetch {nm_id}: {e}")
        return None

    description = data.get("description", "")
    options_raw = data.get("options", [])
    options_str = "; ".join(
        f"{o['name']}: {o['value']}" for o in options_raw
        if o.get("name") and o.get("value")
    )

    # Extract price from sizes[0].price (in kopeks)
    # Prefer 'product' (sale price) > 'total' (with WB wallet) > 'basic' (full price)
    price_kopeks = 0
    sizes = data.get("sizes", [])
    if sizes and isinstance(sizes, list):
        price_data = sizes[0].get("price", {})
        price_kopeks = price_data.get("product") or price_data.get("total") or price_data.get("basic", 0)
    price_rub = round(price_kopeks / 100, 2) if price_kopeks else None

    result = {
        "imt_name": data.get("imt_name", ""),
        "description": description,
        "options": options_str,
        "subj_name": data.get("subj_name", ""),
        "price": price_rub,
    }
    print(f"[WB card] OK: {result['imt_name'][:60]}, price: {price_rub}₽")
    return result


def fetch_wb_price_history(nm_id: int):
    """Fetch price history from WB CDN (no auth needed).

    URL: basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/price-history.json
    Returns list of {"dt": unix_ts, "price_rub": float} sorted by date,
    or None on error.
    Prices in the API are in kopecks (÷100 for rubles).
    """
    try:
        nm_id = int(nm_id)
    except (TypeError, ValueError):
        return None

    vol = nm_id // 100000
    part = nm_id // 1000
    basket = _wb_basket_num(nm_id)
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/price-history.json"

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
        with urlopen(req, timeout=5) as resp:
            raw = resp.read()
            # Handle gzip encoding
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode())
    except (URLError, json.JSONDecodeError, OSError) as e:
        print(f"[WB price] Failed to fetch {nm_id}: {e}")
        return None

    if not isinstance(data, list) or len(data) == 0:
        return None

    result = []
    for entry in data:
        dt = entry.get("dt")
        price_info = entry.get("price", {})
        rub_kopecks = price_info.get("RUB", 0)
        if dt and rub_kopecks:
            result.append({
                "dt": dt,
                "price_rub": round(rub_kopecks / 100, 2),
            })

    result.sort(key=lambda x: x["dt"])
    if result:
        print(f"[WB price] OK: {len(result)} data points, latest: {result[-1]['price_rub']}₽")
    return result if result else None


def avg_price_from_history(price_history, months=3):
    """Calculate average price from last N months of price history.

    Returns float (average price in rubles) or None.
    """
    if not price_history:
        return None

    import time
    now = time.time()
    cutoff = now - (months * 30 * 86400)

    recent = [p["price_rub"] for p in price_history if p["dt"] >= cutoff]
    if not recent:
        # Fall back to all data
        recent = [p["price_rub"] for p in price_history]
    if not recent:
        return None

    return round(sum(recent) / len(recent), 2)


def calculate_money_loss(review_count, period_months, price_rub, quality_score):
    """Calculate estimated money loss from poor communication quality.

    Args:
        review_count: Total reviews received
        period_months: Period in months
        price_rub: Product price in rubles
        quality_score: LLM quality score (1-10)

    Returns:
        {
            "purchases_per_month_min": int,
            "purchases_per_month_max": int,
            "revenue_per_month_min": int,
            "revenue_per_month_max": int,
            "loss_per_month_min": int,
            "loss_per_month_max": int,
        }
        or None if price is not available
    """
    if not price_rub or price_rub <= 0:
        return None

    # Review rate assumptions (3-5% for functional products)
    review_rate_min = 0.03
    review_rate_max = 0.05

    # Calculate purchases
    total_purchases_min = int(review_count / review_rate_max)  # conservative
    total_purchases_max = int(review_count / review_rate_min)  # optimistic

    purchases_per_month_min = int(total_purchases_min / period_months)
    purchases_per_month_max = int(total_purchases_max / period_months)

    # Calculate revenue
    revenue_per_month_min = int(purchases_per_month_min * price_rub)
    revenue_per_month_max = int(purchases_per_month_max * price_rub)

    # CR impact based on quality score (inverse relationship)
    # Note: risky weight = 1 (not 2), harm index calculation adjusted accordingly
    cr_impact_min = 0.02  # 2% for quality 4-6
    cr_impact_max = 0.04  # 4% for quality 1-3

    if quality_score >= 7:
        cr_impact_min, cr_impact_max = 0.01, 0.02
    elif quality_score >= 4:
        cr_impact_min, cr_impact_max = 0.02, 0.04
    else:
        cr_impact_min, cr_impact_max = 0.03, 0.06

    # Calculate losses
    loss_per_month_min = int(revenue_per_month_min * cr_impact_min)
    loss_per_month_max = int(revenue_per_month_max * cr_impact_max)

    return {
        "purchases_per_month_min": purchases_per_month_min,
        "purchases_per_month_max": purchases_per_month_max,
        "revenue_per_month_min": revenue_per_month_min,
        "revenue_per_month_max": revenue_per_month_max,
        "loss_per_month_min": loss_per_month_min,
        "loss_per_month_max": loss_per_month_max,
        "price_rub": round(price_rub),
        "review_count": review_count,
        "period_months": period_months,
        "conversion_loss_pct_min": round(cr_impact_min * 100),
        "conversion_loss_pct_max": round(cr_impact_max * 100),
    }


# ─── WBCON Questions API ─────────────────────────────────────
def fetch_wbcon_questions(nm_id, email, password):
    # type: (int, str, str) -> list
    """Fetch customer questions from WBCON QS API.

    Creates a task, polls for completion, then retrieves results.
    Returns list of question dicts or empty list on any error.
    Timeout: 120 seconds total for polling.
    """
    qs_base = os.getenv("WBCON_QS_BASE", "https://qs.wbcon.su")

    # 1. Create task
    print(f"[WBCON QS] Creating task for article {nm_id}...")
    create_url = f"{qs_base}/create_task_qs?email={email}&password={password}"
    body = json.dumps({"article": int(nm_id)}).encode("utf-8")
    try:
        req = Request(create_url, data=body, method="POST",
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            create_data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, OSError) as e:
        print(f"[WBCON QS] Failed to create task: {e}")
        return []

    task_id = create_data.get("task_id")
    if not task_id:
        print(f"[WBCON QS] No task_id in response: {create_data}")
        return []
    print(f"[WBCON QS] Task created: {task_id}")

    # 2. Poll for status (max 120 seconds, 5s interval = 24 attempts)
    import time as _time
    deadline = _time.time() + 120
    while _time.time() < deadline:
        status_url = f"{qs_base}/task_status?task_id={task_id}&email={email}&password={password}"
        try:
            req = Request(status_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=10) as resp:
                status_data = json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, OSError) as e:
            print(f"[WBCON QS] Status check failed: {e}")
            _time.sleep(5)
            continue

        if status_data.get("is_ready"):
            break

        error = status_data.get("error", "")
        if error:
            print(f"[WBCON QS] Task error: {error}")
            return []

        _time.sleep(5)
    else:
        print("[WBCON QS] Timeout waiting for task to complete (120s)")
        return []

    # 3. Get results
    results_url = f"{qs_base}/get_results_qs?task_id={task_id}&email={email}&password={password}"
    try:
        req = Request(results_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            results_data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, OSError) as e:
        print(f"[WBCON QS] Failed to get results: {e}")
        return []

    # Response is a list; questions are in the first element
    questions = []
    if isinstance(results_data, list) and results_data:
        questions = results_data[0].get("questions", [])
    elif isinstance(results_data, dict):
        questions = results_data.get("questions", [])

    print(f"[WBCON QS] Got {len(questions)} questions")
    return questions


COLOR_WORDS = (
    "красн", "син", "сер", "черн", "бел", "зел", "желт", "роз",
    "фиолет", "голуб", "оранж", "беж", "хаки", "бордо", "коричн",
    "сереб", "золот"
)
NON_COLOR_HINTS = ("шт", "м", "мм", "см", "л", "мл", "люм", "кг", "гр", "набор", "комплект")

# Автодетект категории по названию товара
CATEGORY_KEYWORDS = {
    "flashlight": ["фонар", "налобн", "прожектор", "светодиод"],
    "clothing": ["платье", "куртка", "брюки", "футболк", "одежд", "размер", "джинс", "пальто", "свитер"],
    "electronics": ["наушник", "колонк", "зарядк", "кабель", "смартфон", "планшет", "часы", "bluetooth"],
    "pet_food": ["корм", "кошк", "собак", "питом", "животн", "лакомств", "вкус"],
    "kitchen": ["чайник", "кастрюл", "сковород", "термос", "термокружк",
                "блендер", "миксер", "тостер", "микроволн", "мультиварк",
                "кофевар", "чайный", "кипят", "литр", "электрочайн"],
    "home": ["постель", "полотенц", "подушк", "одеяло", "плед",
             "штор", "ковр", "матрас", "покрывал", "наволоч"],
    "beauty": ["крем", "маска", "шампунь", "косметик", "помад",
               "тушь", "пудр", "тональ", "сыворотк", "бальзам"],
    "toys": ["игрушк", "кукл", "конструктор", "машинк", "пазл",
             "мягк", "плюшев", "лего", "робот"],
    "auto": ["автомобил", "машин", "руль", "бампер", "фар",
             "видеорегистратор", "навигатор", "автомойк"],
    "sports": ["гантел", "коврик", "тренажер", "мяч", "скакалк",
               "фитнес", "йога", "велосипед", "самокат"],
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
    "kitchen": {
        "not_heating": {
            "label": "Не нагревает / не кипятит",
            "emoji": "🔥",
            "patterns": ["не кипят", "не грет", "не нагрев", "холодн", "не горяч", "долго грет", "долго кипят"],
        },
        "leaking": {
            "label": "Протекает",
            "emoji": "💧",
            "patterns": ["проте", "течет", "теч", "капает", "подтек", "льёт"],
        },
        "cable": {
            "label": "Проблемы с кабелем / подставкой",
            "emoji": "🔌",
            "patterns": ["шнур", "кабел", "провод", "зарядк", "usb", "подставк", "контакт"],
        },
        "stopped_working": {
            "label": "Перестал работать",
            "emoji": "⛔",
            "patterns": ["перестал", "не включ", "сгорел", "вышел из строя", "не работ", "сдох"],
        },
        "noise": {
            "label": "Шумит / гудит",
            "emoji": "🔊",
            "patterns": ["шум", "гуд", "громк", "тих", "свист", "трещ"],
        },
        "smell_taste": {
            "label": "Запах / привкус",
            "emoji": "👃",
            "patterns": ["запах", "пахн", "привкус", "пластик", "воняет", "химия"],
        },
    },
    "home": {
        "fabric_quality": {
            "label": "Качество ткани / материала",
            "emoji": "🧵",
            "patterns": ["ткань", "материал", "тонк", "просвеч", "линяет", "катыш", "рвёт"],
        },
        "size_mismatch": {
            "label": "Не соответствует размеру",
            "emoji": "📏",
            "patterns": ["размер", "мал", "велик", "узк", "коротк", "длинн"],
        },
        "smell": {
            "label": "Неприятный запах",
            "emoji": "👃",
            "patterns": ["запах", "воняет", "пахнет", "химия", "вонь"],
        },
        "color_fading": {
            "label": "Цвет выцветает / линяет",
            "emoji": "🎨",
            "patterns": ["цвет", "линя", "выцвет", "полинял", "красит", "стирк"],
        },
    },
    "beauty": {
        "allergy": {
            "label": "Аллергия / раздражение",
            "emoji": "🤧",
            "patterns": ["аллерг", "раздраж", "покрасн", "зуд", "чешет", "сыпь", "жжён"],
        },
        "no_effect": {
            "label": "Нет эффекта",
            "emoji": "😐",
            "patterns": ["не помог", "эффект", "не работ", "бесполезн", "не замет", "без результат"],
        },
        "texture": {
            "label": "Консистенция / текстура",
            "emoji": "💧",
            "patterns": ["жидк", "густ", "консистенц", "текстур", "липк", "жирн"],
        },
        "smell": {
            "label": "Неприятный запах",
            "emoji": "👃",
            "patterns": ["запах", "пахн", "аромат", "воняет", "отдушк"],
        },
    },
    "toys": {
        "safety": {
            "label": "Безопасность (мелкие детали, острые края)",
            "emoji": "⚠️",
            "patterns": ["остр", "мелк", "опасн", "порез", "токсичн", "краск"],
        },
        "durability": {
            "label": "Быстро ломается",
            "emoji": "💔",
            "patterns": ["слома", "развал", "хлипк", "непрочн", "отвал", "оторвал"],
        },
        "not_as_pictured": {
            "label": "Не как на картинке",
            "emoji": "🖼️",
            "patterns": ["не как", "фото", "картинк", "отличает", "ожидал", "обман"],
        },
    },
    "auto": {
        "fitment": {
            "label": "Не подходит по размеру / креплению",
            "emoji": "🔧",
            "patterns": ["не подход", "не подошёл", "крепл", "размер", "не влез", "не встал"],
        },
        "material": {
            "label": "Плохой материал",
            "emoji": "🧱",
            "patterns": ["материал", "пластик", "хлипк", "тонк", "дешёв", "китай"],
        },
    },
    "sports": {
        "durability": {
            "label": "Быстро изнашивается",
            "emoji": "💔",
            "patterns": ["износ", "порвал", "протёр", "развал", "слома", "лопнул"],
        },
        "comfort": {
            "label": "Неудобно использовать",
            "emoji": "😣",
            "patterns": ["неудобн", "натира", "давит", "жмёт", "скольз", "больн"],
        },
        "smell": {
            "label": "Запах материала",
            "emoji": "👃",
            "patterns": ["запах", "воняет", "пахнет", "химия", "резин"],
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

    return "general"  # default fallback — универсальная категория


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
    if any(c in t for c in COLOR_WORDS):
        return True
    return False


def normalize_variant(raw: str) -> str:
    """Нормализует вариант: 'Черный · 0.45 л' -> 'черный', 'белый иней' -> 'белый'."""
    v = raw.lower().strip()
    # Убрать размер/объём после разделителя: "Черный · 0.45 л" -> "черный"
    v = re.sub(r'[·\-/]\s*\d+.*$', '', v).strip()
    # Убрать числа с единицами: "черный 0.45 л" -> "черный"
    v = re.sub(r'\s+\d+[\.,]?\d*\s*(л|мл|шт|м|мм|см|кг|гр)\b.*$', '', v).strip()
    # Убрать модификаторы цвета: "белый иней" -> "белый", "синий металлик" -> "синий"
    v = re.sub(r'\s+(иней|металлик|перламутр|матовый|глянцевый|насыщенный)$', '', v).strip()
    return v


def load_payload(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and data:
        return data[0]
    return data


def get_actions(category: str, target_variant: str, reason_rows: list = None) -> list:
    """Генерирует список рекомендаций на основе найденных причин."""
    actions = []

    # 1. Всегда: проверить партии
    if target_variant and target_variant != "Один товар":
        actions.append(f"Проверить партии варианта «{target_variant}» за последние 30 дней")
    else:
        actions.append("Проверить партии товара за последние 30 дней")

    # 2. Динамические действия на основе top причины
    if reason_rows:
        top_reason = reason_rows[0].get("label", "").lower()
        if any(w in top_reason for w in ["нагрев", "кипят"]):
            actions.append("Проверить нагревательный элемент и термостат у партии")
        elif any(w in top_reason for w in ["протек", "теч"]):
            actions.append("Проверить герметичность и качество сборки")
        elif any(w in top_reason for w in ["кабел", "шнур", "подставк", "контакт"]):
            actions.append("Проверить комплектность и качество кабеля/подставки")
        elif any(w in top_reason for w in ["перестал", "не работ", "не включ"]):
            actions.append("Связаться с производителем — массовый дефект партии")
        elif any(w in top_reason for w in ["шум", "гуд", "громк"]):
            actions.append("Проверить шумоизоляцию и качество сборки")
        elif any(w in top_reason for w in ["вод", "влаг", "герметичн"]):
            actions.append("Проверить герметичность и качество сборки")
        elif any(w in top_reason for w in ["яркость", "свет", "тускл"]):
            actions.append("Сверить заявленную яркость с фактической")
        elif any(w in top_reason for w in ["размер", "маломер", "большемер"]):
            actions.append("Проверить соответствие размерной сетки")
        elif any(w in top_reason for w in ["батаре", "аккумулятор", "заряд"]):
            actions.append("Проверить ёмкость батареи и время работы")
        elif any(w in top_reason for w in ["запах", "пахн", "привкус"]):
            actions.append("Проверить материалы и условия хранения")
        elif any(w in top_reason for w in ["цвет", "отлича", "линя", "выцвет"]):
            actions.append("Сверить фото товара с реальным цветом")
        elif any(w in top_reason for w in ["брак", "дефект", "сломал"]):
            actions.append("Связаться с производителем по качеству партии")
        elif any(w in top_reason for w in ["не тот", "путают", "пересорт"]):
            actions.append("Проверить логистику и комплектацию на складе")
        elif any(w in top_reason for w in ["аллерг", "раздраж"]):
            actions.append("Проверить сертификаты и состав продукта")
        elif any(w in top_reason for w in ["ломает", "развал", "хлипк", "непрочн"]):
            actions.append("Проверить качество материалов и сборки")
        else:
            actions.append("Сверить заявленные характеристики с фактическими")

    # 3. Всегда: обновить описание
    actions.append("Обновить описание товара с учётом выявленных проблем")

    # 4. Всегда: ответить на отзывы
    actions.append("Ответить на негативные отзывы по шаблону (ниже)")

    return actions


def get_reply_template(category: str, main_reason: str) -> str:
    """Генерирует шаблон ответа на основе главной причины негатива."""
    reason_lower = main_reason.lower() if main_reason else ""

    if any(w in reason_lower for w in ["нагрев", "кипят"]):
        return "Спасибо за отзыв. Приносим извинения! Мы уже проверяем нагревательный элемент у данной партии. Напишите нам — поможем с заменой."
    elif any(w in reason_lower for w in ["протек", "теч"]):
        return "Спасибо за отзыв. Нам важно ваше замечание. Мы проверяем герметичность данной партии. Напишите нам для решения вопроса."
    elif any(w in reason_lower for w in ["кабел", "шнур", "подставк"]):
        return "Благодарим за отзыв! Приносим извинения за неудобства. Мы проверим комплектность данной партии. Напишите нам — поможем решить вопрос."
    elif any(w in reason_lower for w in ["перестал", "не работ", "не включ"]):
        return "Благодарим за отзыв! Приносим извинения за доставленные неудобства. Мы передали информацию производителю для проверки партии. Напишите нам — поможем с возвратом."
    elif any(w in reason_lower for w in ["шум", "гуд"]):
        return "Спасибо за отзыв. Мы проверим качество сборки данной партии. Напишите нам — поможем решить вопрос."
    elif any(w in reason_lower for w in ["вод", "влаг", "герметичн"]):
        return "Спасибо за отзыв. Нам важно ваше замечание. Мы уже проверяем качество сборки и герметичность по данной партии."
    elif any(w in reason_lower for w in ["брак", "дефект", "сломал"]):
        return "Благодарим за отзыв! Приносим извинения за доставленные неудобства. Мы передали информацию о дефекте производителю для проверки партии."
    elif any(w in reason_lower for w in ["размер", "маломер", "большемер"]):
        return "Благодарим за отзыв! Мы обновим информацию о размерах в карточке товара, чтобы другим покупателям было проще выбрать."
    elif any(w in reason_lower for w in ["не тот", "путают", "пересорт"]):
        return "Благодарим за отзыв! Приносим извинения за путаницу. Это ошибка комплектации на складе. Напишите нам — поможем решить вопрос."
    elif any(w in reason_lower for w in ["запах", "пахн", "привкус"]):
        return "Спасибо за отзыв. Мы проверим условия хранения и материалы данной партии."
    elif any(w in reason_lower for w in ["батаре", "аккумулятор", "заряд"]):
        return "Спасибо за отзыв. Мы проверим информацию о времени работы и обновим характеристики товара."
    elif any(w in reason_lower for w in ["аллерг", "раздраж"]):
        return "Спасибо за отзыв. Мы проверим сертификаты и состав данной партии. Рекомендуем обратиться к врачу при сильной реакции."
    else:
        return "Спасибо за отзыв. Нам важно ваше замечание. Мы уже проверяем информацию и уточним характеристики товара."


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


# ─────────────────────────────────────────────────────────────
# LLM fallback wrappers
# ─────────────────────────────────────────────────────────────

def _get_actions_with_fallback(use_llm: bool, category: str, target_variant: str, reason_rows: list) -> list:
    """Try LLM actions, fall back to rule-based."""
    if use_llm and reason_rows:
        try:
            result = llm_get_actions(category, target_variant, reason_rows)
            if result:
                print(f"LLM get_actions: OK ({len(result)} actions)")
                return result
            print("LLM get_actions: returned None, fallback")
        except Exception as e:
            print(f"LLM get_actions: error {e}, fallback")
    return get_actions(category, target_variant, reason_rows)


def _get_reply_with_fallback(use_llm: bool, category: str, main_reason: str, product_name: str, target_variant: str) -> str:
    """Try LLM reply, fall back to rule-based."""
    if use_llm and main_reason:
        try:
            result = llm_get_reply_template(category, main_reason, product_name, target_variant)
            if result:
                print(f"LLM get_reply: OK")
                return result
            print("LLM get_reply: returned None, fallback")
        except Exception as e:
            print(f"LLM get_reply: error {e}, fallback")
    return get_reply_template(category, main_reason)


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
        product_name = feedbacks[0].get("product_name") or feedbacks[0].get("name") or ""

    # Fetch WB card description (public API, no auth)
    nm_id = None
    if feedbacks:
        nm_id = feedbacks[0].get("article")
    wb_card = fetch_wb_card_info(nm_id) if nm_id else None

    if wb_card:
        if not product_name:
            product_name = wb_card["imt_name"]

    # Fetch questions from WBCON
    questions = []
    wbcon_email = os.getenv("WBCON_EMAIL", "")
    wbcon_pass = os.getenv("WBCON_PASS", "")
    if nm_id and wbcon_email and wbcon_pass:
        questions = fetch_wbcon_questions(int(nm_id), wbcon_email, wbcon_pass)

    # Автодетект категории если не указана
    category = category_arg or detect_category(product_name, feedbacks)
    print(f"Category: {category} (auto-detected: {category_arg is None})")

    # LLM mode
    use_llm = os.getenv("USE_LLM", "1") == "1" and LLM_AVAILABLE
    print(f"LLM mode: {'enabled' if use_llm else 'disabled'}")

    # Пересобираем REASONS под выбранную категорию
    global REASONS
    REASONS = get_reasons(category)
    feedbacks = payload.get("feedbacks", []) if isinstance(payload, dict) else []

    # Deduplicate feedbacks by ID
    seen_ids = set()
    unique_feedbacks = []
    for fb in feedbacks:
        fb_id = fb.get("id") or fb.get("fb_id")
        if fb_id and fb_id in seen_ids:
            continue
        if fb_id:
            seen_ids.add(fb_id)
        unique_feedbacks.append(fb)
    if len(unique_feedbacks) < len(feedbacks):
        print(f"Dedup: {len(feedbacks)} -> {len(unique_feedbacks)} feedbacks")
    feedbacks = unique_feedbacks

    # Filter feedbacks to last 12 months (366 days to include boundary dates)
    now_utc = datetime.now(timezone.utc)
    cutoff_12months = now_utc - timedelta(days=366)
    filtered_feedbacks = []
    for fb in feedbacks:
        created_str = fb.get("created_at") or fb.get("fb_created_at") or ""
        if not created_str:
            continue
        try:
            # Parse ISO date: "2025-02-07T12:34:56Z" or "2025-02-07 12:34:56"
            created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if created_dt >= cutoff_12months:
                filtered_feedbacks.append(fb)
        except (ValueError, AttributeError):
            # If date parse fails, include (safer to include than exclude)
            filtered_feedbacks.append(fb)
    if len(filtered_feedbacks) < len(feedbacks):
        print(f"12-month filter: {len(feedbacks)} -> {len(filtered_feedbacks)} feedbacks")
    feedbacks = filtered_feedbacks

    # Build article -> display_name mapping
    # Group by article, use article as variant key (reliable), color as display name
    # WBCON may return different color names for same article (renamed over time)
    # so we just strip size/volume suffixes but keep color modifiers
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    cutoff_prev = now - timedelta(days=WINDOW_DAYS * 2)

    has_multiple_articles = len(set(f.get("article", "") for f in feedbacks if f.get("article"))) > 1
    # Track colors per article — prefer recent names (WBCON may rename variants)
    article_colors_recent = defaultdict(lambda: Counter())  # last 30 days
    article_colors_all = defaultdict(lambda: Counter())
    for fb in feedbacks:
        art = fb.get("article", "")
        color = (fb.get("color") or "").strip()
        if not art or not color:
            continue
        # Normalize: "серый, зеленый, хаки" -> "серый", "Белый · 0.45 л" -> "белый"
        c = color.lower().strip()
        # Multi-color: take first color only
        if ", " in c:
            c = c.split(", ")[0].strip()
        c = re.sub(r'[·\-/]\s*\d+.*$', '', c).strip()
        c = re.sub(r'\s+\d+[\.,]?\d*\s*(л|мл|шт|м|мм|см|кг|гр)\b.*$', '', c).strip()
        article_colors_all[art][c] += 1
        dt = parse_date(fb.get("fb_created_at") or "")
        if dt and dt >= cutoff:
            article_colors_recent[art][c] += 1

    article_display = {}
    # First pass: get color for each article (prefer real colors over "1 шт." labels)
    art_color_map = {}
    for art in article_colors_all:
        # Try recent first, fall back to all-time, but always prefer window with real colors
        recent = article_colors_recent.get(art)
        all_colors = article_colors_all[art]
        if not all_colors:
            art_color_map[art] = "?"
            continue
        recent_real = {c: n for c, n in (recent or {}).items() if c and is_color_variant(c)}
        all_real = {c: n for c, n in all_colors.items() if c and is_color_variant(c)}
        if recent_real:
            real_colors = recent_real
        elif all_real:
            real_colors = all_real
        else:
            art_color_map[art] = f"арт. ...{art[-4:]}" if len(art) >= 4 else f"арт. {art}"
            continue
        best = sorted(real_colors.items(), key=lambda x: (-x[1], -len(x[0])))[0][0]
        art_color_map[art] = best

    # Count how many articles share the same color name
    color_usage = Counter(art_color_map.values())

    # Second pass: if color is unique — just use color; if duplicate — add article number
    color_seen = Counter()
    for art in sorted(art_color_map.keys()):
        color_name = art_color_map[art]
        if color_usage[color_name] > 1:
            color_seen[color_name] += 1
            article_display[art] = f"{color_name} #{color_seen[color_name]}"
        else:
            article_display[art] = color_name

    if has_multiple_articles:
        print(f"Article->variant mapping: {dict(article_display)}")
    else:
        print(f"Single article, using color field for variants")

    # Stats by variant
    variant_stats = defaultdict(lambda: {"count": 0, "sum": 0.0})
    variant_recent = defaultdict(lambda: {"count": 0, "sum": 0.0})
    variant_prev = defaultdict(lambda: {"count": 0, "sum": 0.0})  # Предыдущий период
    variant_reason_counts = defaultdict(lambda: Counter())
    variant_reason_recent = defaultdict(lambda: Counter())

    # LLM: коллектор негативных текстов для батч-классификации
    negative_texts_for_llm = []  # [{"variant": str, "text": str}]
    # Review samples for display in card (all negative reviews, not just LLM mode)
    negative_review_samples = []  # [{"variant": str, "text": str, "rating": int, "date": str}]

    for f in feedbacks:
        # Determine variant: use article mapping if multiple articles, else use color
        if has_multiple_articles:
            art = f.get("article", "")
            variant = article_display.get(art, art) if art else "Один товар"
        else:
            variant_raw = f.get("color") or f.get("size") or "Остальные"
            variant = variant_raw.strip()
            if is_color_variant(variant):
                variant = normalize_variant(variant)
            else:
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

        # Collect negative review samples for display + LLM
        if rating_val <= 3:
            # Best text for display: disadvantages > fb_text > advantages
            display_text = disadvantages or fb_text or advantages or ""
            if display_text.strip():
                negative_review_samples.append({
                    "variant": variant,
                    "text": display_text.strip()[:200],
                    "rating": int(rating_val),
                    "date": (f.get("fb_created_at") or "")[:10],
                })

            # LLM: full combined text for classification
            if use_llm:
                combined_parts = []
                if disadvantages:
                    combined_parts.append(disadvantages)
                if advantages:
                    combined_parts.append(advantages)
                if fb_text:
                    combined_parts.append(fb_text)
                combined_text = " ".join(combined_parts).strip()
                if combined_text:
                    negative_texts_for_llm.append({
                        "variant": variant,
                        "text": combined_text,
                    })

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

    # Автовыбор варианта: худший по рейтингу (если стат. значимо)
    if target_variant is None or target_variant not in variant_stats:
        if valid_colors:
            candidates = [v for v in valid_colors if variant_stats[v]["count"] >= MIN_REVIEWS_FOR_SIGNAL]
            if candidates:
                # Average of all candidates (weighted)
                all_sum = sum(variant_stats[v]["sum"] for v in candidates)
                all_cnt = sum(variant_stats[v]["count"] for v in candidates)
                overall_avg = all_sum / all_cnt if all_cnt else 0
                # Find worst variant that's significantly below others
                worst = min(candidates, key=lambda k: avg(variant_stats[k]))
                worst_avg = avg(variant_stats[worst])
                others = [v for v in candidates if v != worst]
                if others:
                    others_sum = sum(variant_stats[v]["sum"] for v in others)
                    others_cnt = sum(variant_stats[v]["count"] for v in others)
                    others_avg = others_sum / others_cnt if others_cnt else 0
                else:
                    others_avg = overall_avg
                gap = round(others_avg - worst_avg, 1)
                if gap >= MIN_GAP_FOR_SIGNAL:
                    target_variant = worst
                else:
                    # No significant gap — pick variant with most reviews for general report
                    target_variant = max(candidates, key=lambda k: variant_stats[k]["count"])
            else:
                target_variant = max(valid_colors, key=lambda k: variant_stats[k]["count"])
        else:
            target_variant = "Один товар"
    elif target_variant not in valid_colors and valid_colors:
        target_variant = max(valid_colors, key=lambda k: variant_stats[k]["count"])

    target_stats = variant_stats.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})
    target_avg = avg(target_stats)

    # Тренд: сравнение текущего периода с предыдущим
    # First try 30-day windows; if insufficient data — split all data in half by date
    target_recent = variant_recent.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})
    target_prev = variant_prev.get(target_variant or "Один товар", {"count": 0, "sum": 0.0})

    trend = None
    trend_delta = 0
    MIN_TREND_REVIEWS = 3
    if target_recent["count"] >= MIN_TREND_REVIEWS and target_prev["count"] >= MIN_TREND_REVIEWS:
        trend_delta = round(avg(target_recent) - avg(target_prev), 2)
    else:
        # Fallback: split target variant's feedbacks into older half / newer half
        target_dates_ratings = []
        for fb in feedbacks:
            if has_multiple_articles:
                art = fb.get("article", "")
                v = article_display.get(art, art) if art else "Один товар"
            else:
                v_raw = fb.get("color") or fb.get("size") or "Остальные"
                v = normalize_variant(v_raw.strip()) if is_color_variant(v_raw.strip()) else "Один товар"
            if v != (target_variant or "Один товар"):
                continue
            dt = parse_date(fb.get("fb_created_at") or "")
            r = float(fb.get("valuation") or 0)
            if dt and r > 0:
                target_dates_ratings.append((dt, r))
        target_dates_ratings.sort(key=lambda x: x[0])
        n = len(target_dates_ratings)
        if n >= MIN_TREND_REVIEWS * 2:
            mid = n // 2
            older = target_dates_ratings[:mid]
            newer = target_dates_ratings[mid:]
            older_avg = sum(r for _, r in older) / len(older)
            newer_avg = sum(r for _, r in newer) / len(newer)
            trend_delta = round(newer_avg - older_avg, 2)

    if trend_delta != 0 or (target_recent["count"] >= MIN_TREND_REVIEWS and target_prev["count"] >= MIN_TREND_REVIEWS):
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

    # --- LLM classification (replaces rule-based if available) ---
    llm_reason_counts = None
    if use_llm and negative_texts_for_llm:
        target_negative = [
            {"index": i, "text": t["text"]}
            for i, t in enumerate(negative_texts_for_llm)
            if t["variant"] == target_variant or target_variant == "Один товар"
        ]
        if target_negative:
            print(f"LLM classify: {len(target_negative)} negative reviews for variant '{target_variant}'")
            reason_defs = {k: {"label": v["label"], "emoji": v["emoji"]} for k, v in REASONS.items()}
            llm_reason_counts = llm_classify_reasons(target_negative, category, reason_defs)
            if llm_reason_counts is not None:
                print(f"LLM classify: OK — {llm_reason_counts}")
            else:
                print(f"LLM classify: failed, using rule-based fallback")

    # Build reason_rows from LLM or rule-based
    if llm_reason_counts is not None:
        reason_counts_final = llm_reason_counts
        reason_total = sum(reason_counts_final.values()) or 0
    else:
        reason_counts_final = dict(reason_counts.most_common()) if reason_counts else {}
        reason_total = sum(reason_counts_final.values()) or 0

    reason_rows = []
    if reason_total:
        sorted_reasons = sorted(reason_counts_final.items(), key=lambda x: x[1], reverse=True)
        for key, cnt in sorted_reasons:
            if key == "other":
                label = "Прочее"
                emoji = "❓"
            elif key in REASONS:
                label = REASONS[key]["label"]
                emoji = REASONS[key]["emoji"]
            else:
                # LLM might return a key not in REASONS — use it as-is
                label = key
                emoji = "❓"
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

    data_window = f"{WINDOW_DAYS} дней" if use_recent else "12 месяцев"

    # Check if there's a statistically significant signal
    has_signal = False
    if target_variant and target_variant != "Один товар":
        others_for_gap = [v for v in valid_colors if v != target_variant and variant_stats[v]["count"] >= MIN_REVIEWS_FOR_SIGNAL]
        if others_for_gap and target_stats["count"] >= MIN_REVIEWS_FOR_SIGNAL:
            others_sum = sum(variant_stats[v]["sum"] for v in others_for_gap)
            others_cnt = sum(variant_stats[v]["count"] for v in others_for_gap)
            others_avg_val = others_sum / others_cnt if others_cnt else 0
            gap = round(others_avg_val - target_avg, 1)
            has_signal = gap >= MIN_GAP_FOR_SIGNAL

    main_reason = None
    if reason_rows:
        main_reason = reason_rows[0]["label"]

    if has_signal:
        signal_title = f"⚠ Проблема в варианте: {target_variant}"
        summary_lines = [
            f"Рейтинг {target_avg} — на {round(gap, 2)} ниже остальных вариантов",
        ]
        if main_reason:
            summary_lines.append(f"Причина: {main_reason}")
        summary_lines.append("Риск падения рейтинга карточки")
        signal_summary = "\n".join(summary_lines)
    elif target_variant and target_variant != "Один товар":
        signal_title = "✓ Варианты в норме"
        signal_summary = f"Разница между вариантами незначительна (менее {MIN_GAP_FOR_SIGNAL})"
    else:
        signal_title = "⚠ Проблема в товаре"
        signal_summary = "Повторяющаяся причина, не случайность"

    # Подсчёт негативных отзывов и неотвеченных
    negative_count = sum(1 for f in feedbacks if float(f.get("valuation") or 0) <= 3)
    unanswered_count = sum(1 for f in feedbacks if not (f.get("answer_text") or "").strip())
    neg_rate = negative_count / max(total, 1)

    # Динамические риски
    risk_items = []
    if neg_rate > 0.15:
        risk_items.append(f"Высокий уровень негатива: {round(neg_rate * 100)}% отзывов с оценкой 1-3")
    elif neg_rate > 0.08:
        risk_items.append(f"Повышенный уровень негатива: {round(neg_rate * 100)}% отзывов с оценкой 1-3")
    else:
        risk_items.append(f"Уровень негатива в норме: {round(neg_rate * 100)}% отзывов с оценкой 1-3")

    if target_avg < 4.0 and target_variant and target_variant != "Один товар":
        risk_items.append(f"Рейтинг варианта «{target_variant}» критически низкий: {target_avg}")
    elif target_avg < 4.5 and target_variant and target_variant != "Один товар":
        risk_items.append(f"Рейтинг варианта «{target_variant}» ниже среднего: {target_avg}")

    if trend == "down":
        risk_items.append(f"Тренд ухудшается: {trend_delta} за последние {WINDOW_DAYS} дней")

    if unanswered_count > 0:
        unanswered_pct = round(unanswered_count / max(total, 1) * 100)
        risk_items.append(f"{unanswered_count} отзывов без ответа ({unanswered_pct}%)")

    if not risk_items:
        risk_items.append("Серьёзных рисков не обнаружено")

    # Категорийно-зависимые тексты
    category_labels = {
        "flashlight": {"type": "варианту", "item": "варианта"},
        "clothing": {"type": "варианту", "item": "варианта"},
        "electronics": {"type": "варианту", "item": "варианта"},
        "pet_food": {"type": "товару", "item": "товара"},
    }
    cat_label = category_labels.get(category, {"type": "варианту", "item": "варианта"})

    # --- Deep analysis: root cause + strategy + actions + reply ---
    deep = None
    if use_llm and target_variant and target_variant != "Один товар" and reason_rows:
        try:
            review_samples = [
                t["text"][:300] for t in negative_texts_for_llm
                if t["variant"] == target_variant
            ][:10]
            other_vars = [
                {"name": v, "rating": round(avg(variant_stats[v]), 2), "count": variant_stats[v]["count"]}
                for v in valid_colors
                if v != target_variant and variant_stats[v]["count"] >= MIN_REVIEWS_FOR_SIGNAL
            ]
            # Build card description for LLM context
            card_description = None
            if wb_card:
                card_description = wb_card.get("description", "")
                if wb_card.get("options"):
                    card_description += "\nХарактеристики: " + wb_card["options"]

            deep = llm_deep_analysis(
                product_name=product_name or (wb_card or {}).get("imt_name", ""),
                category=category,
                target_variant=target_variant,
                target_rating=target_avg,
                target_count=target_stats["count"],
                other_variants=other_vars,
                reason_rows=reason_rows,
                review_samples=review_samples,
                card_description=card_description,
                questions=questions,
            )
            if deep:
                print(f"LLM deep_analysis: OK — type={deep['root_cause'].get('type')}, strategy={deep['strategy'].get('title')}")
            else:
                print("LLM deep_analysis: returned None, using separate LLM calls")
        except Exception as e:
            print(f"LLM deep_analysis: error {e}, using separate LLM calls")

    # Build actions and reply from deep analysis or fallback
    if deep:
        actions_items = deep.get("actions", [])[:3]
        reply_text = deep.get("reply", "")
        risk_explanation = deep.get("root_cause", {}).get("explanation", risk_items)
        risk_conclusion = deep.get("root_cause", {}).get("conclusion")
        strategy_title = deep.get("strategy", {}).get("title")
        actions_desc = deep.get("strategy", {}).get("description")
    else:
        actions_items = _get_actions_with_fallback(use_llm, category, target_variant, reason_rows)
        reply_text = _get_reply_with_fallback(use_llm, category, main_reason, product_name, target_variant)
        risk_explanation = risk_items
        risk_conclusion = None
        strategy_title = None
        actions_desc = None

    # --- Response speed calculation (from data, not LLM) ---
    response_times_all = []
    response_times_neg = []
    for f in feedbacks:
        fb_dt = parse_date(f.get("fb_created_at") or "")
        ans_dt = parse_date(f.get("answer_created_at") or "")
        if fb_dt and ans_dt and ans_dt > fb_dt:
            delta_hours = (ans_dt - fb_dt).total_seconds() / 3600
            response_times_all.append(delta_hours)
            rating = int(f.get("valuation") or 0)
            if rating <= 3:
                response_times_neg.append(delta_hours)

    response_speed = None
    if response_times_all:
        sorted_all = sorted(response_times_all)
        sorted_neg = sorted(response_times_neg) if response_times_neg else []
        response_speed = {
            "all_median_hours": round(sorted_all[len(sorted_all) // 2], 1),
            "all_avg_hours": round(sum(sorted_all) / len(sorted_all), 1),
            "all_count": len(sorted_all),
            "neg_median_hours": round(sorted_neg[len(sorted_neg) // 2], 1) if sorted_neg else None,
            "neg_avg_hours": round(sum(sorted_neg) / len(sorted_neg), 1) if sorted_neg else None,
            "neg_count": len(sorted_neg),
            "max_hours": round(max(sorted_all), 1),
            "same_day_count": sum(1 for h in sorted_all if h < 24),
            "slow_count": sum(1 for h in sorted_all if h >= 24 * 7),
        }
        print(f"[Response speed] all median: {response_speed['all_median_hours']}h, "
              f"neg median: {response_speed['neg_median_hours']}h, "
              f"max: {response_speed['max_hours']}h")

    # --- Communication quality analysis ---
    communication = None
    if use_llm:
        try:
            communication = llm_analyze_communication(
                feedbacks=feedbacks,
                product_name=product_name or (wb_card or {}).get("imt_name", ""),
            )
            if communication:
                print(f"[Communication] OK — quality_score: {communication['quality_score']}/10, "
                      f"verdict: {(communication.get('verdict') or '')[:80]}")
            else:
                print("[Communication] LLM returned None")
        except Exception as e:
            print(f"[Communication] error: {e}")

    # --- Money loss estimation ---
    money_loss = None
    # Use average price from CDN price history (more accurate), fall back to card price
    card_price = (wb_card or {}).get("price")
    price = card_price
    avg_price_3m = None
    if nm_id:
        price_history = fetch_wb_price_history(nm_id)
        avg_price_3m = avg_price_from_history(price_history, months=3)
        if avg_price_3m:
            print(f"[Money loss] Using avg price from history: {avg_price_3m}₽ (card price: {card_price}₽)")
            price = avg_price_3m
    if communication and price:
        # Calculate period in months
        dates = [parse_date(f.get("fb_created_at") or "") for f in feedbacks]
        dates = [d for d in dates if d]
        if dates:
            period_days = (max(dates) - min(dates)).days
            period_months = max(1, round(period_days / 30))

            quality_score = communication.get("quality_score", 5)
            money_loss = calculate_money_loss(
                review_count=len(feedbacks),
                period_months=period_months,
                price_rub=price,
                quality_score=quality_score
            )
            if money_loss:
                if card_price:
                    money_loss["card_price"] = round(card_price)
                if avg_price_3m:
                    money_loss["avg_price_3m"] = round(avg_price_3m)
                print(f"[Money loss] Est. loss: {money_loss['loss_per_month_min']:,} - "
                      f"{money_loss['loss_per_month_max']:,}₽/мес "
                      f"(price: {price}₽, period: {period_months}мес, {len(feedbacks)} reviews)")
            else:
                print("[Money loss] Calculation skipped (no price)")
        else:
            print("[Money loss] Calculation skipped (no dates)")

    result = {
        "header": {
            "title": f"Артикул {article or ''} · Риск по {cat_label['type']}",
            "subtitle": f"WB · {len(feedbacks)} отзывов · рейтинг {rating} · данные за {data_window}",
            "rating": rating,
            "feedback_count": len(feedbacks),
            "analyzed_count": len(feedbacks),
            "unanswered_count": unanswered_count,
            "category": category,
            "product_name": product_name or (wb_card or {}).get("imt_name", ""),
        },
        "signal": {
            "title": signal_title,
            "summary": signal_summary,
            "scores": sorted(
                [
                    {
                        "label": v,
                        "value": avg(variant_stats[v]),
                        "count": variant_stats[v]["count"],
                        "is_target": v == target_variant,
                        "trend": trend if v == target_variant else None,
                        "trend_delta": trend_delta if v == target_variant else None,
                    }
                    for v in valid_colors
                    if variant_stats[v]["count"] >= MIN_REVIEWS_FOR_SIGNAL
                ],
                key=lambda x: x["value"],
            ),
            "meta": f"{target_stats['count']} отзывов, доверие: {'высокое' if target_stats['count'] >= 20 else 'среднее' if target_stats['count'] >= 10 else 'низкое'}",
            "trend_info": f"За {WINDOW_DAYS} дн: {'+' if trend_delta > 0 else ''}{trend_delta}" if trend else None,
        },
        "reasons": {
            "title": f"Почему именно этот {cat_label['type'].replace('у', '')} проседает" if target_variant and target_variant != "Один товар" else "Причины негативных отзывов",
            "items": reason_rows,
            "reviews": [
                r for r in negative_review_samples
                if r["variant"] == target_variant or target_variant == "Один товар"
            ][:5],
            "cta": f"Показать отзывы ({target_stats['count']})",
        },
        "compare": {
            "title": "Это аномалия или норма",
            "rows": compare_rows,
            "conclusion": f"Проблема специфична для варианта «{target_variant}»" if target_variant and target_variant != "Один товар" else "Проблема относится ко всему товару",
        },
        "risk": {
            "title": "Выводы",
            "items": risk_explanation,
            "conclusion": risk_conclusion,
            "note": f"Расчёт на основе {total} отзывов за {data_window}",
        },
        "actions": {
            "title": "Что делать",
            "strategy": strategy_title,
            "description": actions_desc,
            "items": actions_items,
            "status": "⏳ Под наблюдением, пересчет сигнала через 7 дней",
        },
        "reply": {
            "title": "Черновик ответа (авто)",
            "text": reply_text,
            "note": "Ответ не снижает проблему, но снижает повторный негатив.",
        },
        "questions": {
            "count": len(questions),
            "unanswered_count": sum(1 for q in questions if not q.get("answer_text")),
            "samples": [
                {"text": q["qs_text"][:200], "answered": bool(q.get("answer_text"))}
                for q in questions[:5]
            ],
        },
        "response_speed": response_speed,
        "communication": communication,
        "money_loss": money_loss,
        "price": price,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
