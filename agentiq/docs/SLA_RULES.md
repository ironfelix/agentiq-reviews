# AgentIQ SLA Rules: Response Time for Wildberries Seller Communication

> Date: 2026-02-11
> Status: Research Complete
> Based on: Industry benchmarks, academic research, WB platform mechanics

---

## A. SLA Targets by Message Type

### 1. NEGATIVE REVIEWS (1-2 stars) — URGENT

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 30 min** | 1 hour |
| Resolution attempt | < 4 hours | 24 hours |
| Follow-up (если покупатель ответил) | < 1 hour | 3 hours |

**Почему:**
- Ответ на 1-2★ в течение 24ч → **+33% вероятность** повышения оценки до +3 звёзд ([ReviewTrackers](https://www.reviewtrackers.com/reports/customer-reviews-stats/))
- Harvard Business Review: ответ на негатив в 24ч → **+16% customer advocacy** ([Business.com](https://www.business.com/articles/how-much-can-a-bad-review-hurt-your-business/))
- На WB: негативный отзыв снижает конверсию карточки на **15-20%** ([vc.ru](https://vc.ru/marketplace/682913))
- WB "Отложенная публикация негатива" → **3-дневное окно** для решения. Первый час — покупатель максимально вовлечён
- Часы тикают с момента ПЕРВОГО ответа покупателя → ответ в 30 минут максимизирует время на решение

### 2. НЕГАТИВ (3 звезды) — HIGH

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 1 hour** | 4 hours |
| Resolution | < 8 hours | 24 hours |

**Почему:** 3★ восстановимы, но менее срочны. Ответы в течение 24-48ч «закрепляются» вверху ленты отзывов.

### 3. PRE-PURCHASE ВОПРОСЫ — HIGH

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 1 hour** | 2 hours |
| Follow-up | < 30 min | 1 hour |

**Почему:**
- Официальная статистика WB: **+20% конверсия** при ответе на вопрос в течение 1ч ([WB Pro](https://pro.wildberries.ru/))
- Покупатель сравнивает товары в real-time, окно решения **10-20 секунд**
- Игнорирование вопросов → WB может **понизить товар в выдаче** ([totalcrm.ru](https://totalcrm.ru/blog/2025/11/otzyvy-i-voprosy-wildberries/))
- **52% покупателей** ожидают ответ в течение 1ч ([LiveChatAI](https://livechatai.com/blog/customer-support-response-time-statistics))

### 4. ЧАТЫ (post-purchase, общие) — NORMAL

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 4 hours** | 24 hours |
| Follow-up | < 2 hours | 8 hours |

**Почему:**
- Индустриальный средний FRT: **4-6 часов**, best-in-class: 30-60 мин ([Fullview](https://www.fullview.io/blog/support-stats))
- Amazon требует ответ в **24ч** (95% compliance) ([eDesk](https://www.edesk.com/blog/amazon-message-system/))
- **67% покупателей** ожидают решение в 3 часа ([Freshworks Benchmark 2025](https://company-assets.freshworks.com/marketing/freshdesk/Customer-Service-Benchmark-Report-2025.pdf))

### 5. ПОЗИТИВНЫЕ ОТЗЫВЫ (4-5 stars) — LOW

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 24 hours** | 48 hours |

**Почему:**
- **89% покупателей** предпочитают бизнес, который отвечает на ВСЕ отзывы ([Nector.io](https://www.nector.io/blog/the-power-of-reviews-how-customer-feedback-drives-loyalty-and-growth))
- Лояльные клиенты (8% базы) генерируют **41% выручки** ([Ordergroove](https://www.ordergroove.com/blog/customer-loyalty-in-ecommerce/))
- Свежие отзывы с ответами продавца имеют больший вес в ранжировании WB

### 6. БРАК / НЕ ТОТ ТОВАР — CRITICAL

| Metric | Target | Hard Deadline |
|--------|--------|---------------|
| First response | **< 15 min** | 30 minutes |
| Resolution path | < 1 hour | 2 hours |

**Почему:** Высший риск негативного отзыва, возврата и обращения в поддержку WB.

---

## B. Auto-Response Timing: Мгновенно или с задержкой?

### Рекомендация: ЗАДЕРЖКА 3-8 секунд + typing indicator

**НЕ мгновенные ответы.** Исследования показывают:

| Факт | Источник |
|------|----------|
| Пользователи предпочитают **короткую задержку**, а не нулевую — feels more realistic | [ResearchGate: "Faster Is Not Always Better"](https://www.researchgate.net/publication/324949980) |
| **2 секунды** — комфортное ожидание для чат-бота | [ChatBot.com](https://www.chatbot.com/blog/manage-the-speed-of-the-chat-with-the-conversation-delay/) |
| Typing indicators **нейтрализуют** негатив от задержки | [IJHCI 2025](https://www.tandfonline.com/doi/full/10.1080/10447318.2025.2508915) |
| **70% покупателей** предпочитают хороший ответ вместо мгновенного | [CM.com](https://www.cm.com/speed-customer-service/) |

### Конфигурация по типам

| Тип сообщения | Задержка авто-ответа | Typing | Почему |
|--------------|---------------------|--------|--------|
| **Чат (urgent)** | **3-5 сек** | Да | Быстро, но humanized |
| **Чат (normal)** | **5-8 сек** | Да | Feels thoughtful |
| **Отзыв (негатив)** | **НЕ отправлять автоматически** | — | AI draft → seller approval → send |
| **Отзыв (позитив)** | **5-10 сек** после одобрения | — | Seller одобряет, потом send |
| **Pre-purchase вопрос** | **3-5 сек** | Да | Скорость = конверсия |

### Критические правила

1. **НИКОГДА** не отправлять авто-ответ на негативный отзыв без одобрения человека
2. **Варьировать задержку** (3-8 сек random) — фиксированная задержка выглядит механически
3. **Масштабировать по длине**: `delay = 3 + (word_count / 40)`, max 12 сек
4. **Typing indicator** во время задержки в чатах
5. **Первый ответ** в разговоре — быстрее (2-3 сек, acknowledgment)
6. **Время суток**: 09:00-21:00 MSK — короче (3-5с), ночь — длиннее (5-10с)

---

## C. Priority Tiers

### Tier 1: URGENT (красный, звуковой алерт)

| Критерий | SLA | Эскалация |
|----------|-----|-----------|
| Негатив 1-2★ с "отложенной публикацией" | < 30 мин | на 15 мин |
| Интенты: `defect_not_working`, `wrong_item` | < 30 мин | на 15 мин |
| SLA deadline < 30 мин осталось | Немедленно | Уже escalated |
| Ручная эскалация продавцом | Немедленно | — |
| Упоминание Роспотребнадзора, суда | < 15 мин | на 5 мин |

### Tier 2: HIGH (жёлтый)

| Критерий | SLA | Эскалация |
|----------|-----|-----------|
| Pre-purchase: `sizing_fit`, `availability`, `compatibility` | < 1 час | на 30 мин |
| Интенты: `delivery_problem`, `return_refund`, `missing_parts` | < 1 час | на 30 мин |
| Негатив 3★ | < 1 час | на 30 мин |
| Client replied (продолжение диалога) | < 2 часа | на 1 час |
| Новый чат (первое сообщение) | < 1 час | на 30 мин |

### Tier 3: NORMAL (без индикатора)

| Критерий | SLA | Эскалация |
|----------|-----|-----------|
| Обычный post-purchase чат | < 4 часа | на 2 часа |
| `quality_complaint`, `usage_question` | < 4 часа | на 2 часа |
| Follow-up в активном разговоре | < 4 часа | на 2 часа |

### Tier 4: LOW (серый)

| Критерий | SLA | Эскалация |
|----------|-----|-----------|
| Позитивные отзывы 4-5★ | < 24 часа | на 12 часов |
| `positive_feedback` | < 24 часа | на 12 часов |

---

## D. Конфигурация для кода

```python
SLA_CONFIG = {
    "urgent": {
        "target": 30,           # 30 минут
        "hard_deadline": 60,    # 1 час
        "escalation_at": 15,    # Эскалация на 15 мин
    },
    "high": {
        "target": 60,           # 1 час
        "hard_deadline": 120,   # 2 часа
        "escalation_at": 30,    # Эскалация на 30 мин
    },
    "normal": {
        "target": 240,          # 4 часа
        "hard_deadline": 1440,  # 24 часа
        "escalation_at": 120,   # Эскалация на 2 часа
    },
    "low": {
        "target": 1440,         # 24 часа
        "hard_deadline": 2880,  # 48 часов
        "escalation_at": 720,   # Эскалация на 12 часов
    },
}

AUTO_RESPONSE_DELAY = {
    "urgent_chat": {"min_seconds": 3, "max_seconds": 5},
    "normal_chat": {"min_seconds": 5, "max_seconds": 8},
    "review_positive": {"min_seconds": 5, "max_seconds": 10},
    "review_negative": None,  # NO auto-send — human approval required
    "first_message_ack": {"min_seconds": 2, "max_seconds": 3},
    "word_count_factor": 0.025,  # +секунды за длину
    "max_delay": 12,
}

BUSINESS_HOURS = {
    "start": "09:00",
    "end": "21:00",
    "timezone": "Europe/Moscow",
    "weekend_multiplier": 1.5,  # Смягчение SLA на выходных без AI
}
```

---

## E. WB-специфика

### 3-дневное окно (критично)

```
Покупатель оставляет 1-3★ отзыв
  ↓
Авто-сообщение от шаблона продавца
  ↓ (Покупатель отвечает — часы пошли)
  ↓
  +--- 3 ДНЯ на решение ---+
  ↓                         ↓
Продавец решает          Нет ответа/решения
  ↓                         ↓
Просьба обновить         Отзыв публикуется как есть
оценку                   (если покупатель не ответил
  ↓                       на авто-сообщение —
Покупатель 1★ → 4-5★     отзыв НЕ публикуется)
```

**Импликация для AgentIQ:** Момент ответа покупателя в "отложенном" чате = **URGENT с 3-дневным таймером** в UI.
- First response: < 30 мин
- Resolution attempt: < 24ч (оставляя 2 дня на переписку)
- Если нет действия к 48ч: CRITICAL push-уведомление

### Стоимость опции отложенной публикации

~1% дополнительной комиссии. При обороте 10M руб/мес = **100-315K руб/мес**.
AgentIQ должен показывать ROI: если быстрый ответ предотвращает даже 2-3 негативных отзыва в месяц — комиссия окупается многократно.

### Polling limitation

WB Chat API: нет webhooks, только polling каждые 30 сек.
Total buyer-perceived response time: **30-60 секунд** (30с polling + processing + deliberate delay).
Это драматически лучше среднего по индустрии (4-6 часов).

### Формула рейтинга WB

- Последние 20,000 оценок за 2 года, с весом по свежести
- Свежие отзывы (< 90 дней) — полный вес, дальше exponential decay
- Скорость ответа на вопросы/отзывы — сигнал для ранжирования

→ Быстрые ответы на свежие отзывы имеют **непропорционально большое** влияние на рейтинг.

---

**Sources:** ReviewTrackers, Harvard Business Review, Freshworks 2025 Benchmark, LiveChatAI, CM.com, Fullview, eDesk, WB Pro Education, vc.ru marketplace, ResearchGate, ChatBot.com, IJHCI 2025, Nector.io, Ordergroove, seller.wildberries.ru, ppc.world, moneyplace.io
