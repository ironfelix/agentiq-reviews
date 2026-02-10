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


# Intent types with descriptions
INTENTS = {
    "delivery_status": "Где мой заказ?",
    "delivery_delay": "Заказ задерживается",
    "cancel_request": "Хочу отменить",
    "wrong_item": "Прислали не тот товар",
    "defect_not_working": "Брак, не работает",
    "usage_howto": "Как пользоваться?",
    "product_spec": "Характеристики товара",
    "refund_exchange": "Возврат или обмен",
    "thanks": "Благодарность",
    "other": "Другое",
}

# SLA priorities by intent
SLA_PRIORITIES = {
    "defect_not_working": "urgent",    # P0 < 1 hour
    "wrong_item": "urgent",             # P0 < 1 hour
    "delivery_delay": "high",           # P1 < 1 hour (if repeated)
    "cancel_request": "high",           # P1 < 1 hour
    "refund_exchange": "normal",        # P2 < 4 hours
    "delivery_status": "normal",        # P2 < 4 hours
    "usage_howto": "low",               # P3 < 24 hours
    "product_spec": "low",              # P3 < 24 hours
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
2. Структура: {Имя}, здравствуйте! + конкретный ответ + "Если нужна помощь — пишите!"
3. Если проблема очевидна (wrong_item, defect) → сразу инструкция по возврату
4. Если доставка → "Со своей стороны проверили — товар передан в доставку"
5. Если клиент повторяет сообщение → признать задержку, не переспрашивать
6. Если интент неясен → уточнить "Подскажите, что именно произошло?"
7. НЕ выдумывать характеристики товара — только из контекста

ШАБЛОНЫ по интентам:
- delivery_status: "Со своей стороны товар отгружен, отслеживайте в ЛК WB"
- delivery_delay: "Понимаем, ожидание затянулось. Со своей стороны проверили — товар передан в доставку {дата}."
- cancel_request: "Вы можете отменить заказ в ЛК WB: раздел Доставки → Отменить."
- wrong_item: "Приносим извинения! Оформите возврат через ЛК WB с пометкой «не соответствует описанию»."
- defect_not_working: "Нам очень жаль! Оформите возврат через ЛК WB. Передали информацию в отдел качества."
- usage_howto: "По данным карточки: {ответ}. Если нужна помощь — пишите!"
- product_spec: "По данным карточки: {характеристика}. Если нужны подробности — уточните!"
- refund_exchange: "Оформить возврат можно в ЛК WB: раздел Покупки → Оформить возврат."
- thanks: "Рады помочь! Если возникнут вопросы — обращайтесь."

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

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize AI Analyzer.

        Args:
            api_key: DeepSeek API key (defaults to settings)
            base_url: API base URL (defaults to settings)
        """
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL

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
        if not self.api_key:
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
                        "model": "deepseek-chat",
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

        # Add customer name if missing
        if customer_name and not result.lower().startswith(customer_name.lower()):
            if not result.startswith("Здравствуйте"):
                result = f"{customer_name}, здравствуйте! {result}"

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
        elif any(w in all_text for w in ["как", "размер", "характеристик"]):
            intent = "usage_howto"

        # Detect sentiment
        sentiment = "neutral"
        if any(w in all_text for w in ["плохо", "ужас", "кошмар", "разочарован"]):
            sentiment = "negative"
        elif any(w in all_text for w in ["отлично", "спасибо", "супер", "класс"]):
            sentiment = "positive"

        # Generate fallback recommendation
        name_prefix = f"{customer_name}, здравствуйте! " if customer_name else "Здравствуйте! "

        recommendations = {
            "delivery_status": f"{name_prefix}Проверили ваш заказ — со своей стороны товар отгружен. Отслеживайте статус в ЛК WB.",
            "delivery_delay": f"{name_prefix}Понимаем, ожидание затянулось. Со своей стороны проверили — товар передан в доставку.",
            "defect_not_working": f"{name_prefix}Нам очень жаль! Оформите возврат через ЛК WB. Передали информацию в отдел качества.",
            "wrong_item": f"{name_prefix}Приносим извинения! Оформите возврат через ЛК WB с пометкой «не соответствует описанию».",
            "refund_exchange": f"{name_prefix}Оформить возврат можно в ЛК WB: раздел Покупки → Оформить возврат.",
            "cancel_request": f"{name_prefix}Вы можете отменить заказ в ЛК WB: раздел Доставки → Отменить.",
            "thanks": f"{name_prefix}Рады помочь! Если возникнут вопросы — обращайтесь.",
            "usage_howto": f"{name_prefix}Подскажите, пожалуйста, какой именно вопрос у вас возник?",
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
    analyzer = AIAnalyzer()
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
