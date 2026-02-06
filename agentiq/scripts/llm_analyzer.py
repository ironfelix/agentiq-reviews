#!/usr/bin/env python3
"""
LLM-powered analysis module using DeepSeek API (OpenAI-compatible).
Provides replacements for classify_reasons, get_actions, get_reply_template.
Falls back to None on any error — caller should use rule-based fallback.
"""

import json
import os
import re
import time
from collections import Counter
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

MODEL = "deepseek-chat"
MAX_RETRIES = 2
BATCH_SIZE = 30  # reviews per LLM call

_client = None


def _get_client():
    """Lazy-init the DeepSeek client (OpenAI-compatible)."""
    global _client
    if _client is None:
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package not installed")
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
    return _client


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> Optional[str]:
    """Single DeepSeek API call with retry logic."""
    try:
        cl = _get_client()
    except RuntimeError as e:
        print(f"[LLM] Client init failed: {e}")
        return None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = cl.chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            if response.usage:
                print(f"[LLM] tokens: in={response.usage.prompt_tokens} out={response.usage.completion_tokens} total={response.usage.total_tokens}")
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM] Attempt {attempt + 1} failed: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────
# 1. CLASSIFY REASONS
# ─────────────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """Ты — аналитик отзывов на маркетплейсе Wildberries. Классифицируй негативные отзывы по причинам.

Категория товара: {category}

Доступные причины (используй ТОЛЬКО эти ключи):
{reason_keys_json}

Правила:
1. Каждый отзыв может иметь НЕСКОЛЬКО причин (multi-label).
2. Если отзыв не подходит ни под одну причину — верни ["other"].
3. Отвечай ТОЛЬКО валидным JSON без комментариев.
4. Не выдумывай новые ключи — используй только из списка выше."""

CLASSIFY_USER = """Классифицируй каждый негативный отзыв по причинам.

Отзывы:
{reviews_block}

Верни JSON:
{{"classifications": [{{"index": 0, "reasons": ["key1"]}}, ...]}}"""


def llm_classify_reasons(
    negative_texts: list,
    category: str,
    reason_definitions: dict,
) -> Optional[dict]:
    """
    Classify negative review texts into reason categories using DeepSeek.

    Args:
        negative_texts: [{"index": int, "text": str}, ...]
        category: detected product category
        reason_definitions: {key: {"label": str, "emoji": str}, ...}

    Returns:
        {reason_key: count} or None on failure
    """
    if not negative_texts:
        return {}

    reason_keys_desc = {k: v["label"] for k, v in reason_definitions.items()}
    reason_keys_json = json.dumps(reason_keys_desc, ensure_ascii=False, indent=2)

    system = CLASSIFY_SYSTEM.format(
        category=category,
        reason_keys_json=reason_keys_json,
    )

    aggregated = Counter()

    for batch_start in range(0, len(negative_texts), BATCH_SIZE):
        batch = negative_texts[batch_start:batch_start + BATCH_SIZE]

        reviews_lines = []
        for i, item in enumerate(batch):
            text = item["text"][:200]
            reviews_lines.append(f"[{i}] {text}")
        reviews_block = "\n".join(reviews_lines)

        user = CLASSIFY_USER.format(reviews_block=reviews_block)

        raw = _call_llm(system, user, max_tokens=1024)
        parsed = _parse_json_response(raw)

        if parsed is None or "classifications" not in parsed:
            print(f"[LLM] classify batch {batch_start} failed, aborting LLM classification")
            return None

        for item in parsed["classifications"]:
            reasons = item.get("reasons", ["other"])
            for r in reasons:
                if r in reason_definitions or r == "other":
                    aggregated[r] += 1

    return dict(aggregated)


# ─────────────────────────────────────────────────────────────
# 2. GET ACTIONS
# ─────────────────────────────────────────────────────────────

ACTIONS_SYSTEM = """Ты — бизнес-аналитик маркетплейса. Сгенерируй 3-5 конкретных рекомендаций для продавца.

