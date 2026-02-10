# AgentIQ 2.0: Multi-Agent Architecture

> **Статус:** Future roadmap (post-MVP)
> **Цель:** Эволюция от инструмента анализа к агентной платформе для customer service

---

## Видение

**AgentIQ** = Платформа специализированных AI-агентов, которые автономно решают задачи customer service:
- **MVP (сейчас):** Анализ отзывов WB + простые LLM-рекомендации
- **v2.0 (после денег):** Автономные агенты с reasoning, tools, memory
- **v3.0 (масштаб):** WB → Ozon → Яндекс.Маркет → Telegram CS → Email support

---

## Принципиальная разница: LLM call vs AI Agent

### Текущий подход (MVP)
```python
# Один промпт → один ответ
response = llm.generate(
    prompt=f"Ответь на отзыв: {review_text}",
    context={product, rating}
)
# → возвращает готовый текст
```

**Ограничения:**
- Нет памяти о предыдущих отзывах
- Не может принимать решения ("отвечать или нет?")
- Не учится на исправлениях менеджера
- Не использует внешние инструменты (поиск в базе знаний, проверка возвратов)

### Агентный подход (v2.0)

```python
# Агент = LLM + Tools + Memory + Reasoning loop
agent = AutoReplyAgent(
    tools=[
        "search_product_info",
        "check_return_policy",
        "get_similar_replies",      # RAG
        "analyze_sentiment",
        "validate_guardrails"
    ],
    memory=ConversationMemory(),
    reasoning="ReAct"
)

# Агент сам решает: какие инструменты использовать
result = agent.run(review_id=12345)
```

---

## Архитектура: Multi-Agent System

```
┌─────────────────────────────────────────────────────────────────┐
│                      AgentIQ Orchestrator                        │
│         (Координирует агентов, распределяет задачи)             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
   [Analyst]            [Responder]           [Monitor]
   Agent                Agent                 Agent
        │                     │                     │
        ↓                     ↓                     ↓
┌──────────────────────────────────────────────────────────────────┐
│                        Agent Registry                             │
│  - ReviewAnalyst    (анализ отзывов, выявление проблем)         │
│  - AutoResponder    (генерация и публикация ответов)            │
│  - SentimentMonitor (мониторинг настроения в реалтайме)         │
│  - EscalationAgent  (решает, когда привлечь человека)           │
│  - LearningAgent    (обучается на исправлениях менеджера)       │
│  - AnalyticsAgent   (тренды, инсайты, рекомендации)             │
└──────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
   [Tool Layer]        [Memory Layer]        [Integration Layer]
   - WB API            - Vector DB (RAG)     - Telegram
   - LLM calls         - Conv. history       - Email
   - DB queries        - Knowledge base      - CRM
```

---

## Агенты AgentIQ 2.0

### 1. ReviewAnalystAgent (эволюция текущего скрипта)

**Роль:** Глубокий анализ отзывов, выявление проблем товара/коммуникации

**Capabilities:**
```python
class ReviewAnalystAgent:
    tools = [
        "fetch_reviews_from_wb",
        "classify_by_sentiment",
        "extract_product_issues",
        "identify_communication_problems",
        "calculate_impact_on_sales",
        "generate_recommendations"
    ]

    reasoning = "Chain-of-Thought"

    async def analyze(self, article_id: int):
        # Step 1: Fetch data
        reviews = await self.fetch_reviews_from_wb(article_id)

        # Step 2: Classify
        sentiment_map = await self.classify_by_sentiment(reviews)

        # Step 3: Identify root causes
        issues = await self.extract_product_issues(reviews)

        # Step 4: Analyze seller responses
        comm_quality = await self.identify_communication_problems(reviews)

        # Step 5: Calculate money loss
        impact = await self.calculate_impact_on_sales(issues, comm_quality)

        # Step 6: Generate action plan
        recommendations = await self.generate_recommendations(impact)

        return {
            "issues": issues,
            "communication": comm_quality,
            "impact": impact,
            "action_plan": recommendations
        }
```

**Отличие от MVP:**
- ✅ MVP: монолитный скрипт `wbcon-task-to-card-v2.py`
- 🚀 v2.0: автономный агент с reasoning loop

---

### 2. AutoResponderAgent

**Роль:** Генерация и публикация ответов на отзывы

