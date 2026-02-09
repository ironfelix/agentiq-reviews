#!/usr/bin/env python3
"""
Генерирует chat-center-real-data.html из полных данных WB Chat API.

Вход: /tmp/wb_chats_full.json (результат fetch_wb_chats_full.py)
Шаблон: docs/mvp-chat/chat-center-real-data.html (CSS + JS структура)
Выход: обновлённый docs/mvp-chat/chat-center-real-data.html

Правила сниппетов:
  Мета-строка: [dot] Чат · [Арт. NNN / Товар] · [Статус]
  Статусы: Ожидает ответа | Клиент ответил | Отвечено | Авто-ответ
  Секции: В работе → Ожидают ответа → Все сообщения
"""

import json
import re
import os
from collections import Counter
from datetime import datetime, timezone

# === PATHS ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_FILE = "/tmp/wb_chats_full.json"
TEMPLATE_FILE = os.path.join(PROJECT_ROOT, "docs", "mvp-chat", "chat-center-real-data.html")
OUTPUT_FILE = TEMPLATE_FILE  # overwrite

# === LOAD DATA ===
with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

chats = data["chats"]
print(f"Loaded {len(chats)} chats, {data['total_messages']} messages")


# ============================================================
# STEP 1: AUTO-TEMPLATE DETECTION
# ============================================================
AUTO_TEMPLATE_SUBSTR = 'задать вопросы по возврату товара'

def is_auto_template(text):
    """Check if a message is WB's auto-generated return template."""
    return AUTO_TEMPLATE_SUBSTR in text

def has_real_seller_response(messages):
    """Check if there's at least one non-auto-template seller message."""
    for m in messages:
        if m.get("sender") == "seller" and not is_auto_template(m.get("text", "")):
            return True
    return False

def has_only_auto_seller_messages(messages):
    """Check if ALL seller messages in this chat are auto-templates."""
    seller_msgs = [m for m in messages if m.get("sender") == "seller"]
    if not seller_msgs:
        return False
    return all(is_auto_template(m.get("text", "")) for m in seller_msgs)


# ============================================================
# STEP 2: MULTI-LAYER PRODUCT DETECTION
# ============================================================
# Layer 1: Explicit "артикул NNNN"
ARTICLE_RE = re.compile(r'артикул\s+(\d{6,12})', re.IGNORECASE)

# Layer 2: Product name in quotes after "товар"
PRODUCT_NAME_RE = re.compile(r'товар[уе]?\s+"([^"]+)"', re.IGNORECASE)

# Layer 3: Product type keywords (Zegor plumbing products)
# Map stems → normalized display names
PRODUCT_KEYWORD_MAP = {
    'кран': 'Кран',
    'насос': 'Насос',
    'вентиль': 'Вентиль',
    'реле': 'Реле',
    'гофра': 'Гофра',
    'сифон': 'Сифон',
    'манометр': 'Манометр',
    'расходомер': 'Расходомер',
    'коллектор': 'Коллектор',
    'смесител': 'Смеситель',
    'шланг': 'Шланг',
}
PRODUCT_KEYWORD_RE = re.compile(
    r'\b(' + '|'.join(PRODUCT_KEYWORD_MAP.keys()) + r')\w*',
    re.IGNORECASE
)

def extract_article(messages):
    """Layer 1: Extract product article number from message text."""
    for m in messages:
        match = ARTICLE_RE.search(m.get("text", ""))
        if match:
            return match.group(1)
    return None

def extract_product_name(messages):
    """Layer 2+3: Extract product name (quoted or keyword-based)."""
    # Layer 2: Quoted name after "товар"
    for m in messages:
        match = PRODUCT_NAME_RE.search(m.get("text", ""))
        if match:
            return match.group(1)

    # Layer 3: Keyword detection (only in client messages)
    client_text = " ".join(
        m.get("text", "") for m in messages if m.get("sender") == "client"
    )
    match = PRODUCT_KEYWORD_RE.search(client_text)
    if match:
        stem = match.group(1).lower()
        return PRODUCT_KEYWORD_MAP.get(stem, stem.capitalize())

    return None


# ============================================================
# STEP 3: STATUS DETECTION (4 statuses)
# ============================================================
def get_chat_status(chat):
    """
    Determine chat status based on message flow analysis.

    Statuses:
      waiting        — client waiting, seller never responded (or only auto)
      client-replied — seller responded, client replied back
      responded      — seller responded, client silent
      auto-response  — only auto-template seller messages
    """
    msgs = chat.get("messages", [])
    if not msgs:
        return "Нет сообщений", "waiting"

    last_sender = msgs[-1].get("sender", "")
    seller_responded = has_real_seller_response(msgs)
    auto_only = has_only_auto_seller_messages(msgs)

    # Client sent last + seller responded before → client replied back
    if last_sender == "client" and seller_responded:
        return "Клиент ответил", "client-replied"

    # Client sent last + no real seller response → waiting
    if last_sender == "client" and not seller_responded:
        return "Ожидает ответа", "waiting"

    # Last from seller, but only auto-template
    if last_sender == "seller" and auto_only:
        return "Авто-ответ", "auto-response"

    # Last from seller (real response)
    if last_sender == "seller":
        return "Отвечено", "responded"

    return "Ожидает ответа", "waiting"