Правила:
1. Каждая рекомендация — конкретное действие (начинай с глагола).
2. Рекомендации реалистичные и выполнимые.
3. Учитывай категорию, вариант товара, найденные причины.
4. Отвечай ТОЛЬКО JSON-массивом строк.
5. Язык: русский."""

ACTIONS_USER = """Категория товара: {category}
Проблемный вариант: {target_variant}

Топ причины негатива:
{reasons_block}

Сгенерируй 3-5 конкретных рекомендаций для продавца.
Формат: ["Рекомендация 1", "Рекомендация 2", ...]"""


def llm_get_actions(
    category: str,
    target_variant: str,
    reason_rows: list,
) -> Optional[list]:
    """
    Generate actionable recommendations using DeepSeek.
    Returns list of 3-5 action strings, or None on failure.
    """
    reasons_block = "\n".join(
        f"- {r['emoji']} {r['label']} ({r['share']}%)" for r in reason_rows[:5]
    )

    user = ACTIONS_USER.format(
        category=category,
        target_variant=target_variant or "Один товар",
        reasons_block=reasons_block,
    )

    raw = _call_llm(ACTIONS_SYSTEM, user, max_tokens=512)

    # Try parsing as JSON
    parsed = _parse_json_response(raw)
    if parsed is None and raw:
        try:
            parsed = json.loads(raw.strip())
        except (json.JSONDecodeError, AttributeError):
            return None

    if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
        return parsed[:5]

    return None


# ─────────────────────────────────────────────────────────────
# 3. GET REPLY TEMPLATE
# ─────────────────────────────────────────────────────────────

REPLY_SYSTEM = """Ты — специалист по коммуникациям на маркетплейсе. Напиши черновик ответа продавца на негативный отзыв.

Правила:
1. 2-3 предложения, вежливо и конкретно.
2. Не извиняйся за то, что не подтверждено.
3. Не обещай возврат/замену безусловно — предложи связаться.
4. Не обвиняй покупателя.
5. Предложи конкретное решение или следующий шаг.
6. Язык: русский.
7. Отвечай ТОЛЬКО текстом ответа, без кавычек и пояснений."""

REPLY_USER = """Категория товара: {category}
Главная причина негатива: {main_reason}
Контекст: {context}

Напиши черновик ответа продавца (2-3 предложения):"""


def llm_get_reply_template(
    category: str,
    main_reason: str,
    product_name: str = "",
    target_variant: str = "",
) -> Optional[str]:
    """
    Generate a reply draft using DeepSeek.
    Returns reply text string, or None on failure.
    """
    context_parts = []
    if product_name:
        context_parts.append(f"Товар: {product_name}")
    if target_variant and target_variant != "Один товар":
        context_parts.append(f"Проблемный вариант: {target_variant}")
    context = ". ".join(context_parts) if context_parts else "Общий товар"

    user = REPLY_USER.format(
        category=category,
        main_reason=main_reason or "Общая неудовлетворённость",
        context=context,
    )

    raw = _call_llm(REPLY_SYSTEM, user, max_tokens=256)

    if raw and len(raw.strip()) > 10:
        text = raw.strip().strip('"').strip("'")
        return sanitize_reply(text)

    return None


# ─────────────────────────────────────────────────────────────
# 4. DEEP ANALYSIS (root cause + strategy + actions + reply)
# ─────────────────────────────────────────────────────────────

DEEP_SYSTEM = """Ты — эксперт по анализу товаров на маркетплейсе Wildberries.

Задача: проанализировать почему конкретный вариант товара получает плохие оценки,
найти корневую причину и предложить стратегию решения.