**Capabilities:**
```python
class AutoResponderAgent:
    tools = [
        "analyze_review_context",
        "search_similar_replies",      # RAG
        "check_return_policy",
        "generate_reply_variants",
        "validate_guardrails",
        "publish_to_wb",
        "escalate_to_human"
    ]

    reasoning = "ReAct"  # Thought → Action → Observation

    async def respond(self, review_id: str):
        # Thought: "Нужно понять контекст отзыва"
        context = await self.analyze_review_context(review_id)

        # Thought: "Это жалоба на брак, проверю политику возврата"
        if context.complaint_type == "defect":
            policy = await self.check_return_policy(context.category)

        # Thought: "Поищу похожие успешные ответы"
        similar = await self.search_similar_replies(context.review_text)

        # Thought: "Генерирую 3 варианта ответа"
        variants = await self.generate_reply_variants(
            context=context,
            examples=similar,
            tones=["empathetic", "professional", "brief"]
        )

        # Thought: "Проверяю лучший вариант через guardrails"
        best = variants[0]
        validation = await self.validate_guardrails(best, context)

        # Decision: автоответ или показать менеджеру?
        if validation.confidence > 0.9 and context.rating >= 3:
            await self.publish_to_wb(review_id, best.text)
            return {"status": "auto-published", "text": best.text}
        else:
            await self.escalate_to_human(review_id, variants)
            return {"status": "needs-approval", "variants": variants}
```

**UX в dashboard:**
```javascript
{
  "review_id": "12345",
  "agent_decision": "needs-approval",
  "reasoning": [
    "Проанализировал отзыв: жалоба на брак (рейтинг 2★)",
    "Нашёл 3 похожих успешных ответа в базе",
    "Сгенерировал 3 варианта (эмпатия, профессиональный, краткий)",
    "Проверил через guardrails: всё ОК",
    "Confidence = 0.85 (< 0.9) → отправляю менеджеру на проверку"
  ],
  "variants": [...],
  "manager_action": "approve_variant_1" | "edit" | "reject"
}
```

---

### 3. SentimentMonitorAgent

**Роль:** Real-time мониторинг настроения клиентов, алерты на кризисы

**Capabilities:**
```python
class SentimentMonitorAgent:
    tools = [
        "fetch_new_reviews",
        "analyze_sentiment_shift",
        "detect_viral_complaint",
        "check_brand_reputation",
        "trigger_alert"
    ]

    schedule = "every 15 minutes"

    async def monitor(self, article_id: int):
        new_reviews = await self.fetch_new_reviews(article_id)
        sentiment = await self.analyze_sentiment_shift(new_reviews)

        # Критерии алерта
        if sentiment.avg_rating_drop > 0.5:
            await self.trigger_alert(
                severity="high",
                message=f"Рейтинг упал: {sentiment.old} → {sentiment.new}",
                action="Проверить последние отзывы"
            )

        viral = await self.detect_viral_complaint(new_reviews)
        if viral:
            await self.trigger_alert(
                severity="critical",
                message=f"Отзыв {viral.id} набрал {viral.likes} лайков!",
                action="Срочно ответить"
            )
```

**UX:**
```
🚨 Алерт от SentimentMonitor:
Артикул 177068052 (Корм для собак)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Рейтинг упал: 4.8★ → 4.3★ за 24 часа
📊 Новых 1-2★ отзывов: 12 (обычно 2-3)
💬 Частая жалоба: "срок годности близок"

🤖 Рекомендации:
1. Ответить на все негативные отзывы в течение 2 часов
2. Проверить партию товара
3. Рассмотреть временную скидку
```

---

### 4. EscalationAgent

**Роль:** Решает, когда нужен человек

```python
class EscalationAgent:
    tools = [
        "assess_complexity",
        "check_manager_availability",
        "prioritize_queue",
        "route_to_specialist"
    ]

    async def evaluate(self, task: dict):
        complexity = await self.assess_complexity(task)

        escalate = (
            task.rating == 1 and "мошенники" in task.text.lower() or
            complexity.score > 0.8 or
            task.reply_history > 3
        )

        if escalate:
            manager = await self.route_to_specialist(
                expertise_needed=complexity.tags,
                urgency=task.urgency
            )
            return {
                "escalate": True,
                "assigned_to": manager.id,
                "priority": "high"
            }

        return {"escalate": False}
```