# ============================================================
# HELPERS: dates, formatting
# ============================================================
MONTHS_RU = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
    5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
    9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}

def format_date_ru(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return f"{dt.day} {MONTHS_RU[dt.month]} {dt.year} г."

def format_time(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return f"{dt.hour:02d}:{dt.minute:02d}"

def format_date_short(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return f"{dt.day:02d}.{dt.month:02d}"

def format_date_long(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return f"{dt.day} {MONTHS_RU[dt.month]} {dt.year} г., {dt.hour:02d}:{dt.minute:02d}"

def get_date_key(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")

def js_escape(s):
    return (s
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
            .replace('"', '\\"'))


# ============================================================
# STEP 5 (partial): BUILD CHAT HISTORY WITH AUTO-TEMPLATE TAGS
# ============================================================
def build_chat_history(messages):
    """Convert API messages to chatHistory entries with date separators."""
    history = []
    current_date = None

    for m in messages:
        add_time = m.get("addTime", "")
        if not add_time:
            continue

        date_key = get_date_key(add_time)
        if date_key != current_date:
            current_date = date_key
            history.append({"type": "date", "text": format_date_ru(add_time)})

        sender = m.get("sender", "client")
        client_name = m.get("clientName", "") or "Клиент"
        text = m.get("text", "")

        # Tag auto-template seller messages
        if sender == "seller" and is_auto_template(text):
            author = "Продавец [авто]"
        elif sender == "seller":
            author = "Продавец"
        else:
            author = client_name

        history.append({
            "type": "seller" if sender == "seller" else "customer",
            "author": author,
            "time": format_time(add_time),
            "text": text
        })

    return history


# ============================================================
# RISK DETECTION + PRIORITY
# ============================================================
RISK_KEYWORDS = [
    'брак', 'сломан', 'обман', 'плохо', 'ужас', 'не работ',
    'отказ', 'кошмар', 'разочарован', 'верните деньги', 'жалоб',
    'не тот', 'не те', 'не та', 'пришёл другой', 'пришел другой',
]

def detect_risk(chat):
    """Detect if chat is high-risk (urgent or negative)."""
    if chat.get("unread_count", 0) >= 5:
        return "high"
    client_text = " ".join(
        m.get("text", "").lower()
        for m in chat.get("messages", [])
        if m.get("sender") == "client"
    )
    if any(kw in client_text for kw in RISK_KEYWORDS):
        return "high"
    return "normal"

def get_priority(chat):
    """Priority uses risk_level (must be computed first via detect_risk).
    urgent = high risk (unread >= 5 OR risk keywords)
    waiting = has unread messages but not high risk
    normal = no unread
    """
    if chat.get("risk_level") == "high":
        return "urgent"
    if chat.get("unread_count", 0) > 0:
        return "waiting"
    return "normal"


# ============================================================
# ENRICH CHATS
# ============================================================
print("\nProcessing chats...")

for chat in chats:
    msgs = chat.get("messages", [])
    chat["article"] = extract_article(msgs)
    chat["product_name"] = extract_product_name(msgs)
    chat["risk_level"] = detect_risk(chat)  # must be before get_priority
    chat["priority"] = get_priority(chat)
    chat["status_label"], chat["status_class"] = get_chat_status(chat)
    chat["chat_history"] = build_chat_history(msgs)
    chat["has_auto_template"] = any(
        is_auto_template(m.get("text", ""))
        for m in msgs if m.get("sender") == "seller"
    )

    product_info = ""
    if chat["article"]:
        product_info = f" (арт. {chat['article']})"
    elif chat["product_name"]:
        product_info = f" ({chat['product_name']})"
    print(f"  {chat['client_name']}: {chat['status_label']}{product_info}")


# ============================================================
# STEP 4: 3-SECTION SORTING
# ============================================================
def sort_key(c):
    msgs = c.get("messages", [])
    return msgs[-1].get("addTimestamp", 0) if msgs else 0

# Section 1: В работе (urgent: unread >= 5)
urgent = [c for c in chats if c["priority"] == "urgent"]
urgent.sort(key=sort_key, reverse=True)

# Section 2: Ожидают ответа (waiting + client-replied, not urgent)
awaiting = [c for c in chats
            if c["priority"] != "urgent"
            and c["status_class"] in ("waiting", "client-replied")]
awaiting.sort(key=sort_key, reverse=True)

# Section 3: Все сообщения (responded + auto-response)
urgent_ids = {c["chat_id"] for c in urgent}
awaiting_ids = {c["chat_id"] for c in awaiting}
rest = [c for c in chats if c["chat_id"] not in urgent_ids and c["chat_id"] not in awaiting_ids]
rest.sort(key=sort_key, reverse=True)

print(f"\n  В работе: {len(urgent)}")
print(f"  Ожидают ответа: {len(awaiting)}")
print(f"  Все сообщения: {len(rest)}")
print(f"  Итого: {len(chats)}")

# Assign numeric IDs
all_chats_ordered = urgent + awaiting + rest
for i, c in enumerate(all_chats_ordered, 1):
    c["num_id"] = str(i)


# ============================================================
# GENERATE CHAT LIST HTML (with meta format: Чат · товар · статус)
# ============================================================
def generate_chat_item_html(chat, is_active=False):
    classes = ["chat-item"]
    if chat["priority"] == "urgent":
        classes.append("urgent")
    elif chat["status_class"] in ("waiting", "client-replied"):
        classes.append("waiting")
    if is_active:
        classes.append("active")

    unread = chat.get("unread_count", 0)
    name = chat.get("client_name", "Клиент") or "Клиент"
    last_msg = chat.get("messages", [])[-1] if chat.get("messages") else None
    time_str = format_date_short(last_msg["addTime"]) if last_msg else ""

    # Preview text
    last_text = chat.get("last_text", "")
    if chat.get("last_sender") == "seller":
        preview_text = f"Вы: {last_text}" if last_text else "(нет сообщения)"
    else:
        preview_text = last_text if last_text else "(нет сообщения)"
    if len(preview_text) > 75:
        preview_text = preview_text[:72] + "..."

    # Meta line: Чат · [Арт. NNN / Товар] · Статус
    meta_parts = ["Чат"]
    if chat.get("article"):
        meta_parts.append(f"Арт. {chat['article']}")
    elif chat.get("product_name"):
        meta_parts.append(chat["product_name"])
    meta_parts.append(chat["status_label"])
    meta_text = " · ".join(meta_parts)

    dot_classes = chat["status_class"]
    if chat.get("risk_level") == "high":
        dot_classes += " risk"
    status_html = f'<span class="status-dot {dot_classes}"></span>{meta_text}'
    badge_html = f'<span class="unread-badge">{unread}</span>' if unread > 0 else ""

    return f'''                    <div class="{' '.join(classes)}" draggable="true" data-chat-id="{chat['num_id']}" data-status="{chat['status_class']}">
                        <div class="marketplace-icon wb">W</div>
                        <div class="chat-item-content">
                            <div class="chat-item-header">
                                <span class="chat-item-name">{name}</span>
                                {badge_html}
                                <span class="chat-item-time">{time_str}</span>
                            </div>
                            <div class="chat-item-meta">{status_html}</div>
                            <div class="chat-item-preview">{preview_text}</div>
                        </div>
                    </div>'''


# ============================================================
# GENERATE contextData JS
# ============================================================
def generate_ai_suggestion(chat):
    """Analyze FULL chat history and suggest a specific seller response.

    Reads all client messages, detects the specific question/problem,
    and generates a ready-to-send response text.
    """
    name = chat.get("client_name", "Клиент") or "Клиент"
    status = chat.get("status_label", "")
    cats = detect_categories(chat)
    article = chat.get("article", "")
    product = chat.get("product_name", "")
    msgs = chat.get("messages", [])
    client_msgs = [m.get("text", "") for m in msgs if m.get("sender") == "client"]
    all_client_text = " ".join(client_msgs).lower()
    last_client_text = client_msgs[-1].lower() if client_msgs else ""

    product_ref = ""
    if article:
        product_ref = f" (арт. {article})"
    elif product:
        product_ref = f" ({product})"

    # --- Responded: chat is handled ---
    if status == "Отвечено":
        if "спасибо" in all_client_text:
            return "Чат завершён позитивно. Мониторинг."
        return "Чат обработан. Мониторинг."

    # --- Auto-response: only WB template sent ---
    if status == "Авто-ответ":
        # Check if client actually asked something
        if client_msgs:
            return f"{name}, здравствуйте! Видим ваше обращение{product_ref}. Подскажите, пожалуйста, чем можем помочь?"
        return f"{name}, здравствуйте! Подскажите, какой у вас вопрос{product_ref}?"

    # --- Client replied: seller answered, client wrote again ---
    if status == "Клиент ответил":
        if "спасибо" in last_client_text:
            return f"Рады помочь, {name}! Если возникнут ещё вопросы — обращайтесь."
        if "доставил" in last_client_text or "получил" in last_client_text or "привез" in last_client_text:
            return f"Отлично, {name}! Рады, что товар{product_ref} доставлен. Если всё в порядке — будем благодарны за положительный отзыв!"
        return f"Просмотрите ответ {name} и продолжите диалог."

    # --- Waiting: analyze what client specifically asks ---
    # Guardrails: готовый текст от лица продавца, без banned phrases
    # Banned: "обратитесь в поддержку", "мы не можем", "вернём деньги"
    # Структура: эмпатия → конкретика → открытый диалог

    # Check if client mentioned return/exchange
    client_wants_return = any(w in all_client_text for w in [
        "возврат", "вернуть", "замен", "обмен", "поменять"
    ])

    # 1. Wrong product delivered
    if "Ошибочный заказ" in cats or "не заказ" in all_client_text:
        return f"{name}, здравствуйте! Нам жаль, что произошла ошибка. Оформите, пожалуйста, возврат через ЛК WB — мы одобрим заявку."

    # 2. Wrong variant (size, type, etc.)
    if "Не подошёл товар" in cats:
        if client_wants_return:
            return f"{name}, здравствуйте! Приносим извинения за несоответствие{product_ref}. Оформите возврат через ЛК WB — мы одобрим. Правильный вариант можно заказать повторно."
        return f"{name}, здравствуйте! Приносим извинения за несоответствие{product_ref}. Подскажите, пожалуйста, подробнее — поможем разобраться."

    # 3. Defect / broken
    if "Брак / дефект" in cats:
        return f"{name}, здравствуйте! Нам очень жаль — это нештатная ситуация. Оформите возврат через ЛК WB, мы его одобрим. Информацию передали в отдел качества."

    # 4. Delivery — без "обратитесь в поддержку", без "мы не можем повлиять"
    if "Доставка" in cats:
        if "перезаказ" in all_client_text or "может перезаказать" in all_client_text:
            return f"{name}, здравствуйте! Рекомендуем подождать ещё 2-3 дня — иногда доставка задерживается на стороне логистики. Если товар не поступит, можно отменить заказ в ЛК WB и оформить новый. Мы на связи!"
        if "ждать" in all_client_text:
            return f"{name}, здравствуйте! Со своей стороны проверили — товар{product_ref} передан в службу доставки. Иногда сроки увеличиваются на стороне логистики. Если заказ не поступит в ближайшие дни — напишите нам, поможем разобраться."
        if "задерж" in all_client_text or "опазд" in all_client_text:
            return f"{name}, здравствуйте! Понимаем, что задержка — это неприятно. Со своей стороны мы проверили — товар отгружен. Иногда логистика задерживает доставку. Если заказ не поступит в течение 3-5 дней — напишите нам."
        if "где товар" in all_client_text or "где заказ" in all_client_text:
            return f"{name}, здравствуйте! Со своей стороны проверили — товар передан в доставку. Статус можно отследить в ЛК WB. Если нужна помощь — пишите!"
        if "отказ" in all_client_text or "вынужден отказ" in all_client_text:
            return f"{name}, здравствуйте! Понимаем ваше разочарование. Вы можете отменить заказ в ЛК WB. Приносим извинения за неудобства."
        return f"{name}, здравствуйте! Со своей стороны проверили — товар{product_ref} передан в доставку. Если возникнут вопросы — пишите, поможем разобраться."

    # 5. Return request (only if client mentioned it)
    if "Возврат" in cats and client_wants_return:
        return f"{name}, здравствуйте! Для возврата товара{product_ref} оформите заявку в ЛК WB. Мы одобрим. Если нужна помощь — пишите!"

    # 6. Product usage help
    if "Помощь с использованием" in cats:
        return f"{name}, здравствуйте! Готовы помочь с товаром{product_ref}. Подскажите, что именно вас интересует — подберём решение."

    # 7. Has a specific question
    if "?" in " ".join(client_msgs):
        return f"{name}, здравствуйте! Спасибо за обращение{product_ref}. Рассмотрим ваш вопрос и ответим в ближайшее время."

    return f"{name}, здравствуйте! Спасибо за обращение{product_ref}. Подскажите, чем можем помочь?"

def detect_categories(chat):
    all_text = " ".join(m.get("text", "").lower() for m in chat.get("messages", []))
    cats = []
    if any(w in all_text for w in ["доставк", "привез", "когда", "ждать", "ждат", "жду",
                                     "перезаказ", "сколько ждать", "задерж", "не доставл"]):
        cats.append("Доставка")
    if "возврат" in all_text:
        cats.append("Возврат")
    if "артикул" in all_text or "товар" in all_text:
        cats.append("Вопрос о товаре")
    if any(w in all_text for w in ["брак", "дефект", "сломан", "не работ", "гремит", "течёт", "течет"]):
        cats.append("Брак / дефект")
    if "спасибо" in all_text or "благодар" in all_text:
        cats.append("Благодарность")
    if "не заказ" in all_text:
        cats.append("Ошибочный заказ")
    if any(w in all_text for w in ["не подош", "не подходи", "не те ", "не тот", "не та ", "другой размер", "другого размер"]):
        cats.append("Не подошёл товар")
    if "отмен" in all_text:
        cats.append("Отмена заказа")
    if "гарант" in all_text:
        cats.append("Гарантия")
    if any(w in all_text for w in ["промы", "как использ", "как подключ", "инструкц"]):
        cats.append("Помощь с использованием")
    if not cats:
        cats.append("Общий вопрос")
    return cats

def detect_sentiment(chat):
    all_text = " ".join(m.get("text", "").lower() for m in chat.get("messages", []))
    if any(w in all_text for w in ["спасибо", "благодар", "отлично", "супер", "хорош"]):
        return ("Позитивная", "false")
    if any(w in all_text for w in ["брак", "плохо", "ужас", "обман", "не работ", "сломан"]):
        return ("Негативная", "true")
    return ("Нейтральная", "false")

def generate_recommendation(chat):
    status = chat.get("status_label", "")
    cats = detect_categories(chat)
    risk = chat.get("risk_level", "normal")

    if status == "Отвечено":
        return "Мониторинг"
    if status == "Авто-ответ":
        return "Написать реальный ответ"
    if status == "Клиент ответил":
        return "Просмотреть ответ клиента"

    # Waiting
    if risk == "high":
        return "Ответить срочно"
    if "Возврат" in cats or "Брак / дефект" in cats:
        return "Одобрить возврат + ответить"
    if "Не подошёл товар" in cats:
        return "Уточнить проблему + предложить решение"
    if "Доставка" in cats:
        return "Проверить статус + ответить"
    return "Ответить клиенту"


def generate_context_data_js(chats_list):
    entries = []
    for chat in chats_list:
        name = chat.get("client_name", "Клиент") or "Клиент"
        unread = chat.get("unread_count", 0)
        last_msg = chat.get("messages", [])[-1] if chat.get("messages") else None
        last_time_str = format_date_long(last_msg["addTime"]) if last_msg else ""

        # Product
        if chat.get("article"):
            product_js = f"{{ name: '{js_escape(chat.get('product_name') or '')}', article: '{chat['article']}' }}"
        elif chat.get("product_name"):
            product_js = f"{{ name: '{js_escape(chat['product_name'])}', article: null }}"
        else:
            product_js = "null"

        # Chat history
        history_items = []
        for item in chat["chat_history"]:
            if item["type"] == "date":
                history_items.append(f"                        {{ type: 'date', text: '{js_escape(item['text'])}' }}")
            else:
                author = js_escape(item.get("author", ""))
                time_val = item.get("time", "")
                text = js_escape(item.get("text", ""))
                history_items.append(f"                        {{ type: '{item['type']}', author: '{author}', time: '{time_val}', text: '{text}' }}")
        history_js = ",\n".join(history_items)

        ai_suggestion = generate_ai_suggestion(chat)
        categories = detect_categories(chat)
        categories_js = "[" + ", ".join(f"'{c}'" for c in categories) + "]"
        sentiment = detect_sentiment(chat)

        risk = chat.get("risk_level", "normal")
        if risk == "high":
            reason = f"{unread} непрочитанных" if unread >= 5 else "негативные сигналы"
            urgency_label = f"Высокая · {reason}"
            urgency_urgent = "true"
        elif unread > 0:
            urgency_label = f"Средняя · {unread} непрочитанных"
            urgency_urgent = "false"
        else:
            urgency_label = "Низкая · Обработан"
            urgency_urgent = "false"

        # Build header meta with product reference
        header_meta_parts = ["Wildberries"]
        if chat.get("article"):
            header_meta_parts.append(f"Арт. {chat['article']}")
            if chat.get("product_name"):
                pname = chat["product_name"]
                if len(pname) > 40:
                    pname = pname[:37] + "..."
                header_meta_parts.append(pname)
        elif chat.get("product_name"):
            pname = chat["product_name"]
            header_meta_parts.append(f"{pname} (точный артикул не определён)")
        else:
            header_meta_parts.append("Чат покупателя")
        header_meta = " · ".join(header_meta_parts)

        entry = f"""            '{chat['num_id']}': {{
                header: {{ title: '{js_escape(name)}', meta: '{js_escape(header_meta)}' }},
                product: {product_js},
                chatHistory: [
{history_js}
                ],
                sentMessages: [],
                aiSuggestion: '{js_escape(ai_suggestion)}',
                chatDetails: {{ status: '{chat["status_label"]}', lastMessage: '{js_escape(last_time_str)}', unread: '{unread}', client: '{js_escape(name)}' }},
                ai: {{ sentiment: {{ label: '{sentiment[0]}', negative: {sentiment[1]} }}, categories: {categories_js}, urgency: {{ label: '{urgency_label}', urgent: {urgency_urgent} }}, recommendation: '{js_escape(generate_recommendation(chat))}' }},
                externalId: '{chat["chat_id"]}'
            }}"""
        entries.append(entry)

    return ",\n".join(entries)


# ============================================================
# READ TEMPLATE AND APPLY CHANGES
# ============================================================
print("\nReading template...")
with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
    html = f.read()

# --- 1. Replace chat list (3 sections) ---
first_active = urgent[0] if urgent else awaiting[0] if awaiting else rest[0] if rest else None
first_active_id = first_active["num_id"] if first_active else "1"

urgent_items = "\n".join(generate_chat_item_html(c, i == 0) for i, c in enumerate(urgent))
awaiting_items = "\n".join(generate_chat_item_html(c, not urgent and i == 0) for i, c in enumerate(awaiting))
rest_items = "\n".join(generate_chat_item_html(c, not urgent and not awaiting and i == 0) for i, c in enumerate(rest))

new_chat_list = f'''<!-- Chats: {len(chats)} total, {data['total_messages']} messages from WB Chat API -->
                <div class="queue-section">
                    <div class="queue-header">
                        <div class="queue-label">В работе</div>
                        <div class="queue-count">{len(urgent)}</div>
                    </div>

{urgent_items}
                </div>

                <div class="queue-section">
                    <div class="queue-header">
                        <div class="queue-label">Ожидают ответа</div>
                        <div class="queue-count">{len(awaiting)}</div>
                    </div>

{awaiting_items}
                </div>

                <div class="queue-section">
                    <div class="queue-header">
                        <div class="queue-label">Все сообщения</div>
                        <div class="queue-count">{len(rest)}</div>
                    </div>

{rest_items}
                </div>'''

marker_start = '            <!-- Queues -->\n            <div class="chat-list-content">\n'
marker_end = '\n            </div>\n        </section>'
s_idx = html.find(marker_start)
e_idx = html.find(marker_end, s_idx)

if s_idx != -1 and e_idx != -1:
    html = html[:s_idx + len(marker_start)] + new_chat_list + html[e_idx:]
    print("  Chat list replaced (3 sections)!")
else:
    print("  WARNING: Could not find chat list markers!")

# --- 2. Replace ENTIRE <script>...</script> block ---
script_start = html.find("    <script>")
script_end = html.find("    </script>", script_start)

if script_start != -1 and script_end != -1:
    context_js = generate_context_data_js(all_chats_ordered)
    new_script = f"""    <script>
        let currentChatId = '{first_active_id}';

        const contextData = {{
{context_js}
        }};

        // === RENDER CHAT HISTORY ===
        function renderChatHistory(chatId) {{
            const context = contextData[chatId];
            if (!context) return;
            currentChatId = chatId;

            // Update header
            document.querySelector('.chat-header-info h2').textContent = context.header.title;
            document.querySelector('.chat-header-meta').textContent = context.header.meta;

            // Render messages
            var container = document.getElementById('chatMessages');
            container.innerHTML = '';

            context.chatHistory.forEach(function(item) {{
                if (item.type === 'date') {{
                    var sep = document.createElement('div');
                    sep.className = 'date-separator';
                    sep.innerHTML = '<span>' + item.text + '</span>';
                    container.appendChild(sep);
                }} else {{
                    var msg = document.createElement('div');
                    msg.className = 'message ' + item.type;
                    var authorClass = item.author.indexOf('[авто]') !== -1 ? ' auto-tag' : '';
                    msg.innerHTML = '<div class="message-header">' +
                        '<span class="message-author' + authorClass + '">' + item.author + '</span>' +
                        '<span class="message-time">' + item.time + '</span>' +
                        '</div>' +
                        '<div class="message-content">' + (item.text || '<span class="empty-msg">\\ud83d\\udcce Изображение (не сохранилось)</span>').replace(/\\n/g, '<br>') + '</div>';
                    container.appendChild(msg);
                }}
            }});
            container.scrollTop = container.scrollHeight;

            // Update AI suggestion
            var aiEl = document.querySelector('.ai-suggestion-text');
            if (aiEl) aiEl.textContent = context.aiSuggestion;

            // Update product card
            var prodName = document.querySelector('.product-name');
            var prodRating = document.querySelector('.product-rating');
            var prodPrice = document.querySelector('.product-price');
            if (context.product) {{
                if (prodName) prodName.textContent = context.product.name || '';
                if (prodRating) prodRating.textContent = context.product.article ? 'Арт. ' + context.product.article : '';
                if (prodPrice) prodPrice.textContent = '';
            }} else {{
                if (prodName) prodName.textContent = 'Товар не определён';
                if (prodRating) prodRating.textContent = '';
                if (prodPrice) prodPrice.textContent = '';
            }}

            // Update chat details + AI analysis
            var infoValues = document.querySelectorAll('.info-section .info-value');
            // Section 1: Детали чата [0-3]
            if (context.chatDetails) {{
                if (infoValues[0]) infoValues[0].textContent = context.chatDetails.status;
                if (infoValues[1]) infoValues[1].textContent = context.chatDetails.lastMessage;
                if (infoValues[2]) infoValues[2].textContent = context.chatDetails.unread;
                if (infoValues[3]) infoValues[3].textContent = context.chatDetails.client;
            }}
            // Section 2: AI Анализ [4-7]
            if (context.ai) {{
                // [4] Тональность
                if (infoValues[4]) {{
                    infoValues[4].innerHTML = '<span class="insight-badge' + (context.ai.sentiment.negative ? ' negative' : '') + '">' + context.ai.sentiment.label + '</span>';
                }}
                // [5] Категории
                if (infoValues[5]) {{
                    infoValues[5].innerHTML = context.ai.categories.map(function(c) {{ return '<span class="insight-badge">' + c + '</span>'; }}).join(' ');
                }}
                // [6] Срочность
                if (infoValues[6]) {{
                    infoValues[6].innerHTML = '<span class="insight-badge' + (context.ai.urgency.urgent ? ' urgent' : '') + '">' + context.ai.urgency.label + '</span>';
                }}
                // [7] Рекомендация
                if (infoValues[7]) {{
                    infoValues[7].textContent = context.ai.recommendation;
                }}
            }}
        }}

        // === CHAT ITEM CLICK ===
        document.addEventListener('click', function(e) {{
            var chatItem = e.target.closest('.chat-item');
            if (chatItem) {{
                document.querySelectorAll('.chat-item').forEach(function(i) {{ i.classList.remove('active'); }});
                chatItem.classList.add('active');
                var chatId = chatItem.getAttribute('data-chat-id');
                if (chatId) renderChatHistory(chatId);
            }}
        }});

        // === FILTER PILLS ===
        var pills = document.querySelectorAll('.filter-pill');
        pills.forEach(function(pill) {{
            pill.addEventListener('click', function() {{
                pills.forEach(function(p) {{ p.classList.remove('active'); }});
                this.classList.add('active');

                var filter = this.getAttribute('data-filter');
                var items = document.querySelectorAll('.chat-item');
                var sections = document.querySelectorAll('.queue-section');

                items.forEach(function(item) {{
                    var status = item.getAttribute('data-status');
                    if (filter === 'all') {{
                        item.style.display = 'flex';
                    }} else if (filter === 'urgent') {{
                        item.style.display = item.classList.contains('urgent') ? 'flex' : 'none';
                    }} else if (filter === 'unanswered') {{
                        item.style.display = (item.classList.contains('urgent') || status === 'waiting' || status === 'client-replied') ? 'flex' : 'none';
                    }} else if (filter === 'resolved') {{
                        item.style.display = (status === 'responded' || status === 'auto-response') ? 'flex' : 'none';
                    }}
                }});

                // Hide empty sections
                sections.forEach(function(sec) {{
                    var visible = sec.querySelectorAll('.chat-item[style*="flex"], .chat-item:not([style])');
                    var visibleCount = 0;
                    visible.forEach(function(v) {{ if (v.style.display !== 'none') visibleCount++; }});
                    sec.style.display = (filter === 'all' || visibleCount > 0) ? 'block' : 'none';
                }});
            }});
        }});

        // === SEND MESSAGE ===
        function sendMessage() {{
            var input = document.getElementById('chatInput');
            if (input.value.trim()) {{
                console.log('Sending:', input.value);
                input.value = '';
            }}
        }}

        // === AUTO-GROW TEXTAREA ===
        var chatInput = document.getElementById('chatInput');
        if (chatInput) {{
            chatInput.addEventListener('input', function() {{
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            }});
        }}

        // === DRAG & DROP ===
        var draggedElement = null;
        document.querySelectorAll('.chat-item').forEach(function(item) {{
            item.addEventListener('dragstart', function(e) {{
                draggedElement = this;
                this.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            }});
            item.addEventListener('dragend', function() {{
                this.classList.remove('dragging');
            }});
        }});

        document.querySelectorAll('.queue-section').forEach(function(section) {{
            section.addEventListener('dragover', function(e) {{
                e.preventDefault();
                this.classList.add('drag-over');
            }});
            section.addEventListener('dragleave', function(e) {{
                if (!this.contains(e.relatedTarget)) this.classList.remove('drag-over');
            }});
            section.addEventListener('drop', function(e) {{
                e.preventDefault();
                this.classList.remove('drag-over');
                if (draggedElement) {{
                    this.appendChild(draggedElement);
                    document.querySelectorAll('.queue-section').forEach(function(q) {{
                        var count = q.querySelectorAll('.chat-item').length;
                        var countEl = q.querySelector('.queue-count');
                        if (countEl) countEl.textContent = count;
                    }});
                }}
            }});
        }});

        // === MOBILE NAV ===
        function setMobileView(view) {{
            var chatCenter = document.querySelector('.chat-center');
            if (chatCenter) chatCenter.setAttribute('data-mobile-view', view);
        }}

        document.addEventListener('click', function(e) {{
            var chatItem = e.target.closest('.chat-item');
            if (chatItem && window.innerWidth <= 768) {{
                setMobileView('chat');
            }}
        }});

        var infoBtn = document.querySelector('.header-action-btn[title="Информация"]');
        if (infoBtn) {{
            infoBtn.addEventListener('click', function() {{
                if (window.innerWidth <= 768) {{
                    setMobileView('context');
                }}
            }});
        }}

        // === INIT ===
        renderChatHistory('{first_active_id}');
    """
    html = html[:script_start] + new_script + html[script_end:]
    print("  Full <script> block replaced (contextData + JS logic)!")
else:
    print("  WARNING: Could not find <script> block!")

# --- 3. CSS updates ---
# 3a. Remove red dot ::before on urgent name (now unified to status-dot)
urgent_before_css = re.compile(
    r'\.chat-item\.urgent\s+\.chat-item-name::before\s*\{[^}]+\}',
    re.DOTALL
)
html, n_removed = urgent_before_css.subn('/* urgent ::before removed — unified to status-dot */', html)
if n_removed:
    print(f"  CSS: removed .urgent .chat-item-name::before ({n_removed})")

# 3b. Replace .replied → .client-replied if needed
if '.status-dot.replied' in html:
    html = html.replace('.status-dot.replied', '.status-dot.client-replied')
    print("  CSS: .replied → .client-replied")

# 3c. Inject all extra CSS after .status-dot.responded
FULL_CSS_EXTRAS = """.status-dot.auto-response { background: #9aa0a6; }
.status-dot.risk { background: #ea4335 !important; }
.message-author.auto-tag { color: #9aa0a6; font-style: italic; }
.empty-msg { color: #9aa0a6; font-style: italic; }
.chat-header-meta { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.product-context { min-width: 300px; max-width: 300px; flex-shrink: 0; }"""

# Remove old extras if present, then re-inject
for old_rule in ['.status-dot.auto-response', '.status-dot.risk', '.auto-tag', '.empty-msg']:
    pass  # We'll just check and inject what's missing

anchor = '.status-dot.responded { background: #34a853; }'
if anchor in html:
    # Remove any existing extras after anchor (they'll be re-added)
    # Find where extras block ends
    anchor_pos = html.find(anchor)
    after_anchor = html[anchor_pos + len(anchor):]
    # Count lines to skip (old extras)
    lines_after = after_anchor.split('\n')
    skip = 0
    for line in lines_after:
        stripped = line.strip()
        if stripped and (stripped.startswith('.status-dot.auto') or stripped.startswith('.status-dot.risk')
                        or stripped.startswith('.message-author.auto') or stripped.startswith('.empty-msg')
                        or stripped.startswith('.chat-header-meta') or stripped.startswith('.product-context')
                        or stripped.startswith('/*')):
            skip += 1
        else:
            break
    if skip > 0:
        cut_point = anchor_pos + len(anchor)
        remaining_lines = after_anchor.split('\n')
        html = html[:cut_point] + '\n' + FULL_CSS_EXTRAS + '\n' + '\n'.join(remaining_lines[skip:])
    else:
        html = html.replace(anchor, anchor + '\n' + FULL_CSS_EXTRAS)
    print("  CSS: injected risk, auto-tag, empty-msg, header-meta, product-context fixes!")
else:
    print("  WARNING: Could not find CSS anchor!")

# --- 4. Update filter counts (regex-based for robustness) ---
total = len(chats)
urgent_count = len(urgent)
awaiting_count = len(awaiting)
resolved_count = len(rest)

html = re.sub(
    r'(data-filter="all">\s*Все\s*<span class="count">)\d+',
    f'\\g<1>{total}', html
)
html = re.sub(
    r'(data-filter="urgent">\s*Срочно\s*<span class="count">)\d+',
    f'\\g<1>{urgent_count}', html
)
html = re.sub(
    r'(data-filter="unanswered">\s*Без ответа\s*<span class="count">)\d+',
    f'\\g<1>{awaiting_count}', html
)
html = re.sub(
    r'(data-filter="resolved">\s*Обработаны\s*<span class="count">)\d+',
    f'\\g<1>{resolved_count}', html
)
print("  Filter counts updated!")

# --- 5. Update initial active chat header in HTML ---
if first_active:
    fname = first_active.get("client_name", "Клиент") or "Клиент"
    html = re.sub(r'(<div class="chat-header-info">\s*<h2>)[^<]+(</h2>)', f'\\g<1>{fname}\\2', html)

# ============================================================
# SAVE
# ============================================================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

# ============================================================
# REPORT
# ============================================================
print(f"\nSaved to: {OUTPUT_FILE}")
print(f"\nTotal chats: {total}")
print(f"  В работе (urgent): {urgent_count}")
print(f"  Ожидают ответа: {awaiting_count}")
print(f"  Все сообщения: {resolved_count}")

print(f"\nСтатусы:")
status_counts = Counter(c["status_class"] for c in chats)
for status, count in status_counts.most_common():
    print(f"  {status}: {count}")

with_article = sum(1 for c in chats if c.get("article"))
with_product = sum(1 for c in chats if c.get("product_name") and not c.get("article"))
no_product = sum(1 for c in chats if not c.get("article") and not c.get("product_name"))
auto_count = sum(1 for c in chats if c.get("has_auto_template"))

print(f"\nТоварная привязка:")
print(f"  С артикулом: {with_article}")
print(f"  С названием товара (без артикула): {with_product}")
print(f"  Без товара: {no_product}")
print(f"\nАвто-шаблонов WB: {auto_count}")

articles = [(c["client_name"], c["article"], c.get("product_name", "")) for c in chats if c.get("article")]
if articles:
    print(f"\nАртикулы ({len(articles)}):")
    for name, art, prod in articles:
        prod_short = prod[:50] if prod else ""
        print(f"  - {name}: арт. {art} ({prod_short})")

keywords = [(c["client_name"], c["product_name"]) for c in chats if c.get("product_name") and not c.get("article")]
if keywords:
    print(f"\nТовары по ключевым словам ({len(keywords)}):")
    for name, prod in keywords:
        print(f"  - {name}: {prod}")

print("\nDONE!")