ВАЖНО — АЛГОРИТМ ДИАГНОСТИКИ (следуй по шагам):
1. Задай себе вопрос: «Это РЕАЛЬНЫЙ дефект или НЕСОВПАДЕНИЕ ОЖИДАНИЙ?»
   - Если ВСЕ варианты имеют проблему → скорее дефект (партия/конструкция).
   - Если только ОДИН вариант проседает, а остальные в норме → подумай: может это ФИЗИЧЕСКАЯ ОСОБЕННОСТЬ варианта (цвет, размер, материал), а не дефект.
   - Жалобы типа "тусклый", "слабый", "маленький" часто = несовпадение ожиданий, а не брак.
   - Жалобы типа "сломался", "не включается", "перестал работать через день" = скорее дефект.
2. Подумай о НАЗНАЧЕНИИ варианта: зачем покупатель выбирает именно этот вариант? Какую задачу он решает?
   Примеры: красный фонарик — для ночного зрения (охота, астрономия), не для яркости; маленький объём — для поездки, не для дома.
   Если вариант имеет специальное назначение — объясни это в ответе покупателю.
3. Подумай о физике товара: может ли разница между вариантами объясняться свойствами материала, цвета, размера?
   Примеры: красный LED тусклее белого по физике; тёмные ткани выгорают быстрее; маленький объём кончается быстрее.
4. Посмотри на ОПИСАНИЕ КАРТОЧКИ ТОВАРА (если предоставлено): что продавец написал? Объясняет ли он особенности варианта? Если нет — это description_gap.
   ВАЖНО: описание карточки — это ФАКТ. Используй его для понимания товара, его назначения и особенностей вариантов.

Правила:
1. Определи ТИП проблемы: expectation_mismatch / defect / design_flaw / description_gap.
2. Объясни ПОЧЕМУ — 2-3 пункта, КРАТКО. Каждый начинается с ключевого слова (Физика/Ожидания/Описание/Качество и т.д.), после двоеточия — одно предложение.
3. Сделай короткий вывод (1 предложение).
4. Название стратегии: 2-4 слова ПРОСТЫМ языком. Хорошо: «Обновить описание», «Проверить партию», «Объяснить назначение». Плохо: «Сегрегация и управление ожиданиями», «Комплексная оптимизация».
5. Дай 3 конкретных действия, каждое начинается с глагола. Каждое — не длиннее 100 символов.
6. Ответ покупателю: 2 предложения. ОБЪЯСНИ назначение или причину, а не просто «мы проверим».
7. Язык: русский. Отвечай ТОЛЬКО валидным JSON.

ПРИМЕР ЭКСПЕРТНОГО МЫШЛЕНИЯ:
Товар: фонарик, проблемный вариант: «красный», жалобы: «тусклый», «батарея садится».
Плохой анализ: «Дефект аккумулятора → отозвать партию.»
Хороший анализ: «Красный режим предназначен для сохранения ночного зрения (охота, астрономия) — он специально тусклый. Покупатели не знают об этом и ожидают яркость как у белого. Стратегия: объяснить назначение.»

GUARDRAILS:
- НЕ обещай возврат, замену или компенсацию.
- НЕ обвиняй покупателя.
- НЕ пиши «обратитесь в поддержку» — объясни причину.
- Каждое действие конкретное, выполнимое продавцом на WB (карточка, логистика, коммуникация)."""

DEEP_USER = """Товар: {product_name}
Категория: {category}
Проблемный вариант: {target_variant} (рейтинг {target_rating}, {target_count} отзывов)
Остальные варианты: {other_variants}
Общий рейтинг карточки: {overall_rating}
{card_description_block}
{questions_block}
Причины негатива:
{reasons_block}

Примеры негативных отзывов (вариант "{target_variant}"):
{reviews_block}

