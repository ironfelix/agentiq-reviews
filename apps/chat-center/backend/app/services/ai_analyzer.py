"""
AI Analyzer service for chat analysis and response suggestions.

Uses DeepSeek API to:
1. Classify chat intent (delivery_status, defect, refund, etc.)
2. Analyze sentiment and urgency
3. Generate response recommendation following guardrails

Based on RESPONSE_GUARDRAILS.md policy.

Guardrails: all banned phrases and replacements are sourced from
``app.services.guardrails`` (single source of truth).
"""

import asyncio
import httpx
import logging
import json
import re
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.config import get_settings
from app.services.guardrails import (
    replace_banned_phrases,
    get_max_length,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Shared httpx client for connection reuse (avoids per-request TCP handshake)
# ---------------------------------------------------------------------------
_shared_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_shared_client() -> httpx.AsyncClient:
    """Return a module-level httpx.AsyncClient with connection pooling.

    The client is created lazily on first use. Connection pool limits
    are tuned for the typical DeepSeek API usage pattern (few concurrent
    requests, keep-alive connections).

    When called from Celery workers (via run_async), each task invocation
    creates a fresh event loop. The previous client's transport is bound
    to the now-closed loop, causing 'Event loop is closed' errors.
    We detect this by comparing the current running loop to the one
    stored at client creation time and recreate the client when they differ.
    """
    global _shared_client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    needs_new = (
        _shared_client is None
        or _shared_client.is_closed
        or (current_loop is not None and current_loop is not _client_loop)
    )
    if needs_new:
        # Close the stale client to release file descriptors gracefully.
        if _shared_client is not None and not _shared_client.is_closed:
            try:
                _shared_client._transport.close()  # type: ignore[union-attr]
            except Exception:
                pass
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,    # fast fail on connection issues
                read=30.0,      # DeepSeek can take a few seconds
                write=10.0,     # request body is small
                pool=5.0,       # waiting for a free connection
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=120,  # reuse connections for 2 minutes
            ),
        )
        _client_loop = current_loop
    return _shared_client


# Max tokens tuned per channel and complexity
_MAX_TOKENS_SIMPLE = 300   # short replies: positive reviews, thanks
_MAX_TOKENS_STANDARD = 600  # normal replies: most intents
_MAX_TOKENS_COMPLEX = 1000  # complex replies: defects, escalation


def _select_max_tokens(channel: str, intent: Optional[str] = None) -> int:
    """Choose appropriate max_tokens based on expected response length."""
    if intent in ("thanks",):
        return _MAX_TOKENS_SIMPLE
    if channel == "review" and intent in ("thanks", "positive_feedback"):
        return _MAX_TOKENS_SIMPLE
    if intent in ("defect_not_working", "wrong_item", "refund_exchange"):
        return _MAX_TOKENS_COMPLEX
    return _MAX_TOKENS_STANDARD


# Russian surname suffixes — if a single word ends with these, it's likely a last name
_SURNAME_SUFFIXES = (
    # Male: -ов, -ев, -ёв, -ин, -ын, -ский, -цкий, -ой, -ий
    "ов", "ев", "ёв", "ин", "ын", "ский", "цкий", "ской", "цкой",
    # Female: -ова, -ева, -ёва, -ина, -ына, -ская, -цкая
    "ова", "ева", "ёва", "ина", "ына", "ская", "цкая",
    # Ukrainian/common: -ко, -енко, -чук, -щук, -юк, -ук, -ич, -вич
    "ко", "енко", "чук", "щук", "юк", "ук", "ич", "вич",
)


def extract_first_name(customer_name: Optional[str]) -> Optional[str]:
    """
    Extract first name from customer_name for greeting personalization.

    WB format is typically "Фамилия Имя Отчество" or just "Фамилия".
    Returns first name if detectable, None if only surname.
    """
    if not customer_name or not customer_name.strip():
        return None

    parts = customer_name.strip().split()

    if len(parts) >= 2:
        # "Исакович Анна Витальевна" → "Анна"
        return parts[1]

    # Single word — check if it looks like a surname
    word = parts[0]
    word_lower = word.lower()
    for suffix in _SURNAME_SUFFIXES:
        if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 1:
            # Likely a surname, don't use for greeting
            return None

    # Doesn't look like a surname — could be a first name
    return word


# Intent types with descriptions
INTENTS = {
    # Post-purchase intents
    "delivery_status": "Где мой заказ?",
    "delivery_delay": "Заказ задерживается",
    "cancel_request": "Хочу отменить",
    "wrong_item": "Прислали не тот товар",
    "defect_not_working": "Брак, не работает",
    "usage_howto": "Как пользоваться?",
    "product_spec": "Характеристики товара",
    "refund_exchange": "Возврат или обмен",
    "thanks": "Благодарность",
    "quality_complaint": "Жалоба на качество",
    # Pre-purchase intents (HIGH priority - potential sale!)
    "pre_purchase": "Вопрос перед покупкой",
    "sizing_fit": "Какой размер выбрать?",
    "availability": "Есть ли в наличии?",
    "compatibility": "Подойдёт ли к...?",
    "other": "Другое",
}

