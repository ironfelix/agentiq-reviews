"""Channel-specific guardrails for public replies.

**Single source of truth** for all banned phrases, replacements,
and length constraints across the application.

Ported from scripts/llm_analyzer.py GUARDRAILS config (lines 478-519).
Provides pre-send validation and draft-time warnings for review, question,
and chat channels.

Key rules:
- Return/refund: ONLY mention if buyer explicitly asked.
- AI/bot mentions: NEVER in any channel.
- Promises (returns, refunds): NEVER in public channels.
- Blame phrases: NEVER in any channel.
- Dismissive phrases: NEVER in public channels.
- Chat channel is more relaxed (private), but AI mentions still banned.
- Auto-responses have STRICTER guardrails (see validate_auto_response).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Banned phrase lists (detection)
# ---------------------------------------------------------------------------

BANNED_PHRASES_COMMON: List[str] = [
    "ИИ",
    "бот",
    "нейросеть",
    "GPT",
    "ChatGPT",
    "автоматический ответ",
    "искусственный интеллект",
    "нейронная сеть",
]

BANNED_PHRASES_PROMISES: List[str] = [
    "вернём деньги",
    "вернем деньги",
    "гарантируем возврат",
    "гарантируем замену",
    "полный возврат",
    "бесплатную замену",
    "бесплатная замена",
    "компенсируем",
    "компенсация",
    "мы одобрим возврат",
    "мы одобрим заявку",
    "доставим завтра",
    "отменим ваш заказ",
    "ускорим доставку",
]

BANNED_PHRASES_BLAME: List[str] = [
    "вы неправильно",
    "вы не так",
    "ваша вина",
    "сами виноваты",
    "вы ошиблись",
    "ваша ошибка",
]

BANNED_PHRASES_DISMISSIVE: List[str] = [
    "обратитесь в поддержку",
    "напишите в поддержку",
    "мы не можем повлиять",
]

BANNED_PHRASES_LEGAL: List[str] = [
    "характеристики не соответствуют",
    "наша ошибка",
    "мы виноваты",
]

BANNED_PHRASES_JARGON: List[str] = [
    "уважаемый клиент",
    "уважаемый покупатель",
    "пересорт",
    "FBO",
    "FBS",
    "SKU",
]

# ---------------------------------------------------------------------------
# Banned phrases with safe replacements (used by post-generation cleanup)
# ---------------------------------------------------------------------------

BANNED_PHRASE_REPLACEMENTS: Dict[str, str] = {
    # False Authority (Group A) — promises
    "вернём деньги": "Оформите возврат через ЛК WB",
    "вернем деньги": "Оформите возврат через ЛК WB",
    "гарантируем возврат": "Оформите возврат через ЛК WB",
    "гарантируем замену": "Оформите возврат через ЛК WB",
    "мы одобрим возврат": "Оформите возврат через ЛК WB",
    "мы одобрим заявку": "Оформите возврат через ЛК WB",
    "полный возврат": "возврат через ЛК WB",
    "бесплатную замену": "возврат через ЛК WB",
    "бесплатная замена": "возврат через ЛК WB",
    "доставим завтра": "Со своей стороны товар отгружен",
    "отменим ваш заказ": "Вы можете отменить заказ в ЛК WB",
    "ускорим доставку": "Со своей стороны товар отгружен",

    # Blame (forbidden) — remove
    "вы неправильно": "",
    "вы не так": "",
    "ваша вина": "",
    "сами виноваты": "",

    # Dismissive — replace
    "обратитесь в поддержку": "Мы со своей стороны проверим ситуацию",
    "напишите в поддержку": "Мы со своей стороны проверим ситуацию",
    "мы не можем повлиять": "Со своей стороны мы передали информацию",

    # Legal admissions (Group C) — soften
    "характеристики не соответствуют": "возможен дефект конкретного экземпляра",
    "наша ошибка": "нештатная ситуация, разбираемся",
    "мы виноваты": "нештатная ситуация, разбираемся",

    # AI/bot mentions (Group B) — remove
    "ИИ": "",
    "бот": "",
    "нейросеть": "",
    "GPT": "",
    "ChatGPT": "",
    "автоматический ответ": "",

    # Internal jargon — translate
    "пересорт": "прислали не тот товар",
    "FBO": "склад WB",
    "FBS": "склад продавца",
    "SKU": "артикул",

    # Formal/bureaucratic — remove
    "уважаемый клиент": "",
    "уважаемый покупатель": "",
}

# Return trigger words (customer side)
RETURN_TRIGGER_WORDS: List[str] = [
    "возврат",
    "вернуть",
    "замена",
    "заменить",
    "обменять",
    "обмен",
]

# Reply mentions return/refund (seller side)
RETURN_MENTION_PATTERNS: List[str] = [
    "возврат",
    "вернуть",
    "вернём",
    "вернем",
    "замен",
    "обмен",
]

# ---------------------------------------------------------------------------
# Auto-response STRICTER banned patterns (substring match)
# ---------------------------------------------------------------------------
# Auto-responses are sent WITHOUT human review and must be extra-safe.
# These patterns use substring matching (case-insensitive) for broader coverage.

AUTO_RESPONSE_BANNED_PATTERNS: List[str] = [
    # --- All existing banned phrases (substring form) ---
    # AI/bot mentions
    "ИИ",
    "бот",
    "нейросеть",
    "GPT",
    "ChatGPT",
    "автоматический ответ",
    "искусственный интеллект",
    "нейронная сеть",
    # Promises
    "вернём деньги",
    "вернем деньги",
    "гарантируем возврат",
    "гарантируем замену",
    "полный возврат",
    "бесплатную замену",
    "бесплатная замена",
    "мы одобрим возврат",
    "мы одобрим заявку",
    "доставим завтра",
    "отменим ваш заказ",
    "ускорим доставку",
    # Blame
    "вы неправильно",
    "вы не так",
    "ваша вина",
    "сами виноваты",
    "вы ошиблись",
    "ваша ошибка",
    # Dismissive
    "обратитесь в поддержку",
    "напишите в поддержку",
    "мы не можем повлиять",
    # Legal
    "характеристики не соответствуют",
    "наша ошибка",
    "мы виноваты",
    # Jargon
    "уважаемый клиент",
    "уважаемый покупатель",
    "пересорт",
    "FBO",
    "FBS",
    "SKU",
    # --- ADDITIONAL auto-response-specific patterns ---
    "компенсац",        # компенсация/компенсируем
    "скидк",            # скидка (unless promo context, checked separately)
    "бесплатн",         # бесплатная доставка/замена
    "гарантир",         # гарантируем
    "100%",
    "обещ",             # обещаем
    "точно",            # overpromising
    "обязательно",      # overpromising
    "к сожалению",      # negative framing in positive response
    # Competitors
    "Ozon",
    "СДЭК",
    "Яндекс Маркет",
    "AliExpress",
    "Lamoda",
]

# Regex patterns for auto-response (URLs, emails, phone numbers)
AUTO_RESPONSE_BANNED_REGEX: List[re.Pattern] = [
    re.compile(r"https?://", re.IGNORECASE),                         # URLs
    re.compile(r"www\.", re.IGNORECASE),                              # URLs without scheme
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # Email addresses
    re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),  # Phone numbers
]

# Auto-response length limits (stricter than general limits)
AUTO_RESPONSE_MAX_LENGTH_REVIEW = 500
AUTO_RESPONSE_MAX_LENGTH_QUESTION = 800
AUTO_RESPONSE_MAX_LENGTH_CHAT = 1000


def get_auto_response_max_length(channel: str) -> int:
    """Return the maximum auto-response length for a given channel."""
    if channel == "question":
        return AUTO_RESPONSE_MAX_LENGTH_QUESTION
    if channel == "chat":
        return AUTO_RESPONSE_MAX_LENGTH_CHAT
    return AUTO_RESPONSE_MAX_LENGTH_REVIEW  # review or unknown


# ---------------------------------------------------------------------------
# Channel-specific length constraints (matching WB API limits)
# ---------------------------------------------------------------------------

REPLY_MAX_LENGTH_REVIEW = 500
REPLY_MAX_LENGTH_QUESTION = 500
REPLY_MAX_LENGTH_CHAT = 1000
REPLY_MIN_LENGTH = 20

# Legacy alias for backwards compatibility (used by validate_reply_text)
REPLY_MAX_LENGTH = 500


def get_max_length(channel: str) -> int:
    """Return the maximum reply length for a given channel."""
    if channel == "chat":
        return REPLY_MAX_LENGTH_CHAT
    return REPLY_MAX_LENGTH_REVIEW  # review, question, unknown


# ---------------------------------------------------------------------------
# Low-level checks
# ---------------------------------------------------------------------------

def _compile_pattern(phrase: str) -> re.Pattern:
    """Build a case-insensitive word-boundary pattern for a phrase.

    For short tokens like 'ИИ' or 'бот' we require word boundaries so that
    'работа' does not match 'бот'.  For multi-word phrases the surrounding
    context naturally provides boundaries.
    """
    escaped = re.escape(phrase)
    # For single-word tokens use word boundaries
    if " " not in phrase:
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def check_banned_phrases(
    text: str,
    phrase_lists: Optional[Dict[str, List[str]]] = None,
) -> List[Dict]:
    """Return list of violation dicts found in *text*.

    Each violation: ``{"phrase": <matched>, "category": <category_name>}``.
    If *phrase_lists* is ``None`` all categories are checked.
    """
    if not text:
        return []

    if phrase_lists is None:
        phrase_lists = {
            "ai_mention": BANNED_PHRASES_COMMON,
            "promise": BANNED_PHRASES_PROMISES,
            "blame": BANNED_PHRASES_BLAME,
            "dismissive": BANNED_PHRASES_DISMISSIVE,
        }

    violations: List[Dict] = []
    for category, phrases in phrase_lists.items():
        for phrase in phrases:
            pattern = _compile_pattern(phrase)
            if pattern.search(text):
                violations.append({"phrase": phrase, "category": category})
    return violations


def has_return_trigger(customer_text: str) -> bool:
    """Check whether the customer explicitly asked for return/refund."""
    if not customer_text:
        return False
    lower = customer_text.lower()
    return any(word in lower for word in RETURN_TRIGGER_WORDS)


def check_return_mention_without_trigger(
    reply_text: str,
    customer_text: str,
) -> bool:
    """Return True if *reply_text* mentions return/refund but customer did NOT ask.

    This is a guardrail violation: we must not proactively suggest returns
    unless the buyer brought it up.
    """
    if not reply_text:
        return False
    if has_return_trigger(customer_text or ""):
        return False  # customer asked — it is fine to mention

    lower_reply = reply_text.lower()
    return any(word in lower_reply for word in RETURN_MENTION_PATTERNS)


# ---------------------------------------------------------------------------
# Post-generation text cleanup (replacement of banned phrases)
# ---------------------------------------------------------------------------

def replace_banned_phrases(text: str) -> str:
    """Replace known banned phrases with safe alternatives.

    This is a post-generation cleanup step that modifies the text in place.
    Phrases with empty replacement are removed (with surrounding whitespace
    collapsed).  Returns the cleaned text.
    """
    if not text:
        return text

    result = text

    for phrase, replacement in BANNED_PHRASE_REPLACEMENTS.items():
        if phrase.lower() in result.lower():
            if replacement:
                result = re.sub(
                    re.escape(phrase),
                    replacement,
                    result,
                    flags=re.IGNORECASE,
                )
            else:
                result = re.sub(
                    r'\s*' + re.escape(phrase) + r'\s*',
                    ' ',
                    result,
                    flags=re.IGNORECASE,
                )

    # Clean up double spaces
    result = re.sub(r'\s+', ' ', result).strip()
    return result


# ---------------------------------------------------------------------------
# Channel-specific guardrail functions
# ---------------------------------------------------------------------------

def apply_review_guardrails(
    draft_text: str,
    customer_text: str = "",
) -> Tuple[str, List[Dict]]:
    """Apply strictest guardrails for PUBLIC review replies.

    Returns ``(text, warnings)`` where *warnings* is a list of dicts.
    The text is returned unchanged (we warn, not block at draft stage).
    """
    warnings: List[Dict] = []
    if not draft_text:
        return draft_text, warnings

    max_len = REPLY_MAX_LENGTH_REVIEW

    # All banned phrase categories
    violations = check_banned_phrases(draft_text)
    for v in violations:
        warnings.append({
            "type": "banned_phrase",
            "severity": "error",
            "message": f"Запрещённая фраза: \"{v['phrase']}\" (категория: {v['category']})",
            "phrase": v["phrase"],
            "category": v["category"],
        })

    # Return mention without trigger
    if check_return_mention_without_trigger(draft_text, customer_text):
        warnings.append({
            "type": "unsolicited_return",
            "severity": "error",
            "message": "Упоминание возврата/замены без запроса от покупателя",
        })

    # Length checks
    if len(draft_text) > max_len:
        warnings.append({
            "type": "too_long",
            "severity": "warning",
            "message": f"Ответ слишком длинный ({len(draft_text)} > {max_len} символов)",
        })
    if len(draft_text) < REPLY_MIN_LENGTH:
        warnings.append({
            "type": "too_short",
            "severity": "warning",
            "message": f"Ответ слишком короткий ({len(draft_text)} < {REPLY_MIN_LENGTH} символов)",
        })

    return draft_text, warnings


def apply_question_guardrails(
    draft_text: str,
    customer_text: str = "",
) -> Tuple[str, List[Dict]]:
    """Apply strict guardrails for PUBLIC question replies.

    Same banned phrase rules as review. Uses question-specific length limit.
    """
    warnings: List[Dict] = []
    if not draft_text:
        return draft_text, warnings

    max_len = REPLY_MAX_LENGTH_QUESTION

    # All banned phrase categories
    violations = check_banned_phrases(draft_text)
    for v in violations:
        warnings.append({
            "type": "banned_phrase",
            "severity": "error",
            "message": f"Запрещённая фраза: \"{v['phrase']}\" (категория: {v['category']})",
            "phrase": v["phrase"],
            "category": v["category"],
        })

    # Return mention without trigger
    if check_return_mention_without_trigger(draft_text, customer_text):
        warnings.append({
            "type": "unsolicited_return",
            "severity": "error",
            "message": "Упоминание возврата/замены без запроса от покупателя",
        })

    # Length checks
    if len(draft_text) > max_len:
        warnings.append({
            "type": "too_long",
            "severity": "warning",
            "message": f"Ответ слишком длинный ({len(draft_text)} > {max_len} символов)",
        })
    if len(draft_text) < REPLY_MIN_LENGTH:
        warnings.append({
            "type": "too_short",
            "severity": "warning",
            "message": f"Ответ слишком короткий ({len(draft_text)} < {REPLY_MIN_LENGTH} символов)",
        })

    return draft_text, warnings


def apply_chat_guardrails(
    draft_text: str,
    customer_text: str = "",
) -> Tuple[str, List[Dict]]:
    """Apply relaxed guardrails for PRIVATE chat replies.

    Only AI-mention bans apply.  Returns and refund discussion is more freely
    allowed in private chats.  Blame and dismissive phrases still warn but at
    lower severity.
    """
    warnings: List[Dict] = []
    if not draft_text:
        return draft_text, warnings

    max_len = REPLY_MAX_LENGTH_CHAT

    # AI mentions are banned everywhere
    ai_violations = check_banned_phrases(
        draft_text,
        phrase_lists={"ai_mention": BANNED_PHRASES_COMMON},
    )
    for v in ai_violations:
        warnings.append({
            "type": "banned_phrase",
            "severity": "error",
            "message": f"Запрещённая фраза: \"{v['phrase']}\" (категория: {v['category']})",
            "phrase": v["phrase"],
            "category": v["category"],
        })

    # Blame phrases are soft warnings in chat
    blame_violations = check_banned_phrases(
        draft_text,
        phrase_lists={"blame": BANNED_PHRASES_BLAME},
    )
    for v in blame_violations:
        warnings.append({
            "type": "banned_phrase",
            "severity": "warning",
            "message": f"Нежелательная фраза: \"{v['phrase']}\" (категория: {v['category']})",
            "phrase": v["phrase"],
            "category": v["category"],
        })

    # Length checks
    if len(draft_text) > max_len:
        warnings.append({
            "type": "too_long",
            "severity": "warning",
            "message": f"Ответ слишком длинный ({len(draft_text)} > {max_len} символов)",
        })

    return draft_text, warnings


# ---------------------------------------------------------------------------
# Unified apply function
# ---------------------------------------------------------------------------

def apply_guardrails(
    draft_text: str,
    channel: str,
    customer_text: str = "",
) -> Tuple[str, List[Dict]]:
    """Apply channel-appropriate guardrails and return ``(text, warnings)``."""
    if channel == "review":
        return apply_review_guardrails(draft_text, customer_text)
    elif channel == "question":
        return apply_question_guardrails(draft_text, customer_text)
    elif channel == "chat":
        return apply_chat_guardrails(draft_text, customer_text)
    else:
        # Unknown channel: apply strictest (review) rules to be safe
        return apply_review_guardrails(draft_text, customer_text)


# ---------------------------------------------------------------------------
# Pre-send validation (blocking)
# ---------------------------------------------------------------------------

def validate_reply_text(
    text: str,
    channel: str,
    customer_text: str = "",
) -> Dict:
    """Validate reply text before sending.

    This is the ONLY blocking check: if ``valid`` is False the reply API
    endpoint should reject the send.

    Returns::

        {
            "valid": bool,
            "violations": [...]   # blocking errors
            "warnings": [...]     # non-blocking advisories
        }
    """
    result: Dict = {"valid": True, "violations": [], "warnings": []}

    if not text or not text.strip():
        result["valid"] = False
        result["violations"].append({
            "type": "empty_text",
            "message": "Текст ответа не может быть пустым",
        })
        return result

    text = text.strip()

    # Apply channel guardrails
    _, all_warnings = apply_guardrails(text, channel, customer_text)

    for w in all_warnings:
        if w.get("severity") == "error":
            result["violations"].append(w)
        else:
            result["warnings"].append(w)

    # Block only on violations (errors)
    if result["violations"]:
        result["valid"] = False

    return result


# ---------------------------------------------------------------------------
# Auto-response stricter validation (TASK 1)
# ---------------------------------------------------------------------------

def _check_auto_response_banned_patterns(text: str) -> List[str]:
    """Check text against the stricter auto-response banned patterns.

    Returns a list of reason strings for each violation found.
    Uses word-boundary matching for short tokens (same as _compile_pattern)
    and substring matching for longer patterns.
    """
    reasons: List[str] = []
    if not text:
        return reasons

    for pattern_str in AUTO_RESPONSE_BANNED_PATTERNS:
        pat = _compile_pattern(pattern_str)
        if pat.search(text):
            reasons.append(f"Запрещённый паттерн для автоответа: \"{pattern_str}\"")

    # Regex patterns (URLs, emails, phones)
    for regex in AUTO_RESPONSE_BANNED_REGEX:
        if regex.search(text):
            reasons.append(f"Запрещённый паттерн: {regex.pattern}")

    return reasons


def _check_auto_response_length(text: str, channel: str) -> List[str]:
    """Check auto-response text length against channel-specific limits.

    Returns a list of reason strings if the length exceeds the limit.
    """
    max_len = get_auto_response_max_length(channel)
    if len(text) > max_len:
        return [f"Автоответ слишком длинный ({len(text)} > {max_len} символов для канала '{channel}')"]
    if len(text) < REPLY_MIN_LENGTH:
        return [f"Автоответ слишком короткий ({len(text)} < {REPLY_MIN_LENGTH} символов)"]
    return []


def _check_language_russian(text: str) -> List[str]:
    """Check that the response is predominantly in Russian (Cyrillic).

    Returns a list of reason strings if non-Cyrillic characters dominate.
    """
    if not text:
        return []

    # Count Cyrillic vs Latin alphabetic characters
    cyrillic_count = 0
    latin_count = 0
    for ch in text:
        if "\u0400" <= ch <= "\u04ff" or "\u0500" <= ch <= "\u052f":
            cyrillic_count += 1
        elif ch.isalpha():
            latin_count += 1

    total_alpha = cyrillic_count + latin_count
    if total_alpha == 0:
        return []  # No alphabetic characters (e.g. emojis only)

    cyrillic_ratio = cyrillic_count / total_alpha
    if cyrillic_ratio < 0.7:
        return [
            f"Ответ не на русском языке (кириллица: {cyrillic_ratio:.0%}, "
            f"порог: 70%)"
        ]
    return []


async def _check_repetition(
    text: str,
    seller_id: int,
    db,
) -> List[str]:
    """Check if the exact same text was sent to this seller in the last 24h.

    Prevents copy-paste repetition in auto-responses.
    Returns a list of reason strings if a duplicate is found.
    """
    from sqlalchemy import select, and_
    from app.models.interaction import Interaction

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        result = await db.execute(
            select(Interaction.id).where(
                and_(
                    Interaction.seller_id == seller_id,
                    Interaction.is_auto_response == True,
                    Interaction.updated_at >= cutoff,
                )
            ).limit(200)
        )
        interaction_ids = [row[0] for row in result.all()]

        if not interaction_ids:
            return []

        # Check extra_data for matching reply text
        from app.models.interaction import Interaction as InteractionModel
        result2 = await db.execute(
            select(InteractionModel).where(
                InteractionModel.id.in_(interaction_ids)
            )
        )
        interactions = result2.scalars().all()
        normalized_text = text.strip().lower()
        for interaction in interactions:
            if isinstance(interaction.extra_data, dict):
                last_reply = interaction.extra_data.get("last_reply_text", "")
                if last_reply and last_reply.strip().lower() == normalized_text:
                    return [
                        f"Дублирование: такой же текст уже был отправлен "
                        f"(interaction_id={interaction.id}) за последние 24ч"
                    ]
    except Exception as exc:
        logger.warning("auto_response repetition check failed: %s", exc)
        # Non-blocking: if DB check fails, allow the response
        return []

    return []


async def validate_auto_response(
    text: str,
    channel: str,
    seller_id: int,
    db,
) -> Tuple[bool, List[str]]:
    """Run ALL stricter checks for auto-responses.

    Auto-responses are sent WITHOUT human review, so they must be extra-safe.

    Checks:
    a) Stricter banned phrase patterns (including overpromising, competitors, etc.)
    b) Channel-specific max length (500/800/1000)
    c) Repetition check (same text to same seller in last 24h)
    d) Language check (must be predominantly Russian/Cyrillic)

    Args:
        text: The auto-response text to validate.
        channel: The channel (review, question, chat).
        seller_id: The seller's ID for repetition checks.
        db: AsyncSession for DB queries.

    Returns:
        Tuple of (is_safe, list_of_reasons_if_blocked).
        If is_safe is True, the list is empty.
    """
    if not text or not text.strip():
        return False, ["Текст автоответа пуст"]

    text = text.strip()
    all_reasons: List[str] = []

    # a) Stricter banned patterns
    all_reasons.extend(_check_auto_response_banned_patterns(text))

    # b) Length check
    all_reasons.extend(_check_auto_response_length(text, channel))

    # c) Repetition check (async, requires DB)
    repetition_reasons = await _check_repetition(text, seller_id, db)
    all_reasons.extend(repetition_reasons)

    # d) Language check
    all_reasons.extend(_check_language_russian(text))

    is_safe = len(all_reasons) == 0
    return is_safe, all_reasons