Верни JSON:
{{
  "root_cause": {{
    "type": "expectation_mismatch | defect | design_flaw | description_gap",
    "explanation": ["Ключевое слово: пояснение почему", "..."],
    "conclusion": "Короткий вывод (1 предложение)"
  }},
  "strategy": {{
    "title": "Название стратегии",
    "description": "Описание подхода (1-2 предложения)"
  }},
  "actions": ["Действие 1", "Действие 2", "..."],
  "reply": "Текст ответа покупателю (2-3 предложения)"
}}"""


def llm_deep_analysis(
    product_name: str,
    category: str,
    target_variant: str,
    target_rating: float,
    target_count: int,
    other_variants: list,
    reason_rows: list,
    review_samples: list,
    card_description: str = None,
    questions: list = None,
) -> Optional[dict]:
    """
    Deep analysis: root cause + strategy + actions + reply in one LLM call.

    Args:
        product_name: product name from WB
        category: detected category
        target_variant: problematic variant name
        target_rating: its average rating
        target_count: number of reviews for this variant
        other_variants: [{"name": str, "rating": float, "count": int}, ...]
        reason_rows: [{"emoji": str, "label": str, "share": int}, ...]
        review_samples: list of negative review texts (up to 10, 300 chars each)
        card_description: WB card description + options (from public API)
        questions: list of customer question dicts from WBCON QS API

    Returns:
        {"root_cause": {...}, "strategy": {...}, "actions": [...], "reply": "..."} or None
    """
    if not review_samples:
        return None

    reasons_block = "\n".join(
        f"- {r['emoji']} {r['label']} ({r['share']}%)" for r in reason_rows[:5]
    )

    reviews_block = "\n".join(
        f"[{i+1}] «{text}»" for i, text in enumerate(review_samples[:10])
    )

    other_vars_str = ", ".join(
        f"{v['name']} ({v['rating']}, {v['count']} отз.)" for v in other_variants
    ) if other_variants else "нет данных"

    # Card description block (from WB public API)
    if card_description and card_description.strip():
        desc_trimmed = card_description.strip()[:800]
        card_description_block = f"\nОписание карточки на WB:\n{desc_trimmed}\n"
    else:
        card_description_block = ""

    # Questions block (from WBCON QS API)
    questions_block = ""
    if questions:
        # Sort: unanswered first, then by recency (newest first)
        sorted_qs = sorted(
            questions,
            key=lambda q: (
                0 if not q.get("answer_text") else 1,
                q.get("qs_created_at", ""),
            ),
        )
        # Reverse the date part within each group (unanswered/answered)
        unanswered = [q for q in sorted_qs if not q.get("answer_text")]
        answered = [q for q in sorted_qs if q.get("answer_text")]
        unanswered.sort(key=lambda q: q.get("qs_created_at", ""), reverse=True)
        answered.sort(key=lambda q: q.get("qs_created_at", ""), reverse=True)
        top_qs = (unanswered + answered)[:10]

        qs_lines = []
        for i, q in enumerate(top_qs):
            text = (q.get("qs_text") or "")[:200]
            status = "(без ответа)" if not q.get("answer_text") else "(есть ответ)"
            qs_lines.append(f"[{i+1}] {status} {text}")
        questions_block = "\nВопросы покупателей ({} всего, {} без ответа):\n{}\n".format(
            len(questions),
            sum(1 for q in questions if not q.get("answer_text")),
            "\n".join(qs_lines),
        )

    user = DEEP_USER.format(
        product_name=product_name or "Не указано",
        category=category,
        target_variant=target_variant,
        target_rating=round(target_rating, 2),
        target_count=target_count,
        other_variants=other_vars_str,
        overall_rating=round(target_rating, 2),
        card_description_block=card_description_block,
        questions_block=questions_block,
        reasons_block=reasons_block,
        reviews_block=reviews_block,
    )

    raw = _call_llm(DEEP_SYSTEM, user, max_tokens=1024)
    parsed = _parse_json_response(raw)

    if parsed is None:
        return None

    # Validate structure
    if not isinstance(parsed.get("root_cause"), dict):
        return None
    if not isinstance(parsed.get("strategy"), dict):
        return None
    if not isinstance(parsed.get("actions"), list):
        return None
    if not isinstance(parsed.get("reply"), str):
        return None

    # --- Post-processing guardrails ---
    parsed = _apply_guardrails(parsed)

    return parsed


# ─────────────────────────────────────────────────────────────
# 5. GUARDRAILS CONFIG
# ─────────────────────────────────────────────────────────────
# All guardrail rules in one place. Easy to extend, test, or move to a file/DB.

GUARDRAILS = {
    # Reply: banned phrases → replaced with this substitute
    "reply_banned_phrases": [
        "вернём деньги", "вернем деньги", "гарантируем возврат",
        "гарантируем замену", "полный возврат", "бесплатную замену",
        "вы неправильно", "вы не так", "ваша вина", "сами виноваты",
        "обратитесь в поддержку",
    ],
    "reply_banned_substitute": "мы рассмотрим ваш вопрос",
    "reply_max_length": 300,
    "reply_min_length": 20,

    # Communication analysis: banned mentions (we are AI ourselves)
    "comm_banned_phrases": [
        "ИИ-ответ", "ии-ответ", "ИИ ответ", "искусственный интеллект",
        "бот-ответ", "бот ответ", "нейросет", "GPT", "ChatGPT",
        "автоматический ответ",
    ],
    "comm_banned_substitute": "шаблонный ответ",

    # Return/refund: only suggest if buyer asked for it
    "comm_return_trigger_words": [
        "возврат", "вернуть", "замена", "заменить", "обменять", "обмен",
    ],

    # Actions
    "actions_max_count": 3,
    "actions_max_item_length": 120,
    "actions_min_item_length": 5,

    # Root cause
    "root_cause_valid_types": {
        "expectation_mismatch", "defect", "design_flaw", "description_gap",
    },
    "root_cause_default_type": "expectation_mismatch",
    "explanation_max_items": 3,
    "explanation_max_item_length": 150,
    "conclusion_max_length": 120,

    # Strategy
    "strategy_title_max_length": 40,
}


def sanitize_reply(text: str) -> str:
    """Apply guardrails to a reply text. Works for both deep analysis and standalone replies."""
    if not isinstance(text, str) or not text.strip():
        return text

    cfg = GUARDRAILS
    reply = text.strip()

    # Ban check
    reply_lower = reply.lower()
    for banned in cfg["reply_banned_phrases"]:
        if banned in reply_lower:
            print(f"[GUARDRAIL] Banned phrase in reply: '{banned}'")
            reply = re.sub(re.escape(banned), cfg["reply_banned_substitute"], reply, flags=re.IGNORECASE)
            reply_lower = reply.lower()  # refresh after replacement

    # Length limit
    max_len = cfg["reply_max_length"]
    if len(reply) > max_len:
        cut = reply[:max_len]
        last_period = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        if last_period > max_len // 3:
            reply = cut[:last_period + 1]
        else:
            reply = cut + "…"

    return reply


def _trunc(text: str, limit: int) -> str:
    """Truncate text at word boundary, add '...' if truncated."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space > limit // 3:
        cut = cut[:last_space]
    return cut.rstrip(".,;: ") + "…"