---

### 5. LearningAgent (ключевой для агентной системы!)

**Роль:** Учится на действиях менеджеров, улучшает других агентов

```python
class LearningAgent:
    tools = [
        "collect_feedback",
        "extract_patterns",
        "update_rag_database",
        "fine_tune_prompts",
        "generate_training_examples"
    ]

    async def learn_from_correction(self, event: dict):
        """Менеджер исправил автоответ → агент учится."""

        original = event.agent_reply
        corrected = event.manager_reply
        review_context = event.review

        # Анализ различий
        diff = await self.extract_patterns(original, corrected)

        # Сохранение в RAG
        await self.update_rag_database({
            "review": review_context.text,
            "good_reply": corrected,
            "bad_reply": original,
            "lesson": diff.insight
        })

        # Обновление промпта
        if diff.pattern_frequency > 10:
            await self.fine_tune_prompts(
                agent="AutoResponder",
                instruction=f"Add more empathy: {diff.example}"
            )

        return {"learned": True, "pattern": diff.insight}
```

**Feedback loop:**
```
Менеджер исправил → LearningAgent анализирует → Сохраняет в RAG →
→ Обновляет промпт → Следующий раз агент отвечает лучше
```

---

### 6. AnalyticsAgent

**Роль:** Анализ трендов, инсайты, рекомендации

```python
class AnalyticsAgent:
    tools = [
        "aggregate_metrics",
        "detect_trends",
        "compare_competitors",
        "generate_insights",
        "create_reports"
    ]

    async def weekly_report(self, user_id: int):
        metrics = await self.aggregate_metrics(user_id, period="7d")
        trends = await self.detect_trends(metrics)
        benchmark = await self.compare_competitors(metrics.category)
        insights = await self.generate_insights(trends, benchmark)

        report = {
            "highlights": [
                "✅ Скорость ответа: 12ч → 8ч",
                "⚠️ Рейтинг упал на 0.3★",
                "💡 Конкуренты отвечают за 6ч"
            ],
            "recommendations": insights.actions
        }

        await send_to_telegram(user_id, report)
```

---

## Orchestrator: Координация агентов

```python
class AgentIQOrchestrator:
    """Главный контроллер."""

    def __init__(self):
        self.agents = {
            "analyst": ReviewAnalystAgent(),
            "responder": AutoResponderAgent(),
            "monitor": SentimentMonitorAgent(),
            "escalation": EscalationAgent(),
            "learning": LearningAgent(),
            "analytics": AnalyticsAgent()
        }

        self.event_bus = EventBus()  # Pub/Sub

    async def on_new_review(self, review: dict):
        """Новый отзыв → запуск цепочки агентов."""

        # 1. Monitor проверяет sentiment
        alert = await self.agents["monitor"].check_sentiment(review)

        # 2. Escalation решает: авто или человек?
        escalation = await self.agents["escalation"].evaluate(review)

        if escalation.escalate:
            await self.notify_manager(escalation.assigned_to, review)
        else:
            # 3. Responder генерирует ответ
            response = await self.agents["responder"].respond(review)

            if response.status == "auto-published":
                # 4. Learning наблюдает
                await self.agents["learning"].record_action(response)

    async def on_manager_feedback(self, event: dict):
        """Менеджер исправил → обучение."""
        await self.agents["learning"].learn_from_correction(event)
```

---

## База данных

```sql
-- Агенты
CREATE TABLE agents (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    status ENUM('active', 'paused', 'learning'),
    config JSON,
    version VARCHAR(20)
);

-- Задачи для агентов
CREATE TABLE agent_tasks (
    id INT PRIMARY KEY,
    agent_id INT,
    task_type VARCHAR(50),
    input_data JSON,
    status ENUM('pending', 'processing', 'completed', 'failed'),
    result JSON,
    created_at DATETIME
);

-- Reasoning traces (дебаг + обучение)
CREATE TABLE agent_reasoning (
    id INT PRIMARY KEY,
    task_id INT,
    step_num INT,
    thought TEXT,
    action VARCHAR(100),
    action_input JSON,
    observation TEXT,
    timestamp DATETIME
);

-- Feedback loop
CREATE TABLE agent_feedback (
    id INT PRIMARY KEY,
    agent_id INT,
    original_output TEXT,
    corrected_output TEXT,
    feedback_type ENUM('correction', 'approval', 'rejection'),
    lesson_learned TEXT,
    applied BOOLEAN DEFAULT FALSE
);

-- RAG база
CREATE TABLE knowledge_base (
    id INT PRIMARY KEY,
    review_text TEXT,
    successful_reply TEXT,
    tags JSON,
    embedding VECTOR(1536),
    created_at DATETIME
);
```

