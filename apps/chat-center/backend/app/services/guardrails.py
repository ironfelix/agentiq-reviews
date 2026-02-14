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
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

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