def _apply_guardrails(result: dict) -> dict:
    """Post-process LLM deep analysis output to enforce all guardrails."""
    cfg = GUARDRAILS

    # 1. Root cause type
    rc = result.get("root_cause", {})
    if rc.get("type") not in cfg["root_cause_valid_types"]:
        rc["type"] = cfg["root_cause_default_type"]

    # 2. Explanation items
    explanation = rc.get("explanation", [])
    max_item = cfg["explanation_max_item_length"]
    rc["explanation"] = [
        _trunc(item, max_item) for item in explanation[:cfg["explanation_max_items"]]
        if isinstance(item, str)
    ]

    # 3. Conclusion
    conclusion = rc.get("conclusion", "")
    if isinstance(conclusion, str) and len(conclusion) > cfg["conclusion_max_length"]:
        rc["conclusion"] = _trunc(conclusion, cfg["conclusion_max_length"])

    # 4. Actions
    actions = result.get("actions", [])
    result["actions"] = [
        _trunc(a, cfg["actions_max_item_length"])
        for a in actions[:cfg["actions_max_count"]]
        if isinstance(a, str) and len(a.strip()) > cfg["actions_min_item_length"]
    ]

    # 5. Reply
    result["reply"] = sanitize_reply(result.get("reply", ""))

    # 6. Strategy title
    strategy = result.get("strategy", {})
    title_max = cfg["strategy_title_max_length"]
    if isinstance(strategy.get("title"), str) and len(strategy["title"]) > title_max:
        strategy["title"] = _trunc(strategy["title"], title_max)

    return result