# SLA priorities by intent
SLA_PRIORITIES = {
    # P0 (urgent) < 1 hour - critical issues
    "defect_not_working": "urgent",
    "wrong_item": "urgent",
    # P1 (high) < 1 hour - pre-purchase = potential sale!
    "pre_purchase": "high",
    "sizing_fit": "high",
    "availability": "high",
    "compatibility": "high",
    "delivery_delay": "high",
    "cancel_request": "high",
    # P2 (normal) < 4 hours
    "quality_complaint": "normal",
    "refund_exchange": "normal",
    "delivery_status": "normal",
    # P3 (low) < 24 hours
    "usage_howto": "low",
    "product_spec": "low",
    "thanks": "low",
    "other": "normal",
}

# NOTE: BANNED_PHRASES dict has been moved to guardrails.py
# (BANNED_PHRASE_REPLACEMENTS). This module now uses
# replace_banned_phrases() from guardrails for post-generation cleanup.

# Return keywords (to suggest refund instruction)
RETURN_TRIGGER_WORDS = [
    "возврат", "вернуть", "замена", "заменить", "обменять", "обмен",
]

# Escalation keywords
ESCALATION_KEYWORDS = {
    "medical": ["аллергия", "здоровье", "реакция", "отравление", "химия"],
    "legal": ["суд", "роспотребнадзор", "жалоба", "претензия", "адвокат"],
    "counterfeit": ["подделка", "фейк", "контрафакт", "не оригинал"],
}


# System prompt for DeepSeek
CHAT_ANALYSIS_SYSTEM = """Ты — эксперт по клиентскому сервису на маркетплейсах WB/Ozon.

Задача: проанализировать чат с покупателем и предложить ответ продавца.

ИНТЕНТЫ (выбери один):
- delivery_status: "Где мой заказ?"
- delivery_delay: "Заказ задерживается"
- cancel_request: "Хочу отменить"
- wrong_item: "Прислали не тот товар"
- defect_not_working: "Брак, не работает"
- usage_howto: "Как пользоваться?"
- product_spec: "Характеристики товара"
- refund_exchange: "Возврат или обмен"
- thanks: "Благодарность"
- other: "Другое"

КРИТИЧЕСКИ ВАЖНО — ЗАПРЕЩЕНО писать в recommendation:
1. "вернём деньги", "гарантируем возврат/замену" — продавец НЕ контролирует возвраты на WB
2. "доставим завтра", "через N дней" — продавец НЕ контролирует логистику
3. "отменим заказ", "ускорим доставку" — нет таких полномочий
4. "вы неправильно", "ваша вина" — обвинение покупателя запрещено
5. "ИИ", "бот", "нейросеть", "GPT" — раскрытие автоматизации
6. "обратитесь в поддержку WB" — отписка
7. "характеристики не соответствуют" — юридическое признание обмана

ПРАВИЛА генерации recommendation:
1. Формат: 2-3 предложения, макс 500 символов
2. Начни с "{Имя}, здравствуйте!" если есть имя покупателя
3. Дай КОНКРЕТНЫЙ ответ по ситуации — не общие фразы
4. Концовка должна быть РАЗНОЙ и уместной — НЕ копипасти одну и ту же фразу
5. Если проблема очевидна (wrong_item, defect) → сразу инструкция по возврату
6. Если доставка → дай конкретику: дату отгрузки, статус, что проверили
7. Если клиент повторяет сообщение → признать задержку, не переспрашивать
8. Если интент неясен → уточнить конкретный вопрос
9. НЕ выдумывать характеристики товара — только из контекста чата
10. НЕ заканчивай шаблонно "Если нужна помощь — пишите!" — это выглядит как бот

ОСОБЫЙ КЕЙС — покупатель доволен / проблема решена:
Если последнее сообщение покупателя выражает благодарность, удовлетворение или подтверждение решения проблемы (например: "Спасибо", "Всё получилось", "Доставили", "Вопрос решён") — НЕ отвечай дежурной фразой.
Вместо этого:
- Поблагодари за обратную связь
- Мягко попроси оставить отзыв в карточке товара на WB (это помогает другим покупателям)
- НЕ будь навязчивым, просьба должна быть естественной
- Если покупатель доволен ПОСЛЕ решения проблемы (возврат, дефект, доставка) — это самый ценный момент для просьбы об отзыве
- intent = "thanks" в этом случае

ПРИМЕРЫ хороших рекомендаций:
- wrong_item: "Олег, здравствуйте! Очень неприятная ситуация — приносим извинения. Оформите возврат через ЛК WB с пометкой «не соответствует описанию», мы со своей стороны передали информацию на склад."
- defect_not_working: "Сергей, здравствуйте! Нам очень жаль, что товар оказался с дефектом. Оформите, пожалуйста, возврат через ЛК WB с пометкой «брак» — мы уже передали информацию в отдел качества."
- delivery_status: "Алексей, здравствуйте! Со своей стороны проверили — ваш заказ передан в доставку. Отслеживайте актуальный статус в личном кабинете WB в разделе «Доставки»."
- usage_howto: "Здравствуйте! Насос работает только с чистой водой — при попадании песка нужно промыть корпус проточной водой. В карточке товара есть подробная инструкция."
- cancel_request: "Здравствуйте! Вы можете отменить заказ самостоятельно в ЛК WB: раздел Доставки → выберите заказ → Отменить."
- refund_exchange: "Здравствуйте! Оформить возврат можно в ЛК WB: раздел Покупки → выберите товар → Оформить возврат. Деньги вернутся на карту в течение нескольких дней."
- thanks (просто благодарность): "Спасибо за тёплые слова! Рады, что товар понравился."
- thanks (после решения проблемы): "Рады, что всё получилось! Если будет минутка — оставьте, пожалуйста, отзыв в карточке товара на WB. Это помогает другим покупателям с выбором."
- thanks (после доставки): "Отлично, что всё дошло! Будем рады, если поделитесь впечатлениями в отзыве к товару на WB."

ESCALATION (needs_escalation = true):
- Аллергия, здоровье, мед. реакция → STOP
- Подозрение на контрафакт → STOP
- Угрозы, юридические претензии → STOP
- Персональные данные в чате → STOP"""


