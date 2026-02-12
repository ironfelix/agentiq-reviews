"""
AI Analyzer service for chat analysis and response suggestions.

Uses DeepSeek API to:
1. Classify chat intent (delivery_status, defect, refund, etc.)
2. Analyze sentiment and urgency
3. Generate response recommendation following guardrails

Based on RESPONSE_GUARDRAILS.md policy.
"""

import httpx
import logging
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

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
    "refund_exchange": "normal",
    "delivery_status": "normal",
    # P3 (low) < 24 hours
    "usage_howto": "low",
    "product_spec": "low",
    "thanks": "low",
    "other": "normal",
}

# Banned phrases with replacements
BANNED_PHRASES = {
    # False Authority (Group A)
    "вернём деньги": "Оформите возврат через ЛК WB",
    "вернем деньги": "Оформите возврат через ЛК WB",
    "гарантируем возврат": "Оформите возврат через ЛК WB",
    "гарантируем замену": "Оформите возврат через ЛК WB",
    "мы одобрим возврат": "Оформите возврат через ЛК WB",
    "мы одобрим заявку": "Оформите возврат через ЛК WB",
    "полный возврат": "возврат через ЛК WB",
    "бесплатную замену": "возврат через ЛК WB",
    "доставим завтра": "Со своей стороны товар отгружен",
    "отменим ваш заказ": "Вы можете отменить заказ в ЛК WB",
    "ускорим доставку": "Со своей стороны товар отгружен",

    # Blame (forbidden)
    "вы неправильно": "",
    "вы не так": "",
    "ваша вина": "",
    "сами виноваты": "",

    # Dismissive
    "обратитесь в поддержку": "Мы со своей стороны проверим ситуацию",
    "мы не можем повлиять": "Со своей стороны мы передали информацию",

    # Legal admissions (Group C)
    "характеристики не соответствуют": "возможен дефект конкретного экземпляра",
    "наша ошибка": "нештатная ситуация, разбираемся",
    "мы виноваты": "нештатная ситуация, разбираемся",

    # AI/bot mentions (Group B)
    "ИИ": "",
    "бот": "",
    "нейросеть": "",
    "GPT": "",
    "ChatGPT": "",
    "автоматический ответ": "",

    # Internal jargon
    "пересорт": "прислали не тот товар",
    "FBO": "склад WB",
    "FBS": "склад продавца",
    "SKU": "артикул",

    # Formal/bureaucratic
    "уважаемый клиент": "",
    "уважаемый покупатель": "",
}

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
1. Формат: 2-3 предложения, макс 300 символов
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

История переписки (от старых к новым):
{messages_block}

Верни JSON:
{{
  "intent": "один из интентов",
  "sentiment": "positive" | "negative" | "neutral",
  "urgency": "low" | "normal" | "high" | "critical",
  "categories": ["complaint", "question", "order_status", ...],
  "recommendation": "ГОТОВЫЙ ТЕКСТ ответа от лица продавца (2-3 предл., макс 300 симв.)",
  "recommendation_reason": "почему именно такой ответ (1 предл.)",
  "needs_escalation": true | false,
  "escalation_reason": "причина эскалации если needs_escalation=true"
}}

ВАЖНО:
- recommendation — это ГОТОВЫЙ ТЕКСТ для отправки, НЕ инструкция
- Используй имя покупателя если есть
- Если последнее сообщение от продавца — рекомендация не нужна, верни recommendation: null"""


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
    ) -> Optional[Dict]:
        """
        Analyze chat and generate response recommendation.

        Args:
            messages: List of message dicts with keys:
                - text: message text
                - author_type: "buyer" or "seller"
                - created_at: datetime
            product_name: Product name for context
            customer_name: Customer name for personalization

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
            return self._fallback_analysis(messages, customer_name)

        if not messages:
            return None

        # Build messages block
        messages_block = self._format_messages(messages, customer_name)

        # Check for escalation keywords first
        escalation = self._check_escalation_keywords(messages)

        try:
            # Call DeepSeek API
            response = await self._call_llm(
                product_name=product_name or "Товар",
                messages_block=messages_block
            )

            if not response:
                return self._fallback_analysis(messages, customer_name)

            # Parse and validate response
            analysis = self._parse_response(response)

            # Apply guardrails to recommendation
            if analysis.get("recommendation"):
                analysis["recommendation"] = self._apply_guardrails(
                    analysis["recommendation"],
                    customer_name
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
                messages
            )

            analysis["analyzed_at"] = datetime.utcnow().isoformat()

            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._fallback_analysis(messages, customer_name)

    async def _call_llm(self, product_name: str, messages_block: str) -> Optional[Dict]:
        """Call DeepSeek API for chat analysis."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": CHAT_ANALYSIS_SYSTEM},
                            {"role": "user", "content": CHAT_ANALYSIS_USER.format(
                                product_name=product_name,
                                messages_block=messages_block
                            )}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"}
                    }
                )
                response.raise_for_status()

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return json.loads(content) if content else None

            except httpx.HTTPStatusError as e:
                logger.error(f"DeepSeek API error: {e.response.status_code}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return None
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
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

    def _apply_guardrails(self, text: str, customer_name: Optional[str] = None) -> str:
        """Apply guardrails to recommendation text."""
        if not text:
            return text

        result = text

        # Replace banned phrases
        for phrase, replacement in BANNED_PHRASES.items():
            if phrase.lower() in result.lower():
                if replacement:
                    result = re.sub(
                        re.escape(phrase),
                        replacement,
                        result,
                        flags=re.IGNORECASE
                    )
                else:
                    result = re.sub(
                        r'\s*' + re.escape(phrase) + r'\s*',
                        ' ',
                        result,
                        flags=re.IGNORECASE
                    )

        # Clean up double spaces
        result = re.sub(r'\s+', ' ', result).strip()

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

        # Truncate to 300 chars
        if len(result) > 300:
            # Find last sentence boundary
            cut_point = result[:297].rfind('.')
            if cut_point > 200:
                result = result[:cut_point + 1]
            else:
                result = result[:297] + "..."

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
        messages: List[Dict]
    ) -> str:
        """Calculate SLA priority based on intent, urgency, and message patterns."""
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

    def _fallback_analysis(
        self,
        messages: List[Dict],
        customer_name: Optional[str]
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
            "sla_priority": SLA_PRIORITIES.get(intent, "normal"),
            "analyzed_at": datetime.utcnow().isoformat(),
        }


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