# ─────────────────────────────────────────────────────────────
# 6. COMMUNICATION QUALITY ANALYSIS
# ─────────────────────────────────────────────────────────────

COMM_SYSTEM = """Ты — эксперт по коммуникации продавца с покупателями на маркетплейсе Wildberries.

Задача: оценить качество ОТВЕТОВ ПРОДАВЦА на отзывы. Важно не только отвечать, но и КАК отвечать.

Типы ошибок в ответах (risk_type → risk_label):
- "blame" → "Перекладывает вину" (tooltip: «Читайте описание», «вы неправильно используете» — винит клиента в проблеме)
- "ignore" → "Игнорирует жалобу" (tooltip: покупатель жалуется, а продавец благодарит за «позитивный отзыв» или отвечает про другое)
- "amplify" → "Подтверждает проблему" (tooltip: продавец сам признаёт несоответствие описанию — это видят все покупатели)
- "deny" → "Отрицает проблему" (tooltip: «у нас всё хорошо» — проблема есть, но продавец говорит что нет)
- "template" → "Копипаст-шаблон" (tooltip: одинаковый текст на все отзывы — покупатель видит: никто не читает)
- "no_answer" → "Без ответа" (tooltip: продавец не ответил на негативный отзыв вообще)

Хорошие ответы:
- "ok" → "Нормальный ответ" (вежливый, но неконкретный — не вредит, но и не помогает)
- "good" → "Хороший ответ" (эмпатия + конкретное решение или объяснение)

КРИТИЧЕСКИ ВАЖНО:
1. НИКОГДА не обещать в рекомендациях: возвраты денег, замены, компенсации, конкретные сроки.
2. Предлагать возврат через ЛК WB ТОЛЬКО если покупатель сам написал о возврате/замене в отзыве.
3. Если покупатель НЕ просил возврат — предлагать: эмпатию, объяснение, помощь с настройкой.
4. НИКОГДА не упоминать в текстах: «ИИ», «бот», «нейросеть», «автоматический ответ», «GPT».
5. Не обвинять покупателя НИКОГДА.
6. В verdict — главный вывод для продавца, 1-2 предложения."""