CHAT_ANALYSIS_USER = """Проанализируй чат и предложи ответ.

Товар: {product_name}
{product_context_block}
{rating_context_block}
История переписки (от старых к новым):
{messages_block}

Верни JSON:
{{
  "intent": "один из интентов",
  "sentiment": "positive" | "negative" | "neutral",
  "urgency": "low" | "normal" | "high" | "critical",
  "categories": ["complaint", "question", "order_status", ...],
  "recommendation": "ГОТОВЫЙ ТЕКСТ ответа от лица продавца (2-3 предл., макс 500 симв.)",
  "recommendation_reason": "почему именно такой ответ (1 предл.)",
  "needs_escalation": true | false,
  "escalation_reason": "причина эскалации если needs_escalation=true"
}}

ВАЖНО:
- recommendation — это ГОТОВЫЙ ТЕКСТ для отправки, НЕ инструкция
- Используй имя покупателя если есть
- Если есть информация о товаре — используй её для КОНКРЕТНОГО ответа (состав, размеры, характеристики)
- НЕ выдумывай характеристики, используй ТОЛЬКО те, что указаны в контексте
- Если последнее сообщение от продавца — рекомендация не нужна, верни recommendation: null"""


# ---------------------------------------------------------------------------
# Channel-specific system prompts (reviews & questions)
# ---------------------------------------------------------------------------

REVIEW_DRAFT_SYSTEM = """Ты — эксперт по клиентскому сервису на маркетплейсах WB/Ozon.

Задача: написать публичный ответ продавца на отзыв покупателя.

ВАЖНО — ЭТО ОТЗЫВ, А НЕ ЧАТ:
- Ответ на отзыв — публичный, его видят ВСЕ покупатели
- Покупатель НЕ может ответить — НЕ задавай вопросов
- Будь лаконичным, конкретным, полезным
- Поблагодари за покупку

ПРАВИЛА ПО РЕЙТИНГУ:
- ★1-2 (негатив): Эмпатия + извинение + конкретное решение проблемы
- ★3 (средний): Благодарность + признание недостатка + что делаем для улучшения
- ★4-5 (позитив): Благодарность за отзыв + подчеркни что рады

КРИТИЧЕСКИ ВАЖНО — ЗАПРЕЩЕНО писать:
1. "вернём деньги", "гарантируем возврат/замену" — продавец НЕ контролирует возвраты на WB
2. "доставим завтра", "через N дней" — продавец НЕ контролирует логистику
3. "вы неправильно", "ваша вина" — обвинение покупателя запрещено
4. "ИИ", "бот", "нейросеть", "GPT" — раскрытие автоматизации
5. "обратитесь в поддержку WB" — отписка
6. НЕ задавай вопросов покупателю — он не ответит на отзыв

ПРАВИЛА генерации recommendation:
1. Формат: 2-3 предложения, макс 500 символов
2. Начни с приветствия и благодарности за отзыв
3. Адресуй конкретные жалобы из текста отзыва
4. НЕ предлагай возврат/замену ЕСЛИ покупатель сам не просил
5. Если дефект очевиден → инструкция "Оформите возврат через ЛК WB"
6. НЕ выдумывать характеристики товара — только из контекста
7. Концовка должна быть РАЗНОЙ — НЕ копипасти шаблон
8. НЕ заканчивай "Если нужна помощь — пишите!" — покупатель не ответит

ПРИМЕРЫ хороших ответов на отзывы:
- ★1 (брак): "Здравствуйте! Очень жаль, что товар оказался с дефектом. Оформите, пожалуйста, возврат через ЛК WB — мы передали информацию в отдел качества."
- ★2 (не подошёл размер): "Здравствуйте! Спасибо за обратную связь. К сожалению, данная модель может маломерить — рекомендуем ориентироваться на размерную сетку в карточке товара."
- ★5 (доволен): "Спасибо за отзыв! Рады, что товар оправдал ожидания. Приятных покупок!"
- ★4 (нравится, но замечание): "Благодарим за отзыв и обратную связь! Ваше замечание учтём при улучшении товара."

ESCALATION (needs_escalation = true):
- Аллергия, здоровье, мед. реакция → STOP
- Подозрение на контрафакт → STOP
- Угрозы, юридические претензии → STOP"""


REVIEW_DRAFT_USER = """Напиши ответ продавца на отзыв покупателя.

Товар: {product_name}
Рейтинг: ★{rating}/5

Текст отзыва:
{review_text}

Верни JSON:
{{
  "intent": "один из: thanks, defect_not_working, wrong_item, refund_exchange, product_spec, other",
  "sentiment": "positive" | "negative" | "neutral",
  "urgency": "low" | "normal" | "high" | "critical",
  "categories": ["complaint", "praise", "defect", ...],
  "recommendation": "ГОТОВЫЙ ТЕКСТ ответа от лица продавца (2-3 предл., макс 500 симв.)",
  "recommendation_reason": "почему именно такой ответ (1 предл.)",
  "needs_escalation": true | false,
  "escalation_reason": "причина эскалации если needs_escalation=true"
}}

ВАЖНО:
- recommendation — это ГОТОВЫЙ ТЕКСТ для публикации, НЕ инструкция
- Учитывай рейтинг при выборе тона и содержания
- НЕ задавай вопросов — покупатель не ответит на отзыв"""