---

## Dashboard 2.0

```
┌──────────────────────────────────────────────────┐
│  AgentIQ Dashboard                               │
├──────────────────────────────────────────────────┤
│                                                   │
│  🤖 Активные агенты: 6                           │
│  ┌──────────────────────────────────────────┐   │
│  │ AutoResponder      ●  ACTIVE             │   │
│  │  ↳ Обработано сегодня: 23 отзыва         │   │
│  │  ↳ Автоответов: 18, На проверку: 5       │   │
│  │                                            │   │
│  │ SentimentMonitor   ●  ACTIVE             │   │
│  │  ↳ Алертов за день: 2                     │   │
│  │                                            │   │
│  │ LearningAgent      ●  LEARNING           │   │
│  │  ↳ Обработано исправлений: 7             │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  📬 Очередь задач (5)                            │
│  ┌──────────────────────────────────────────┐   │
│  │ [1★] "Пришёл брак" → AutoResponder       │   │
│  │  💭 Thought: "Жалоба на дефект..."       │   │
│  │  🔧 Action: check_return_policy()         │   │
│  │  [Посмотреть reasoning] [Вмешаться]      │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  🧠 Обучение агентов                             │
│  ┌──────────────────────────────────────────┐   │
│  │ Менеджер исправил ответ:                 │   │
│  │ Было:   "Приносим извинения."            │   │
│  │ Стало:  "Нам очень жаль! Оформите..."    │   │
│  │                                            │   │
│  │ 🤖 LearningAgent: "Добавлять эмпатию     │   │
│  │    при rating ≤ 2"                        │   │
│  │ [✓ Применить] [Игнорировать]             │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## Roadmap (актуализировано)

### Phase 1: Revenue Foundation (сейчас → 1–2 месяца)
- ✅ ReviewAnalyst (текущий скрипт)
- 🔨 **Chat Center MVP+ (Ozon)** → платные пилоты
- 🔨 Базовый UX: единое окно чатов + SLA таймеры

**Подход:** простые LLM calls + ручные ответы. Главная цель — деньги и ретеншн.

### Phase 2: Multi-market + AI Assist (2–3 месяца, после первых оплат)
- WB + Яндекс.Маркет коннекторы
- Copilot-подсказки (без автоотправки)
- Метрики качества/скорости ответа

### Phase 3: Autonomy (4–6 месяцев)
- EscalationAgent + routing
- Auto-publish для простых кейсов
- Learning loop (feedback от менеджеров)

### Phase 4: Analytics & Scale (6–12 месяцев)
- AnalyticsAgent
- RAG база знаний
- API для CRM

### Phase 5: Enterprise (12+ месяцев)
- Custom agents для клиентов
- White-label
- Agent marketplace

---

## Конкурентные преимущества

| Традиционный | AgentIQ v2.0 |
|-------------|--------------|
| Скрипт раз в день | Агенты 24/7 |
| Менеджер решает | Агент предлагает + reasoning |
| Нет обучения | LearningAgent улучшается |
| Простые алерты | SentimentMonitor с контекстом |
| Разрозненные данные | Агенты делятся знаниями |

---

## Технический стек (v2.0)

- **Agent Framework:** LangChain / LangGraph
- **LLM:** DeepSeek (cost-effective) + GPT-4 (сложные кейсы)
- **Vector DB:** Qdrant / Pinecone (RAG)
- **Orchestration:** Celery + Redis (task queue)
- **Memory:** PostgreSQL + pgvector
- **Monitoring:** Langfuse / LangSmith (observability)

---

## Важно

**MVP (до денег):**
- Простые LLM calls
- Без агентной архитектуры
- Focus на value proposition

**v2.0 (после денег):**
- Полноценная агентная платформа
- Автономность, обучение, reasoning
- Масштаб на другие маркетплейсы

---

_Документ обновлён: 2026-02-08_
_Следующий review: после достижения product-market fit_