COMM_USER = """Проанализируй ответы продавца на отзывы.

Товар: {product_name}

Отзывы с ответами:
{reviews_block}

Верни JSON:
{{
  "quality_score": число 1-10,
  "verdict": "Главный вывод для продавца, 1-2 предложения. Что хорошо + что критично плохо.",
  "total_analyzed": число,
  "negative_count": число (1-3★),
  "distribution": {{
    "harmful": число (вредят продажам),
    "risky": число (есть проблемы),
    "acceptable": число (нормальные),
    "good": число (хорошие)
  }},
  "error_types": [
    {{
      "label": "Понятное название ошибки",
      "tooltip": "Пояснение что это значит, 1 предложение",
      "count": число,
      "severity": "critical|warning|ok",
      "risk_type": "blame|ignore|amplify|deny|template|no_answer|ok|good"
    }}
  ],
  "worst_responses": [
    {{
      "review_rating": число,
      "review_text": "цитата отзыва (до 100 симв)",
      "response_text": "цитата ответа продавца (до 150 симв)",
      "risk_type": "blame|ignore|amplify|deny|template|no_answer",
      "risk_label": "понятное название ошибки",
      "explanation": "почему этот ответ вредит (1-2 предл.)",
      "recommendation": "как стоило ответить (2-3 предл.)"
    }}
  ],
  "hidden_risks": [
    {{
      "review_rating": число,
      "reviewer_name": "имя покупателя если есть",
      "review_text": "цитата жалобы из позитивного отзыва",
      "response_text": "цитата ответа продавца (до 150 симв)",
      "issue": "что именно проигнорировано"
    }}
  ],
  "buyer_perception": [
    "что видит потенциальный покупатель при чтении отзывов (3-5 пунктов)"
  ],
  "action_plan": [
    {{
      "priority": "critical|important",
      "action": "конкретное действие для продавца, начинается с глагола"
    }}
  ]
}}

Правила:
1. verdict — первым делом, главный вывод
2. error_types — ВСЕ типы включая хорошие (severity: ok, risk_type: ok/good). Хорошие идут первыми, ошибки — после. Шаблон отображает их в ДВУХ секциях: «Хорошие ответы» и «Ошибки в ответах».
3. worst_responses — ТОП-3 самых вредных, с реальными цитатами отзыва И ответа
4. hidden_risks — 3-5 позитивных отзывов (4-5★) где есть жалоба и продавец её проигнорировал. ОБЯЗАТЕЛЬНО включать реальную цитату ответа продавца (response_text). Поле issue пиши ПРОСТЫМ языком (не «несоответствие карточке товара не адресовано», а «покупатель указал на расхождение с описанием — продавец не заметил»).
5. action_plan — 3-5 конкретных шагов, с приоритетами critical/important
6. recommendation НИКОГДА не обещает возврат/замену если покупатель сам не просил
7. Не упоминать ИИ/бот/нейросеть в buyer_perception и verdict"""


def llm_analyze_communication(
    feedbacks: list,
    product_name: str = "",
) -> Optional[dict]:
    """
    Analyze quality of seller responses to ALL reviews via DeepSeek.

    Args:
        feedbacks: list of feedback dicts from WBCON API
        product_name: product name for context

    Returns:
        Communication quality analysis dict or None
    """
    if not feedbacks:
        return None

    # Build reviews block — ALL reviews, not just negative
    lines = []
    for i, fb in enumerate(feedbacks):
        rating = int(fb.get("valuation") or 0)
        text = (fb.get("fb_text") or fb.get("disadvantages") or "").strip()
        advantages = (fb.get("advantages") or "").strip()
        disadvantages = (fb.get("disadvantages") or "").strip()
        answer = (fb.get("answer_text") or "").strip()

        # Compose review text
        parts = []
        if text:
            parts.append(text[:200])
        if disadvantages and disadvantages != text:
            parts.append(f"Минусы: {disadvantages[:100]}")
        if advantages and rating >= 4:
            parts.append(f"Плюсы: {advantages[:80]}")
        review_text = ". ".join(parts) if parts else "(без текста)"

        answer_text = answer[:200] if answer else "(БЕЗ ОТВЕТА)"

        lines.append(
            f"[{i+1}] ★{rating} | Отзыв: {review_text}\n"
            f"    Ответ: {answer_text}"
        )

    reviews_block = "\n\n".join(lines)

    user = COMM_USER.format(
        product_name=product_name or "Не указано",
        reviews_block=reviews_block,
    )

    # Use larger max_tokens for comprehensive analysis
    raw = _call_llm(COMM_SYSTEM, user, max_tokens=2048)
    parsed = _parse_json_response(raw)

    if parsed is None:
        return None

    # Validate structure
    if not isinstance(parsed.get("quality_score"), (int, float)):
        return None
    if not isinstance(parsed.get("worst_responses"), list):
        return None

    # Apply communication guardrails
    parsed = _apply_communication_guardrails(parsed)

    return parsed