QUESTION_DRAFT_SYSTEM = """Ты — дружелюбный и внимательный эксперт по клиентскому сервису на маркетплейсах WB/Ozon.

Задача: написать ПОЛЕЗНЫЙ и ЗАБОТЛИВЫЙ публичный ответ продавца на вопрос покупателя.

КЛЮЧЕВОЙ ПРИНЦИП — ПОМОГИ ПОКУПАТЕЛЮ:
- Ответ публичный, его видят ВСЕ покупатели — он помогает другим
- Покупатель задал вопрос = ему ВАЖНО получить ответ, прояви уважение
- Отвечай ПОДРОБНО и КОНКРЕТНО — это повышает конверсию
- Покажи, что продавец разбирается в товаре и заботится о клиентах
- Если вопрос перед покупкой — помоги принять решение, дай полезную информацию

ТИПЫ ВОПРОСОВ:
- Pre-purchase: размеры, состав, наличие, совместимость → помоги купить, подскажи детали
- Post-purchase: как пользоваться, проблема → дай решение/инструкцию, прояви заботу
- Характеристики: конкретный факт из карточки → чёткий полный ответ

ТОН ОТВЕТА — ДРУЖЕЛЮБНЫЙ И ЗАБОТЛИВЫЙ:
- Начни с приветствия: "Здравствуйте!" или "Добрый день!"
- Поблагодари за вопрос: "Спасибо за интерес к товару!" или "Отличный вопрос!"
- Ответь КОНКРЕТНО и ПОЛЕЗНО — покупатель хочет факты, не отписки
- Если не знаешь точного ответа — честно скажи, но предложи помощь
- Закончи дружелюбно: "С радостью поможем с выбором!" или "Пишите, если нужна помощь!"
- НЕ используй формальные отписки: "информация в карточке", "смотрите описание"

КРИТИЧЕСКИ ВАЖНО — ЗАПРЕЩЕНО писать:
1. "вернём деньги", "гарантируем возврат/замену" — продавец НЕ контролирует возвраты на WB
2. "вы неправильно", "ваша вина" — обвинение покупателя запрещено
3. "ИИ", "бот", "нейросеть", "GPT" — раскрытие автоматизации
4. "обратитесь в поддержку WB" — отписка, неуважение к покупателю
5. "посмотрите в описании" — если информация есть, ПРОЦИТИРУЙ её прямо в ответе
6. НЕ выдумывай характеристики — только из контекста / карточки

ПРАВИЛА генерации recommendation:
1. Формат: 2-4 предложения, макс 500 символов
2. Начни с приветствия + благодарности за вопрос
3. Ответь КОНКРЕТНО — используй факты, цифры, характеристики
4. Если вопрос о размере/параметрах — дай конкретные данные из карточки
5. Если не знаешь точный ответ — предложи уточнить у покупателя или обещай проверить
6. Финал: предложи помощь, покажи заинтересованность в покупателе

ПРИМЕРЫ хороших ответов на вопросы:
- Размер: "Здравствуйте! Спасибо за вопрос! Модель соответствует стандартной размерной сетке. При росте 175 и весе 70 кг рекомендуем размер M. Если сомневаетесь — напишите ваши параметры, поможем подобрать!"
- Состав: "Добрый день! Состав: 95% хлопок, 5% эластан. Ткань мягкая, приятная к телу и хорошо тянется. Подойдёт для повседневной носки."
- Наличие: "Здравствуйте! Да, товар есть в наличии. Поставки регулярные, так что можно заказывать смело. Будем рады, если выберете нас!"
- Использование: "Добрый день! Спасибо за вопрос! Для начала работы зарядите устройство 2-3 часа. После полной зарядки индикатор загорится зелёным. Если будут вопросы по использованию — пишите!"

ESCALATION (needs_escalation = true):
- Аллергия, здоровье → STOP
- Подозрение на контрафакт → STOP"""


QUESTION_DRAFT_USER = """Напиши ответ продавца на вопрос покупателя.

Товар: {product_name}

Вопрос покупателя:
{question_text}

Верни JSON:
{{
  "intent": "один из: product_spec, sizing_fit, availability, compatibility, usage_howto, pre_purchase, other",
  "sentiment": "neutral",
  "urgency": "low" | "normal" | "high",
  "categories": ["question", "pre_purchase", "specs", ...],
  "recommendation": "ГОТОВЫЙ ТЕКСТ ответа от лица продавца (1-3 предл., макс 500 симв.)",
  "recommendation_reason": "почему именно такой ответ (1 предл.)",
  "needs_escalation": true | false,
  "escalation_reason": "причина эскалации если needs_escalation=true"
}}

ВАЖНО:
- recommendation — это ГОТОВЫЙ ТЕКСТ для публикации, НЕ инструкция
- Ответь на вопрос КОНКРЕТНО"""


# ---------------------------------------------------------------------------
# Tone instructions (injected into system prompt based on seller settings)
# ---------------------------------------------------------------------------

