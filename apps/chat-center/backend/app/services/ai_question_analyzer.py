"""LLM-based question intent classification.

Provides a hybrid approach: rule-based detection first (fast, free),
with LLM fallback when rule-based returns ``general_question``.

The LLM call is optional (controlled by ``ENABLE_LLM_INTENT`` config flag),
has a strict 5-second timeout, and never blocks ingestion on failure.
"""

from __future__ import annotations

import logging
from typing import Optional, Set

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Valid intent values (must match _question_intent rule-based output)
VALID_INTENTS: Set[str] = {
    "sizing_fit",
    "availability_delivery",
    "spec_compatibility",
    "compliance_safety",
    "post_purchase_issue",
    "general_question",
}

INTENT_CLASSIFICATION_PROMPT = """Классифицируй вопрос покупателя на маркетплейсе Wildberries.

Вопрос: "{question_text}"

Возможные интенты (выбери ОДИН):
- sizing_fit — вопрос про размер, рост, вес, подойдёт ли по фигуре
- availability_delivery — наличие, когда будет, сроки доставки, поступление
- spec_compatibility — характеристики, материал, состав, совместимость, мощность
- compliance_safety — сертификаты, аллергия, безопасность, гарантия
- post_purchase_issue — брак, не работает, сломалось, возврат
- general_question — прочее, не подходит ни к одной категории

Ответь ТОЛЬКО названием интента, без объяснений."""

# LLM call timeout in seconds
_LLM_TIMEOUT_SECONDS = 5.0


async def classify_question_intent_llm(
    question_text: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """Classify question intent using LLM (DeepSeek / OpenAI-compatible API).

    Returns:
        Intent string if classification succeeded, ``None`` on any failure.
    """
    settings = get_settings()
    resolved_key = api_key or settings.DEEPSEEK_API_KEY
    resolved_url = base_url or settings.DEEPSEEK_BASE_URL
    resolved_model = model or "deepseek-chat"

    if not resolved_key:
        logger.debug("LLM intent classification skipped: no API key configured")
        return None

    prompt = INTENT_CLASSIFICATION_PROMPT.format(question_text=question_text)

    try:
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{resolved_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {resolved_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": resolved_model,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 30,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .lower()
                .replace(".", "")
                .replace('"', "")
                .replace("'", "")
                .strip()
            )

            if content in VALID_INTENTS:
                return content

            logger.warning(
                "LLM returned unknown intent %r for question (first 80 chars): %s",
                content,
                question_text[:80],
            )
            return None

    except httpx.TimeoutException:
        logger.warning("LLM intent classification timed out (%.1fs)", _LLM_TIMEOUT_SECONDS)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("LLM intent classification HTTP error: %s", exc.response.status_code)
        return None
    except Exception:
        logger.exception("LLM intent classification unexpected error")
        return None


async def classify_question_intent(
    question_text: str,
    *,
    enable_llm: Optional[bool] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """Hybrid intent classification: rule-based first, LLM fallback.

    Args:
        question_text: The buyer question text.
        enable_llm: Override for ``ENABLE_LLM_INTENT`` setting. If ``None``,
            reads from config.
        api_key: Override DeepSeek API key.
        base_url: Override DeepSeek base URL.
        model: Override model name.

    Returns:
        ``(intent, method)`` where method is ``"rule_based"`` or ``"llm"``.
    """
    from app.services.interaction_ingest import _question_intent

    rule_intent = _question_intent(question_text)
    if rule_intent != "general_question":
        return rule_intent, "rule_based"

    # Decide whether to try LLM
    if enable_llm is None:
        settings = get_settings()
        enable_llm = settings.ENABLE_LLM_INTENT

    if not enable_llm:
        return "general_question", "rule_based"

    try:
        llm_intent = await classify_question_intent_llm(
            question_text,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        if llm_intent is not None and llm_intent in VALID_INTENTS:
            logger.info(
                "LLM reclassified question from general_question -> %s (first 80 chars): %s",
                llm_intent,
                question_text[:80],
            )
            return llm_intent, "llm"
    except Exception:
        logger.exception("LLM intent fallback failed, keeping general_question")

    return "general_question", "rule_based"