def _apply_communication_guardrails(result: dict) -> dict:
    """Post-process communication analysis to enforce guardrails."""
    cfg = GUARDRAILS
    reply_banned = cfg["reply_banned_phrases"]
    reply_sub = cfg["reply_banned_substitute"]
    comm_banned = cfg.get("comm_banned_phrases", [])
    comm_sub = cfg.get("comm_banned_substitute", "шаблонный ответ")
    return_triggers = cfg.get("comm_return_trigger_words", [])

    # --- 1. Sanitize recommendations in worst_responses ---
    for resp in result.get("worst_responses", []):
        rec = resp.get("recommendation", "")
        if isinstance(rec, str):
            # Ban reply-level phrases
            rec_lower = rec.lower()
            for phrase in reply_banned:
                if phrase in rec_lower:
                    print(f"[COMM GUARDRAIL] Banned phrase in recommendation: '{phrase}'")
                    rec = re.sub(re.escape(phrase), reply_sub, rec, flags=re.IGNORECASE)
                    rec_lower = rec.lower()

            # Check return suggestion: only allow if buyer mentioned return
            review_text = (resp.get("review_text") or "").lower()
            buyer_asked_return = any(w in review_text for w in return_triggers)
            if not buyer_asked_return:
                for trigger in return_triggers:
                    if trigger in rec.lower():
                        print(f"[COMM GUARDRAIL] Return suggestion without buyer request, removing: '{trigger}'")
                        # Remove sentence containing the trigger
                        sentences = rec.split(". ")
                        sentences = [s for s in sentences if trigger not in s.lower()]
                        rec = ". ".join(sentences)

            resp["recommendation"] = rec

    # --- 2. Ban AI/bot mentions in all text fields ---
    text_fields_to_check = [
        ("verdict", result),
    ]
    for item in result.get("buyer_perception", []):
        text_fields_to_check.append(("__list_item__", item))

    # Verdict
    verdict = result.get("verdict", "")
    if isinstance(verdict, str):
        for phrase in comm_banned:
            if phrase.lower() in verdict.lower():
                print(f"[COMM GUARDRAIL] AI mention in verdict: '{phrase}'")
                verdict = re.sub(re.escape(phrase), comm_sub, verdict, flags=re.IGNORECASE)
        result["verdict"] = _trunc(verdict, 200)

    # Buyer perception
    perception = result.get("buyer_perception", [])
    sanitized_perception = []
    for item in perception:
        if isinstance(item, str):
            for phrase in comm_banned:
                if phrase.lower() in item.lower():
                    print(f"[COMM GUARDRAIL] AI mention in perception: '{phrase}'")
                    item = re.sub(re.escape(phrase), comm_sub, item, flags=re.IGNORECASE)
            sanitized_perception.append(item)
    result["buyer_perception"] = sanitized_perception[:6]

    # --- 3. Clamp quality_score to 1-10 ---
    score = result.get("quality_score", 5)
    result["quality_score"] = max(1, min(10, int(score)))

    # --- 4. Limit array sizes ---
    result["worst_responses"] = result.get("worst_responses", [])[:5]
    result["hidden_risks"] = result.get("hidden_risks", [])[:5]

    # --- 5. Validate error_types ---
    valid_severities = {"critical", "warning", "ok"}
    error_types = result.get("error_types", [])
    for et in error_types:
        if et.get("severity") not in valid_severities:
            et["severity"] = "warning"
        if isinstance(et.get("tooltip"), str):
            et["tooltip"] = _trunc(et["tooltip"], 120)
        if isinstance(et.get("count"), (int, float)):
            et["count"] = max(0, int(et["count"]))
    result["error_types"] = error_types[:10]

    # --- 6. Validate action_plan ---
    valid_priorities = {"critical", "important"}
    action_plan = result.get("action_plan", [])
    # Backwards compat: if old "recommendations" field exists, convert
    if not action_plan and result.get("recommendations"):
        action_plan = [
            {"priority": "important", "action": r}
            for r in result.get("recommendations", [])
            if isinstance(r, str)
        ]
    for ap in action_plan:
        if ap.get("priority") not in valid_priorities:
            ap["priority"] = "important"
        if isinstance(ap.get("action"), str):
            ap["action"] = _trunc(ap["action"], 200)
    result["action_plan"] = action_plan[:5]

    # Clean up old field
    result.pop("recommendations", None)

    return result