TONE_INSTRUCTIONS: Dict[str, str] = {
    "formal": "\nТОН ОТВЕТА: Используй вежливый деловой тон. Обращайся на «Вы». Без сокращений, без неформальных оборотов.",
    "friendly": "\nТОН ОТВЕТА: Используй тёплый дружеский тон. Можно на «Вы», но с теплотой и эмпатией. Допустимы неформальные обороты.",
    "neutral": "\nТОН ОТВЕТА: Используй нейтрально-вежливый тон. По делу, без излишней эмоциональности.",
}


def get_system_prompt(channel: str, tone: str = "neutral") -> str:
    """Return the appropriate system prompt for the given channel and tone.

    Args:
        channel: One of 'review', 'question', 'chat'.
        tone: One of 'formal', 'friendly', 'neutral'.

    Returns:
        Complete system prompt string with tone instruction appended.
    """
    if channel == "review":
        base = REVIEW_DRAFT_SYSTEM
    elif channel == "question":
        base = QUESTION_DRAFT_SYSTEM
    else:
        # chat or unknown -- fall back to chat prompt
        base = CHAT_ANALYSIS_SYSTEM

    tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["neutral"])
    return base + tone_instruction


def get_user_prompt(
    channel: str,
    *,
    product_name: str = "Товар",
    messages_block: str = "",
    review_text: str = "",
    rating: Optional[int] = None,
    question_text: str = "",
    product_context_block: str = "",
    rating_context_block: str = "",
    customer_context_block: str = "",
) -> str:
    """Return the appropriate user prompt for the given channel.

    Args:
        channel: One of 'review', 'question', 'chat'.
        product_name: Product name for context.
        messages_block: Formatted chat messages (for chat channel).
        review_text: Review text (for review channel).
        rating: Review rating 1-5 (for review channel).
        question_text: Question text (for question channel).
        product_context_block: Product card context block (for chat channel).
        rating_context_block: Rating context block (for chat channel).
        customer_context_block: Customer profile context block (for all channels).

    Returns:
        Formatted user prompt string.
    """
    # Customer context is appended to the prompt for all channels
    suffix = customer_context_block if customer_context_block else ""

    if channel == "review":
        base = REVIEW_DRAFT_USER.format(
            product_name=product_name,
            rating=rating if rating is not None else "?",
            review_text=review_text or "(пустой отзыв)",
        )
        return base + suffix
    elif channel == "question":
        base = QUESTION_DRAFT_USER.format(
            product_name=product_name,
            question_text=question_text or "(пустой вопрос)",
        )
        return base + suffix
    else:
        base = CHAT_ANALYSIS_USER.format(
            product_name=product_name,
            messages_block=messages_block,
            product_context_block=product_context_block,
            rating_context_block=rating_context_block,
        )
        return base + suffix


class AIAnalyzer:
    """AI-powered chat analyzer using DeepSeek API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize AI Analyzer.

        Args:
            api_key: DeepSeek API key (defaults to settings)
            base_url: API base URL (defaults to settings)
        """
        self.provider = (provider or "deepseek").strip().lower()
        self.model_name = (model_name or "deepseek-chat").strip()
        self.enabled = bool(enabled)
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL

        if not self.enabled:
            logger.info("LLM disabled by runtime config, AI analyzer in fallback mode")
        if self.provider != "deepseek":
            logger.warning("Unsupported LLM provider '%s', fallback mode will be used", self.provider)
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not configured, AI analysis disabled")

    async def analyze_chat(
        self,
        messages: List[Dict],
        product_name: Optional[str] = None,
        customer_name: Optional[str] = None,
        product_context: Optional[str] = None,
        rating_context: Optional[str] = None,
        customer_context: Optional[str] = None,
        channel: str = "chat",
        tone: str = "neutral",
        rating: Optional[int] = None,
        sla_config: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Analyze chat/review/question and generate response recommendation.

        Args:
            messages: List of message dicts with keys:
                - text: message text
                - author_type: "buyer" or "seller"
                - created_at: datetime
            product_name: Product name for context
            customer_name: Customer name for personalization
            product_context: Formatted product card context (from product_context.py)
            rating_context: Rating-aware prompt instructions (from product_context.py)
            customer_context: Formatted customer profile context (from customer_profile_service.py)
            channel: One of 'review', 'question', 'chat' (selects prompt template)
            tone: One of 'formal', 'friendly', 'neutral' (seller preference)
            rating: Review rating 1-5 (for review channel)
            sla_config: Optional seller-specific SLA config dict from sla_config service

        Returns:
            Analysis dict with keys:
                - intent: classified intent
                - sentiment: positive/negative/neutral
                - urgency: low/normal/high/critical
                - categories: list of categories
                - recommendation: suggested reply text
                - recommendation_reason: why this reply
                - needs_escalation: bool
                - escalation_reason: if escalation needed
                - sla_priority: calculated SLA priority
                - analyzed_at: timestamp
        """
        if not self.enabled or self.provider != "deepseek" or not self.api_key:
            return self._fallback_analysis(messages, customer_name, sla_config=sla_config)

        if not messages:
            return None

        # Build messages block
        messages_block = self._format_messages(messages, customer_name)

        # Check for escalation keywords first
        escalation = self._check_escalation_keywords(messages)

        # Resolve the text for review/question channels
        buyer_text = ""
        for msg in messages:
            if msg.get("author_type") == "buyer":
                buyer_text = msg.get("text", "")
                break

        try:
            # Build channel-specific prompts
            system_prompt = get_system_prompt(channel, tone)
            user_prompt = get_user_prompt(
                channel,
                product_name=product_name or "Товар",
                messages_block=messages_block,
                review_text=buyer_text if channel == "review" else "",
                rating=rating,
                question_text=buyer_text if channel == "question" else "",
                product_context_block=(
                    f"\nИнформация о товаре:\n{product_context}\n" if product_context else ""
                ),
                rating_context_block=(
                    f"\n{rating_context}\n" if rating_context else ""
                ),
                customer_context_block=(
                    f"\nИнформация о клиенте:\n{customer_context}\n" if customer_context else ""
                ),
            )

            # Call DeepSeek API
            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            if not response:
                return self._fallback_analysis(messages, customer_name, sla_config=sla_config)

            # Parse and validate response
            analysis = self._parse_response(response)

            # Apply guardrails to recommendation
            if analysis.get("recommendation"):
                analysis["recommendation"] = self._apply_guardrails(
                    analysis["recommendation"],
                    customer_name,
                    channel=channel,
                )

            # Override escalation if detected by keywords
            if escalation:
                analysis["needs_escalation"] = True
                analysis["escalation_reason"] = escalation

            # Calculate SLA priority
            intent = analysis.get("intent", "other")
            analysis["sla_priority"] = self._calculate_sla_priority(
                intent,
                analysis.get("urgency", "normal"),
                messages,
                sla_config=sla_config,
            )

            analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()

            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._fallback_analysis(messages, customer_name, sla_config=sla_config)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        # Legacy kwargs kept for backwards compatibility with external callers
        product_name: Optional[str] = None,
        messages_block: Optional[str] = None,
        product_context: Optional[str] = None,
        rating_context: Optional[str] = None,
    ) -> Optional[Dict]:
        """Call DeepSeek API for analysis.

        Args:
            system_prompt: Complete system prompt (channel + tone specific).
            user_prompt: Complete user prompt (already formatted).
        """
        # Legacy fallback: if called with old positional args, build prompts
        if product_name is not None and messages_block is not None:
            product_context_block = ""
            if product_context:
                product_context_block = f"\nИнформация о товаре:\n{product_context}\n"
            rating_context_block = ""
            if rating_context:
                rating_context_block = f"\n{rating_context}\n"
            system_prompt = CHAT_ANALYSIS_SYSTEM
            user_prompt = CHAT_ANALYSIS_USER.format(
                product_name=product_name,
                messages_block=messages_block,
                product_context_block=product_context_block,
                rating_context_block=rating_context_block,
            )

        client = _get_shared_client()
        max_tokens = _select_max_tokens(
            channel="chat",  # default; callers can refine later
        )
        t_start = time.monotonic()
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()

            elapsed = time.monotonic() - t_start
            data = response.json()

            # Log timing and token usage for monitoring
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            logger.info(
                "LLM response in %.1fs | model=%s | tokens: prompt=%d completion=%d total=%d | max_tokens=%d",
                elapsed,
                self.model_name,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                max_tokens,
            )

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return json.loads(content) if content else None

        except httpx.HTTPStatusError as e:
            elapsed = time.monotonic() - t_start
            logger.error(
                "DeepSeek API error: status=%s elapsed=%.1fs",
                e.response.status_code,
                elapsed,
            )
            return None
        except json.JSONDecodeError as e:
            elapsed = time.monotonic() - t_start
            logger.error("Failed to parse LLM response: %s elapsed=%.1fs", e, elapsed)
            return None
        except Exception as e:
            elapsed = time.monotonic() - t_start
            logger.error("LLM call failed: %s elapsed=%.1fs", e, elapsed)
            return None

    def _format_messages(self, messages: List[Dict], customer_name: Optional[str]) -> str:
        """Format messages for prompt."""
        lines = []
        for msg in messages[-10:]:  # Last 10 messages
            author = "Покупатель" if msg.get("author_type") == "buyer" else "Продавец"
            if msg.get("author_type") == "buyer" and customer_name:
                author = customer_name

            text = msg.get("text", "").strip()
            if not text:
                continue

            created_at = msg.get("created_at")
            if isinstance(created_at, datetime):
                time_str = created_at.strftime("%d.%m %H:%M")
            else:
                time_str = str(created_at)[:16] if created_at else ""

            lines.append(f"[{time_str}] {author}: {text}")

        return "\n".join(lines)

    def _parse_response(self, response: Dict) -> Dict:
        """Parse and validate LLM response."""
        return {
            "intent": response.get("intent", "other"),
            "sentiment": response.get("sentiment", "neutral"),
            "urgency": response.get("urgency", "normal"),
            "categories": response.get("categories", []),
            "recommendation": response.get("recommendation"),
            "recommendation_reason": response.get("recommendation_reason"),
            "needs_escalation": response.get("needs_escalation", False),
            "escalation_reason": response.get("escalation_reason"),
        }

    def _apply_guardrails(
        self,
        text: str,
        customer_name: Optional[str] = None,
        channel: str = "chat",
    ) -> str:
        """Apply guardrails to recommendation text.

        Uses ``replace_banned_phrases()`` from the guardrails module (single
        source of truth) and applies channel-aware truncation.
        """
        if not text:
            return text

        # Replace banned phrases using guardrails module (single source of truth)
        result = replace_banned_phrases(text)

        # Normalize greeting: strip any existing greeting, re-add with proper first name
        # This prevents: surname greetings ("Курченко, здравствуйте!"),
        # double greetings, and missing greetings
        result = re.sub(
            r'^[А-ЯЁа-яё\s,]+здравствуйте!?\s*',
            '', result, count=1, flags=re.IGNORECASE
        )
        result = re.sub(
            r'^Здравствуйте!?\s*',
            '', result, count=1, flags=re.IGNORECASE
        )
        result = re.sub(
            r'^Добрый\s+(день|вечер|утро)!?\s*',
            '', result, count=1, flags=re.IGNORECASE
        )
        result = result.strip()

        first_name = extract_first_name(customer_name)
        if first_name:
            result = f"{first_name}, здравствуйте! {result}"
        else:
            result = f"Здравствуйте! {result}"

        # Channel-aware truncation
        max_len = get_max_length(channel)
        if len(result) > max_len:
            # Find last sentence boundary within limit
            cut_point = result[:max_len - 3].rfind('.')
            if cut_point > max_len // 2:
                result = result[:cut_point + 1]
            else:
                result = result[:max_len - 3] + "..."

        return result

    def _check_escalation_keywords(self, messages: List[Dict]) -> Optional[str]:
        """Check for escalation keywords in messages."""
        all_text = " ".join(
            msg.get("text", "").lower()
            for msg in messages
            if msg.get("author_type") == "buyer"
        )

        for category, keywords in ESCALATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in all_text:
                    return f"Обнаружено: {keyword} (категория: {category})"

        return None

    def _calculate_sla_priority(
        self,
        intent: str,
        urgency: str,
        messages: List[Dict],
        sla_config: Optional[Dict] = None,
    ) -> str:
        """Calculate SLA priority based on intent, urgency, and message patterns.

        Args:
            intent: Classified intent string.
            urgency: LLM-reported urgency level.
            messages: List of message dicts.
            sla_config: Optional seller-specific SLA config dict. If provided,
                intent priority is looked up from ``sla_config["intents"]``
                instead of the module-level ``SLA_PRIORITIES`` constant.
        """
        if sla_config and isinstance(sla_config, dict):
            intents_cfg = sla_config.get("intents", {})
            intent_entry = intents_cfg.get(intent, {})
            base_priority = intent_entry.get("priority", SLA_PRIORITIES.get(intent, "normal"))
        else:
            base_priority = SLA_PRIORITIES.get(intent, "normal")

        # Check for repeated messages (escalation)
        buyer_messages = [m for m in messages if m.get("author_type") == "buyer"]
        if len(buyer_messages) >= 3:
            # Multiple messages = frustration
            if base_priority == "normal":
                base_priority = "high"
            elif base_priority == "high":
                base_priority = "urgent"

        # Check for caps / exclamation (anger)
        last_buyer_msg = next(
            (m for m in reversed(messages) if m.get("author_type") == "buyer"),
            None
        )
        if last_buyer_msg:
            text = last_buyer_msg.get("text", "")
            caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
            exclaim_count = text.count("!")

            if caps_ratio > 0.5 or exclaim_count >= 3:
                if base_priority == "normal":
                    base_priority = "high"
                elif base_priority == "high":
                    base_priority = "urgent"

        # Override with explicit urgency if higher
        if urgency == "critical":
            base_priority = "urgent"
        elif urgency == "high" and base_priority not in ["urgent"]:
            base_priority = "high"

        return base_priority

    @staticmethod
    def _resolve_intent_priority(intent: str, sla_config: Optional[Dict] = None) -> str:
        """Resolve base priority for an intent, using sla_config if available."""
        if sla_config and isinstance(sla_config, dict):
            intents_cfg = sla_config.get("intents", {})
            intent_entry = intents_cfg.get(intent, {})
            if isinstance(intent_entry, dict) and "priority" in intent_entry:
                return intent_entry["priority"]
        return SLA_PRIORITIES.get(intent, "normal")

    def _fallback_analysis(
        self,
        messages: List[Dict],
        customer_name: Optional[str],
        sla_config: Optional[Dict] = None,
    ) -> Dict:
        """Fallback analysis when LLM is unavailable."""
        # Simple heuristics
        all_text = " ".join(
            msg.get("text", "").lower()
            for msg in messages
            if msg.get("author_type") == "buyer"
        )

        # Detect intent by keywords
        intent = "other"
        if any(w in all_text for w in ["где заказ", "где товар", "когда доставят"]):
            intent = "delivery_status"
        elif any(w in all_text for w in ["сломан", "не работает", "брак", "дефект"]):
            intent = "defect_not_working"
        elif any(w in all_text for w in ["не тот", "другой", "прислали не то"]):
            intent = "wrong_item"
        elif any(w in all_text for w in RETURN_TRIGGER_WORDS):
            intent = "refund_exchange"
        elif any(w in all_text for w in ["отменить", "отмена"]):
            intent = "cancel_request"
        elif any(w in all_text for w in ["спасибо", "благодар"]):
            intent = "thanks"
        # Pre-purchase intents (HIGH priority!)
        elif any(w in all_text for w in ["какой размер", "посоветуйте размер", "на какой рост", "на какой вес"]):
            intent = "sizing_fit"
        elif any(w in all_text for w in ["есть в наличии", "когда будет", "будет ли"]):
            intent = "availability"
        elif any(w in all_text for w in ["подойдёт ли", "подойдет ли", "совместим", "подходит к"]):
            intent = "compatibility"
        elif any(w in all_text for w in ["хочу купить", "собираюсь брать", "думаю взять", "стоит ли брать"]):
            intent = "pre_purchase"
        elif any(w in all_text for w in ["как", "размер", "характеристик"]):
            intent = "usage_howto"

        # Detect sentiment
        sentiment = "neutral"
        if any(w in all_text for w in ["плохо", "ужас", "кошмар", "разочарован"]):
            sentiment = "negative"
        elif any(w in all_text for w in ["отлично", "спасибо", "супер", "класс"]):
            sentiment = "positive"

        # Generate fallback recommendation
        first_name = extract_first_name(customer_name)
        name_prefix = f"{first_name}, здравствуйте! " if first_name else "Здравствуйте! "

        recommendations = {
            "delivery_status": f"{name_prefix}Проверили ваш заказ — со своей стороны товар отгружен. Отслеживайте статус в ЛК WB.",
            "delivery_delay": f"{name_prefix}Понимаем, ожидание затянулось. Со своей стороны проверили — товар передан в доставку.",
            "defect_not_working": f"{name_prefix}Нам очень жаль! Оформите возврат через ЛК WB. Передали информацию в отдел качества.",
            "wrong_item": f"{name_prefix}Приносим извинения! Оформите возврат через ЛК WB с пометкой «не соответствует описанию».",
            "refund_exchange": f"{name_prefix}Оформить возврат можно в ЛК WB: раздел Покупки → Оформить возврат.",
            "cancel_request": f"{name_prefix}Вы можете отменить заказ в ЛК WB: раздел Доставки → Отменить.",
            "thanks": f"{name_prefix}Рады помочь! Если возникнут вопросы — обращайтесь.",
            "usage_howto": f"{name_prefix}Подскажите, пожалуйста, какой именно вопрос у вас возник?",
            # Pre-purchase recommendations
            "sizing_fit": f"{name_prefix}Подскажите ваши параметры (рост, вес), и мы поможем с выбором размера!",
            "availability": f"{name_prefix}Уточняем наличие, напишем вам в ближайшее время!",
            "compatibility": f"{name_prefix}Уточните, пожалуйста, модель вашего устройства, и мы проверим совместимость.",
            "pre_purchase": f"{name_prefix}Будем рады помочь с выбором! Какой вопрос у вас возник?",
            "other": f"{name_prefix}Подскажите, что именно произошло? Мы постараемся помочь!",
        }

        return {
            "intent": intent,
            "sentiment": sentiment,
            "urgency": "normal",
            "categories": [],
            "recommendation": recommendations.get(intent, recommendations["other"]),
            "recommendation_reason": "Fallback: LLM unavailable",
            "needs_escalation": False,
            "escalation_reason": None,
            "sla_priority": self._resolve_intent_priority(intent, sla_config),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }


async def _get_seller_tone(db_session, seller_id: int) -> str:
    """Read seller's tone preference from AI settings in DB.

    Returns 'neutral' if not configured.
    """
    try:
        from sqlalchemy import select
        from app.models.runtime_setting import RuntimeSetting

        key = f"ai_settings_v1:seller:{seller_id}"
        result = await db_session.execute(
            select(RuntimeSetting).where(RuntimeSetting.key == key)
        )
        record = result.scalar_one_or_none()
        if record and record.value:
            import json as _json
            payload = _json.loads(record.value)
            settings_obj = payload.get("settings", {}) if isinstance(payload, dict) else {}
            tone = settings_obj.get("tone", "neutral")
            if tone in ("formal", "friendly", "neutral"):
                return tone
    except Exception as exc:
        logger.debug("Failed to read seller tone: %s", exc)

    return "neutral"


async def analyze_chat_for_db(chat_id: int, db_session) -> Optional[Dict]:
    """
    Analyze chat and update database.

    Args:
        chat_id: Chat ID
        db_session: AsyncSession

    Returns:
        Analysis dict or None
    """
    from sqlalchemy import select
    from app.models.chat import Chat
    from app.models.message import Message
    from app.services.llm_runtime import get_llm_runtime_config

    # Get chat
    result = await db_session.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        logger.warning(f"Chat {chat_id} not found")
        return None

    # Get messages
    msg_result = await db_session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.sent_at.asc())
    )
    messages = msg_result.scalars().all()

    if not messages:
        logger.debug(f"No messages in chat {chat_id}")
        return None

    # Convert to dicts
    messages_data = [
        {
            "text": m.text,
            "author_type": m.author_type,
            "created_at": m.sent_at,
        }
        for m in messages
    ]

    # Read seller tone preference
    tone = await _get_seller_tone(db_session, chat.seller_id)

    # Read seller SLA config (configurable priority thresholds)
    from app.services.sla_config import get_sla_config
    sla_config = await get_sla_config(db_session, chat.seller_id)

    # Analyze
    llm_runtime = await get_llm_runtime_config(db_session)
    analyzer = AIAnalyzer(
        provider=llm_runtime.provider,
        model_name=llm_runtime.model_name,
        enabled=llm_runtime.enabled,
    )
    analysis = await analyzer.analyze_chat(
        messages=messages_data,
        product_name=chat.product_name,
        customer_name=chat.customer_name,
        channel="chat",
        tone=tone,
        sla_config=sla_config,
    )

    if analysis:
        # Update chat with analysis
        import json
        chat.ai_analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
        chat.ai_suggestion_text = analysis.get("recommendation")

        # Update SLA priority if not manually set
        if chat.sla_priority == "normal":
            chat.sla_priority = analysis.get("sla_priority", "normal")

        await db_session.commit()
        logger.info(f"Updated chat {chat_id} with AI analysis")

    return analysis
