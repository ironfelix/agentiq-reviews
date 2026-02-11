# AgentIQ Billing Architecture

## 1. Executive Summary

AgentIQ переходит на платную модель с hybrid pricing: базовая подписка (3 тира) + usage-based оверлимит по AI-запросам. Платёжный провайдер — YooKassa (рекуррентные платежи, 54-ФЗ из коробки, СБП 0%). Биллинг реализуется как изолированный модуль `app/billing/` внутри существующего FastAPI-приложения с отдельными моделями, роутерами и Celery-задачами. Feature gating через middleware-декоратор `@require_plan("pro")` на endpoint-уровне. Trial 14 дней с полным Pro-функционалом, конвертация через soft paywall.

---

## 2. Платёжный провайдер

### Выбор: YooKassa

| Критерий | YooKassa | CloudPayments | Тинькофф |
|---|---|---|---|
| Комиссия карты | 2.8% | 2.7-3.5% (инд.) | 2.49% (от оборота) |
| СБП | 0% | 0.4% | 0.4% |
| Рекурренты | Да (autopayments) | Да (recurrent) | Да |
| 54-ФЗ чеки | Встроенная касса 0 руб | Через партнёров | Через партнёров |
| API качество | Отличное, REST + idempotency | Хорошее | Среднее |
| Webhooks | payment.succeeded, payment.canceled, refund.succeeded | Много событий | Ограниченно |
| Подключение ИП | 1-3 дня | 3-5 дней | 5-7 дней |
| Python SDK | `yookassa` (офиц.) | Нет офиц. | Нет офиц. |
| Документация | Лучшая в РФ | Хорошая | Слабая |

**Обоснование:**
1. **54-ФЗ из коробки** — YooKassa предлагает встроенную онлайн-кассу за 0 руб, чеки отправляются автоматически. Не нужно покупать отдельную кассу (АТОЛ, Эвотор) и настраивать интеграцию.
2. **СБП 0%** — при среднем чеке 4990 руб экономия ~125 руб с каждого платежа vs карты (2.8%).
3. **Рекуррентные платежи** — `save_payment_method: true` при первом платеже, далее автосписание по `payment_method_id`.
4. **Idempotency key** — защита от дублирования платежей на уровне API.
5. **Python SDK** — `pip install yookassa`, минимум boilerplate.

### Схема взаимодействия

```
[Frontend] → POST /api/billing/checkout
    → [Backend] создаёт Payment в YooKassa (save_payment_method=true)
    → [YooKassa] возвращает confirmation_url
    → [Frontend] redirect на confirmation_url
    → [Покупатель] оплачивает
    → [YooKassa] webhook → POST /api/billing/webhook/yookassa
    → [Backend] активирует подписку, сохраняет payment_method_id
    → Ежемесячно: Celery task → создаёт Payment с payment_method_id
```

### Конфигурация YooKassa

```python
# app/config.py — добавить
class Settings(BaseSettings):
    # ... existing ...

    # YooKassa
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_WEBHOOK_SECRET: str = ""  # Не используется — YooKassa верифицирует по IP
    YOOKASSA_RETURN_URL: str = "https://agentiq.ru/app/billing/success"

    # Billing
    TRIAL_DAYS: int = 14
    GRACE_PERIOD_DAYS: int = 3
    BILLING_ENABLED: bool = True
```

---

## 3. Pricing Model

### Стартовая модель: Hybrid (Flat tiers + Usage overages)

```
┌─────────────┬──────────────┬──────────────┬───────────────┐
│             │   Starter    │     Pro      │  Enterprise   │
│             │  2 990 ₽/мес │ 6 990 ₽/мес  │  По запросу   │
├─────────────┼──────────────┼──────────────┼───────────────┤
│ Кабинеты МП │      1       │      3       │  Без лимита   │
│ Чаты/мес    │    500       │    3 000     │  Без лимита   │
│ AI-ответы   │    100       │    1 000     │  Без лимита   │
│ AI-анализ   │    200       │    3 000     │  Без лимита   │
│ Менеджеры   │      1       │      5       │  Без лимита   │
│ Reviews     │  1 артикул   │  10 артик.   │  Без лимита   │
│ SLA правила │      5       │     50       │  Без лимита   │
│ История     │   30 дней    │   365 дней   │  Без лимита   │
│ Приоритет   │   Обычный    │  Высокий     │  Dedicated    │
├─────────────┼──────────────┼──────────────┼───────────────┤
│ Overages    │              │              │               │
│ AI-ответ    │  5 ₽/шт      │  3 ₽/шт      │    —          │
│ Кабинет     │  990 ₽/мес   │  990 ₽/мес   │    —          │
│ Менеджер    │  490 ₽/мес   │  490 ₽/мес   │    —          │
└─────────────┴──────────────┴──────────────┴───────────────┘
```

**Почему именно эта модель:**
- **Flat tiers** понятны малым продавцам (большинство ЦА). Не надо считать "сколько я потрачу".
- **Usage overages** монетизируют крупных продавцов без завышения тарифов для мелких.
- **Per-cabinet** как add-on — отражает реальную ценность (каждый кабинет = отдельная интеграция).

### Roadmap эволюции pricing

| Фаза | Срок | Изменение |
|---|---|---|
| v1 | Март 2026 | Starter + Pro, оплата картой/СБП |
| v2 | Май 2026 | Enterprise (invoice billing), промокоды |
| v3 | Авг 2026 | Usage overages (AI-запросы), per-seat |
| v4 | Ноя 2026 | Annual plans (-20%), реферальная программа |
| v5 | 2027 | Per-cabinet pricing, A/B тесты тарифов |

---

## 4. Trial и Freemium

### Trial: 14 дней Pro

```
Регистрация → Trial Pro (14 дней, без карты)
    │
    ├─ День 1: Welcome email + онбординг
    ├─ День 7: "Осталась неделя" email + usage summary
    ├─ День 12: "2 дня до конца" + soft paywall в UI
    ├─ День 14: Trial истёк
    │
    ├─ Если оплатил → Pro подписка
    └─ Если не оплатил → Grace Period (3 дня)
         │
         ├─ Soft block: AI-ответы отключены, чаты read-only
         ├─ Данные сохраняются, синхронизация продолжается
         └─ День 17 → Hard block: только просмотр дашборда
              └─ День 47 (30 дней после hard block) → Данные удаляются
```

### Что доступно без подписки (после trial)

| Функция | Доступ |
|---|---|
| Просмотр дашборда | Да (read-only) |
| Просмотр чатов | Да (последние 10) |
| Ответ на чаты | Нет |
| AI-анализ | Нет |
| AI-ответы | Нет |
| Reviews Audit | Нет |
| SLA мониторинг | Нет |
| Экспорт данных | Да (свои данные — GDPR-like) |
| Настройки аккаунта | Да |

### Конвертация trial → paid

1. **Soft paywall** — при попытке использовать платную фичу показываем inline-блок "Подключите Pro для AI-ответов" с кнопкой оплаты. Не модалка — не раздражает.
2. **Usage meter** — в sidebar показываем "Использовано 73/100 AI-ответов". Визуальный прогресс мотивирует.
3. **Value-first** — trial даёт полный Pro, чтобы пользователь привык к AI-фичам и не смог без них.

---

## 5. Database Schema

### Новые таблицы

```sql
-- ================================================================
-- PLANS: Тарифные планы (конфигурируются из админки)
-- ================================================================
CREATE TABLE plans (
    id              SERIAL PRIMARY KEY,
    slug            VARCHAR(50) NOT NULL UNIQUE,         -- 'starter', 'pro', 'enterprise'
    name            VARCHAR(100) NOT NULL,               -- 'Starter', 'Pro', 'Enterprise'
    description     TEXT,

    -- Pricing
    price_monthly   INTEGER NOT NULL DEFAULT 0,          -- Цена в копейках (299000 = 2990 руб)
    price_annual    INTEGER,                             -- Годовая цена (если есть)
    currency        VARCHAR(3) NOT NULL DEFAULT 'RUB',

    -- Limits (NULL = unlimited)
    max_cabinets        INTEGER,                         -- Макс кабинетов МП
    max_chats_monthly   INTEGER,                         -- Макс чатов в месяц
    max_ai_responses    INTEGER,                         -- Макс AI-ответов в месяц
    max_ai_analyses     INTEGER,                         -- Макс AI-анализов в месяц
    max_managers        INTEGER,                         -- Макс менеджеров (seats)
    max_review_skus     INTEGER,                         -- Макс артикулов для Reviews
    max_sla_rules       INTEGER,                         -- Макс SLA-правил
    history_days        INTEGER,                         -- Глубина истории в днях

    -- Overage pricing (копейки за единицу, NULL = нет overages)
    overage_ai_response INTEGER,                         -- Цена за AI-ответ сверх лимита
    overage_cabinet     INTEGER,                         -- Цена за доп. кабинет/мес
    overage_manager     INTEGER,                         -- Цена за доп. менеджера/мес

    -- Feature flags (JSON — какие фичи включены)
    features        JSONB NOT NULL DEFAULT '{}',
    -- Пример: {"ai_responses": true, "ai_analysis": true, "reviews_audit": true,
    --          "sla_monitoring": true, "export": true, "priority_support": false,
    --          "custom_sla_rules": true, "api_access": false}

    -- Metadata
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_public       BOOLEAN NOT NULL DEFAULT true,       -- Показывать на pricing page
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_active ON plans(is_active, is_public, sort_order);

-- Seed data
INSERT INTO plans (slug, name, price_monthly, max_cabinets, max_chats_monthly, max_ai_responses, max_ai_analyses, max_managers, max_review_skus, max_sla_rules, history_days, overage_ai_response, overage_cabinet, overage_manager, features, sort_order) VALUES
('starter', 'Starter', 299000, 1, 500, 100, 200, 1, 1, 5, 30, 500, 99000, 49000, '{"ai_responses": true, "ai_analysis": true, "reviews_audit": true, "sla_monitoring": true, "export": false, "priority_support": false, "custom_sla_rules": false, "api_access": false}', 1),
('pro', 'Pro', 699000, 3, 3000, 1000, 3000, 5, 10, 50, 365, 300, 99000, 49000, '{"ai_responses": true, "ai_analysis": true, "reviews_audit": true, "sla_monitoring": true, "export": true, "priority_support": true, "custom_sla_rules": true, "api_access": false}', 2),
('enterprise', 'Enterprise', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{"ai_responses": true, "ai_analysis": true, "reviews_audit": true, "sla_monitoring": true, "export": true, "priority_support": true, "custom_sla_rules": true, "api_access": true}', 3);


-- ================================================================
-- SUBSCRIPTIONS: Подписки продавцов
-- ================================================================
CREATE TABLE subscriptions (
    id                  SERIAL PRIMARY KEY,
    seller_id           INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    plan_id             INTEGER NOT NULL REFERENCES plans(id),

    -- Status
    status              VARCHAR(30) NOT NULL DEFAULT 'trialing',
    -- 'trialing', 'active', 'past_due', 'grace_period', 'canceled', 'expired'

    -- Billing period
    billing_cycle       VARCHAR(10) NOT NULL DEFAULT 'monthly',  -- 'monthly', 'annual'
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end  TIMESTAMPTZ NOT NULL,

    -- Trial
    trial_start         TIMESTAMPTZ,
    trial_end           TIMESTAMPTZ,

    -- Cancellation
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,         -- Отменить в конце периода
    canceled_at         TIMESTAMPTZ,
    cancel_reason       TEXT,

    -- Payment method (YooKassa)
    payment_method_id   VARCHAR(255),                            -- YooKassa saved payment method
    payment_method_type VARCHAR(50),                             -- 'bank_card', 'sbp', 'yoo_money'
    payment_method_last4 VARCHAR(4),                             -- Последние 4 цифры карты

    -- Promo
    promo_code_id       INTEGER REFERENCES promo_codes(id),
    discount_percent    INTEGER DEFAULT 0,                       -- 0-100
    discount_end_at     TIMESTAMPTZ,

    -- Metadata
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_subscription_seller UNIQUE (seller_id)         -- 1 активная подписка на продавца
);

CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period_end ON subscriptions(current_period_end);
CREATE INDEX idx_subscriptions_seller ON subscriptions(seller_id);


-- ================================================================
-- INVOICES: Счета/платежи
-- ================================================================
CREATE TABLE invoices (
    id                  SERIAL PRIMARY KEY,
    seller_id           INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    subscription_id     INTEGER REFERENCES subscriptions(id),

    -- Invoice details
    invoice_number      VARCHAR(50) NOT NULL UNIQUE,             -- 'INV-2026-000001'
    status              VARCHAR(30) NOT NULL DEFAULT 'draft',
    -- 'draft', 'pending', 'paid', 'failed', 'refunded', 'void'

    -- Amounts (всё в копейках)
    subtotal            INTEGER NOT NULL DEFAULT 0,              -- До скидок
    discount_amount     INTEGER NOT NULL DEFAULT 0,
    tax_amount          INTEGER NOT NULL DEFAULT 0,              -- НДС (если применимо)
    total               INTEGER NOT NULL DEFAULT 0,              -- Итого к оплате
    currency            VARCHAR(3) NOT NULL DEFAULT 'RUB',

    -- Billing period this invoice covers
    period_start        TIMESTAMPTZ,
    period_end          TIMESTAMPTZ,

    -- Line items (JSON для гибкости)
    line_items          JSONB NOT NULL DEFAULT '[]',
    -- [{"description": "Pro подписка (март 2026)", "quantity": 1, "unit_price": 699000, "total": 699000},
    --  {"description": "Доп. AI-ответы (127 шт)", "quantity": 127, "unit_price": 300, "total": 38100}]

    -- Payment
    paid_at             TIMESTAMPTZ,
    payment_provider    VARCHAR(50),                             -- 'yookassa'
    payment_id          VARCHAR(255),                            -- YooKassa payment ID
    payment_method      VARCHAR(50),                             -- 'bank_card', 'sbp'

    -- Идемпотентность
    idempotency_key     VARCHAR(255) UNIQUE,

    -- Metadata
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_seller ON invoices(seller_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_payment_id ON invoices(payment_id);
CREATE INDEX idx_invoices_created ON invoices(created_at);


-- ================================================================
-- USAGE_TRACKING: Трекинг использования (агрегация по месяцам)
-- ================================================================
CREATE TABLE usage_records (
    id                  SERIAL PRIMARY KEY,
    seller_id           INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,

    -- Period
    period_start        DATE NOT NULL,                           -- Начало месяца (2026-03-01)
    period_end          DATE NOT NULL,                           -- Конец месяца (2026-03-31)

    -- Counters
    chats_count         INTEGER NOT NULL DEFAULT 0,
    ai_responses_count  INTEGER NOT NULL DEFAULT 0,
    ai_analyses_count   INTEGER NOT NULL DEFAULT 0,
    messages_sent       INTEGER NOT NULL DEFAULT 0,
    review_skus_count   INTEGER NOT NULL DEFAULT 0,

    -- Overages (вычисляются при биллинге)
    ai_responses_overage INTEGER NOT NULL DEFAULT 0,
    overage_amount      INTEGER NOT NULL DEFAULT 0,              -- В копейках

    -- Metadata
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_usage_seller_period UNIQUE (seller_id, period_start)
);

CREATE INDEX idx_usage_seller_period ON usage_records(seller_id, period_start);


-- ================================================================
-- BILLING_EVENTS: Аудит-лог (append-only)
-- ================================================================
CREATE TABLE billing_events (
    id                  BIGSERIAL PRIMARY KEY,
    seller_id           INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    subscription_id     INTEGER REFERENCES subscriptions(id),
    invoice_id          INTEGER REFERENCES invoices(id),

    event_type          VARCHAR(50) NOT NULL,
    -- 'subscription.created', 'subscription.activated', 'subscription.canceled',
    -- 'subscription.expired', 'subscription.plan_changed', 'subscription.renewed',
    -- 'payment.initiated', 'payment.succeeded', 'payment.failed',
    -- 'invoice.created', 'invoice.paid', 'invoice.refunded',
    -- 'trial.started', 'trial.ended', 'trial.converted',
    -- 'usage.limit_warning', 'usage.limit_reached',
    -- 'promo.applied', 'promo.expired'

    -- Event data
    data                JSONB NOT NULL DEFAULT '{}',
    -- Пример: {"plan_from": "starter", "plan_to": "pro", "prorate_amount": 350000}

    -- Source
    source              VARCHAR(30) NOT NULL DEFAULT 'system',
    -- 'system', 'user', 'webhook', 'admin', 'celery'

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_billing_events_seller ON billing_events(seller_id, created_at);
CREATE INDEX idx_billing_events_type ON billing_events(event_type, created_at);
-- Не нужен updated_at — append-only таблица


-- ================================================================
-- PROMO_CODES: Промокоды и скидки
-- ================================================================
CREATE TABLE promo_codes (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(50) NOT NULL UNIQUE,             -- 'LAUNCH30', 'FRIEND20'

    -- Discount
    discount_type       VARCHAR(20) NOT NULL DEFAULT 'percent',  -- 'percent', 'fixed'
    discount_value      INTEGER NOT NULL,                        -- 30 (%) или 100000 (коп)

    -- Restrictions
    applicable_plans    JSONB,                                   -- ["starter", "pro"] или null = все
    max_uses            INTEGER,                                 -- Макс общее кол-во использований
    max_uses_per_seller INTEGER DEFAULT 1,
    current_uses        INTEGER NOT NULL DEFAULT 0,

    -- Validity
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until         TIMESTAMPTZ,
    duration_months     INTEGER,                                 -- Сколько месяцев действует скидка

    -- Metadata
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_promo_codes_code ON promo_codes(code, is_active);
```

### Изменения в существующей таблице sellers

```sql
-- Добавить в sellers (связь с billing)
ALTER TABLE sellers ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'trial';
-- Кешированное поле для быстрого feature gating без JOIN на subscriptions.
-- Обновляется триггером/кодом при смене подписки.
-- Значения: 'trial', 'starter', 'pro', 'enterprise', 'expired'
```

### SQLAlchemy модели

```python
# app/billing/models.py

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    Text, ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price_monthly = Column(Integer, nullable=False, default=0)
    price_annual = Column(Integer)
    currency = Column(String(3), nullable=False, default="RUB")
    max_cabinets = Column(Integer)
    max_chats_monthly = Column(Integer)
    max_ai_responses = Column(Integer)
    max_ai_analyses = Column(Integer)
    max_managers = Column(Integer)
    max_review_skus = Column(Integer)
    max_sla_rules = Column(Integer)
    history_days = Column(Integer)
    overage_ai_response = Column(Integer)
    overage_cabinet = Column(Integer)
    overage_manager = Column(Integer)
    features = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(String(30), nullable=False, default="trialing")
    billing_cycle = Column(String(10), nullable=False, default="monthly")
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime(timezone=True))
    cancel_reason = Column(Text)
    payment_method_id = Column(String(255))
    payment_method_type = Column(String(50))
    payment_method_last4 = Column(String(4))
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"))
    discount_percent = Column(Integer, default=0)
    discount_end_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan = relationship("Plan", back_populates="subscriptions")
    seller = relationship("Seller", backref="subscription")
    invoices = relationship("Invoice", back_populates="subscription")

    __table_args__ = (
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_period_end", "current_period_end"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    invoice_number = Column(String(50), nullable=False, unique=True)
    status = Column(String(30), nullable=False, default="draft")
    subtotal = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    tax_amount = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="RUB")
    period_start = Column(DateTime(timezone=True))
    period_end = Column(DateTime(timezone=True))
    line_items = Column(JSON, nullable=False, default=list)
    paid_at = Column(DateTime(timezone=True))
    payment_provider = Column(String(50))
    payment_id = Column(String(255))
    payment_method = Column(String(50))
    idempotency_key = Column(String(255), unique=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subscription = relationship("Subscription", back_populates="invoices")

    __table_args__ = (
        Index("idx_invoices_seller", "seller_id"),
        Index("idx_invoices_status", "status"),
        Index("idx_invoices_payment_id", "payment_id"),
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    chats_count = Column(Integer, nullable=False, default=0)
    ai_responses_count = Column(Integer, nullable=False, default=0)
    ai_analyses_count = Column(Integer, nullable=False, default=0)
    messages_sent = Column(Integer, nullable=False, default=0)
    review_skus_count = Column(Integer, nullable=False, default=0)
    ai_responses_overage = Column(Integer, nullable=False, default=0)
    overage_amount = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("seller_id", "period_start", name="uq_usage_seller_period"),
        Index("idx_usage_seller_period", "seller_id", "period_start"),
    )


class BillingEvent(Base):
    __tablename__ = "billing_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    event_type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    source = Column(String(30), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_billing_events_seller", "seller_id", "created_at"),
        Index("idx_billing_events_type", "event_type", "created_at"),
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    discount_type = Column(String(20), nullable=False, default="percent")
    discount_value = Column(Integer, nullable=False)
    applicable_plans = Column(JSON)
    max_uses = Column(Integer)
    max_uses_per_seller = Column(Integer, default=1)
    current_uses = Column(Integer, nullable=False, default=0)
    valid_from = Column(DateTime(timezone=True), server_default=func.now())
    valid_until = Column(DateTime(timezone=True))
    duration_months = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## 6. Backend Architecture

### Файловая структура

```
app/
├── billing/                          # Изолированный биллинг-модуль
│   ├── __init__.py
│   ├── models.py                     # Plan, Subscription, Invoice, UsageRecord, BillingEvent, PromoCode
│   ├── schemas.py                    # Pydantic schemas для API
│   ├── router.py                     # FastAPI endpoints (/api/billing/*)
│   ├── webhook.py                    # Webhook handler (/api/billing/webhook/yookassa)
│   ├── service.py                    # Бизнес-логика (создание подписки, смена плана, биллинг)
│   ├── usage.py                      # Инкремент usage, проверка лимитов
│   ├── yookassa_client.py            # Обёртка над yookassa SDK
│   ├── feature_gate.py               # Декоратор @require_plan, @check_limit
│   └── tasks.py                      # Celery: рекурренты, напоминания, usage aggregation
├── api/
│   ├── auth.py                       # (existing) — добавить создание trial при register
│   ├── sellers.py                    # (existing)
│   ├── chats.py                      # (existing) — добавить @check_limit("chats")
│   └── messages.py                   # (existing) — добавить @check_limit("ai_responses")
├── middleware/
│   ├── auth.py                       # (existing)
│   └── billing.py                    # Middleware для инъекции subscription в request.state
├── models/
│   └── seller.py                     # (existing) — добавить subscription_tier поле
└── main.py                           # (existing) — подключить billing router
```

### API Endpoints

```python
# app/billing/router.py

from fastapi import APIRouter, Depends, HTTPException
from app.middleware.auth import get_current_seller
from app.billing import service, schemas

router = APIRouter(prefix="/billing", tags=["billing"])


# ---- Plans ----

@router.get("/plans", response_model=list[schemas.PlanResponse])
async def list_plans():
    """Публичный список тарифов для pricing page."""
    return await service.get_active_plans()


@router.get("/plans/{slug}", response_model=schemas.PlanResponse)
async def get_plan(slug: str):
    """Детали тарифа."""
    return await service.get_plan_by_slug(slug)


# ---- Subscription ----

@router.get("/subscription", response_model=schemas.SubscriptionResponse)
async def get_subscription(seller=Depends(get_current_seller)):
    """Текущая подписка продавца."""
    return await service.get_subscription(seller.id)


@router.post("/subscribe", response_model=schemas.CheckoutResponse)
async def subscribe(
    payload: schemas.SubscribeRequest,
    seller=Depends(get_current_seller),
):
    """
    Оформить/сменить подписку.
    Возвращает confirmation_url для оплаты через YooKassa.
    """
    return await service.create_checkout(seller, payload)


@router.post("/change-plan", response_model=schemas.ChangePlanResponse)
async def change_plan(
    payload: schemas.ChangePlanRequest,
    seller=Depends(get_current_seller),
):
    """
    Сменить тариф mid-cycle.
    Upgrade: доплата за остаток периода, применяется сразу.
    Downgrade: применяется в конце текущего периода.
    """
    return await service.change_plan(seller, payload)


@router.post("/cancel", response_model=schemas.SubscriptionResponse)
async def cancel_subscription(
    payload: schemas.CancelRequest,
    seller=Depends(get_current_seller),
):
    """Отменить подписку в конце текущего периода."""
    return await service.cancel_subscription(seller, payload)


@router.post("/reactivate", response_model=schemas.SubscriptionResponse)
async def reactivate_subscription(seller=Depends(get_current_seller)):
    """Отменить отмену (до конца периода)."""
    return await service.reactivate_subscription(seller)


# ---- Usage ----

@router.get("/usage", response_model=schemas.UsageResponse)
async def get_usage(seller=Depends(get_current_seller)):
    """Текущее использование за период."""
    return await service.get_current_usage(seller.id)


# ---- Invoices ----

@router.get("/invoices", response_model=list[schemas.InvoiceResponse])
async def list_invoices(seller=Depends(get_current_seller)):
    """История платежей."""
    return await service.get_invoices(seller.id)


# ---- Payment method ----

@router.post("/update-payment-method", response_model=schemas.CheckoutResponse)
async def update_payment_method(seller=Depends(get_current_seller)):
    """Привязать новую карту через YooKassa."""
    return await service.create_card_update_checkout(seller)


# ---- Promo ----

@router.post("/apply-promo", response_model=schemas.PromoResponse)
async def apply_promo(
    payload: schemas.ApplyPromoRequest,
    seller=Depends(get_current_seller),
):
    """Применить промокод."""
    return await service.apply_promo_code(seller, payload.code)
```

### Webhook Endpoint

```python
# app/billing/webhook.py

from fastapi import APIRouter, Request, HTTPException
from app.billing import service
import logging
import json

router = APIRouter(prefix="/billing/webhook", tags=["webhooks"])
logger = logging.getLogger(__name__)

# YooKassa webhook IPs (whitelist)
YOOKASSA_IPS = {
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11",
    "77.75.156.35",
    "77.75.154.128/25",
    "2a02:5180::/32",
}


@router.post("/yookassa")
async def yookassa_webhook(request: Request):
    """
    Обработка webhook от YooKassa.

    YooKassa не подписывает webhooks — верификация по IP.
    Events: payment.succeeded, payment.canceled, refund.succeeded
    """
    # 1. Verify source IP
    client_ip = request.client.host
    # В продакшне IP приходит через nginx X-Real-IP
    forwarded_for = request.headers.get("X-Real-IP", client_ip)

    # TODO: проверка IP по YOOKASSA_IPS (с поддержкой CIDR)
    # В dev-окружении пропускаем проверку

    # 2. Parse body
    body = await request.json()
    event_type = body.get("event")
    payment_object = body.get("object", {})

    logger.info(f"YooKassa webhook: {event_type}, payment_id={payment_object.get('id')}")

    # 3. Idempotency: check if we already processed this event
    payment_id = payment_object.get("id")

    # 4. Route event
    if event_type == "payment.succeeded":
        await service.handle_payment_succeeded(payment_object)
    elif event_type == "payment.canceled":
        await service.handle_payment_canceled(payment_object)
    elif event_type == "refund.succeeded":
        await service.handle_refund_succeeded(payment_object)
    else:
        logger.warning(f"Unknown webhook event: {event_type}")

    # YooKassa expects 200 OK
    return {"status": "ok"}
```

### Billing Service (бизнес-логика)

```python
# app/billing/service.py (ключевые методы)

from datetime import datetime, timedelta, timezone, date
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Plan, Subscription, Invoice, UsageRecord, BillingEvent
from app.billing.yookassa_client import YooKassaClient
from app.database import AsyncSessionLocal


async def create_trial_subscription(seller_id: int, db: AsyncSession):
    """Создать trial подписку при регистрации."""
    pro_plan = await db.execute(select(Plan).where(Plan.slug == "pro"))
    plan = pro_plan.scalar_one()

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=14)

    subscription = Subscription(
        seller_id=seller_id,
        plan_id=plan.id,
        status="trialing",
        billing_cycle="monthly",
        current_period_start=now,
        current_period_end=trial_end,
        trial_start=now,
        trial_end=trial_end,
    )
    db.add(subscription)

    # Billing event
    db.add(BillingEvent(
        seller_id=seller_id,
        event_type="trial.started",
        data={"plan": "pro", "trial_days": 14},
        source="system",
    ))

    await db.flush()
    return subscription


async def create_checkout(seller, payload) -> dict:
    """Создать платёж в YooKassa, вернуть URL для оплаты."""
    async with AsyncSessionLocal() as db:
        # Get plan
        plan = await db.execute(select(Plan).where(Plan.slug == payload.plan_slug))
        plan = plan.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Plan {payload.plan_slug} not found")

        # Calculate amount
        amount = plan.price_monthly  # kopecks

        # Apply promo if provided
        discount = 0
        if payload.promo_code:
            discount = await _calculate_discount(db, payload.promo_code, plan, amount)

        total = max(amount - discount, 0)

        # Create invoice
        invoice = Invoice(
            seller_id=seller.id,
            invoice_number=f"INV-{datetime.now().strftime('%Y')}-{uuid4().hex[:8].upper()}",
            status="pending",
            subtotal=amount,
            discount_amount=discount,
            total=total,
            line_items=[{
                "description": f"{plan.name} подписка",
                "quantity": 1,
                "unit_price": amount,
                "total": amount,
            }],
            idempotency_key=str(uuid4()),
        )
        db.add(invoice)
        await db.flush()

        # Create YooKassa payment
        client = YooKassaClient()
        payment = client.create_payment(
            amount=total / 100,  # YooKassa expects rubles
            currency="RUB",
            description=f"AgentIQ {plan.name} — {seller.email}",
            save_payment_method=True,  # Для рекуррентных платежей
            metadata={
                "seller_id": seller.id,
                "invoice_id": invoice.id,
                "plan_slug": plan.slug,
            },
            receipt={
                "customer": {"email": seller.email},
                "items": [{
                    "description": f"Подписка AgentIQ {plan.name}",
                    "quantity": "1.00",
                    "amount": {"value": f"{total / 100:.2f}", "currency": "RUB"},
                    "vat_code": 1,  # Без НДС (для ИП на УСН)
                    "payment_subject": "service",
                    "payment_mode": "full_payment",
                }],
            },
            idempotency_key=invoice.idempotency_key,
        )

        # Update invoice with payment ID
        invoice.payment_id = payment.id
        invoice.payment_provider = "yookassa"

        # Billing event
        db.add(BillingEvent(
            seller_id=seller.id,
            invoice_id=invoice.id,
            event_type="payment.initiated",
            data={"payment_id": payment.id, "amount": total, "plan": plan.slug},
            source="user",
        ))

        await db.commit()

        return {
            "confirmation_url": payment.confirmation.confirmation_url,
            "payment_id": payment.id,
            "invoice_id": invoice.id,
        }


async def handle_payment_succeeded(payment_object: dict):
    """Обработка успешного платежа (webhook)."""
    async with AsyncSessionLocal() as db:
        metadata = payment_object.get("metadata", {})
        seller_id = int(metadata["seller_id"])
        invoice_id = int(metadata["invoice_id"])
        plan_slug = metadata["plan_slug"]

        # Update invoice
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one()

        if invoice.status == "paid":
            return  # Idempotency: already processed

        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)
        invoice.payment_method = payment_object.get("payment_method", {}).get("type")

        # Get plan
        plan_result = await db.execute(select(Plan).where(Plan.slug == plan_slug))
        plan = plan_result.scalar_one()

        # Activate/update subscription
        sub_result = await db.execute(
            select(Subscription).where(Subscription.seller_id == seller_id)
        )
        subscription = sub_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=30)

        if subscription:
            subscription.plan_id = plan.id
            subscription.status = "active"
            subscription.current_period_start = now
            subscription.current_period_end = period_end
            subscription.cancel_at_period_end = False

            # Save payment method for recurring
            pm = payment_object.get("payment_method", {})
            if pm.get("saved"):
                subscription.payment_method_id = pm["id"]
                subscription.payment_method_type = pm.get("type")
                card = pm.get("card", {})
                subscription.payment_method_last4 = card.get("last4")
        else:
            subscription = Subscription(
                seller_id=seller_id,
                plan_id=plan.id,
                status="active",
                billing_cycle="monthly",
                current_period_start=now,
                current_period_end=period_end,
            )
            pm = payment_object.get("payment_method", {})
            if pm.get("saved"):
                subscription.payment_method_id = pm["id"]
                subscription.payment_method_type = pm.get("type")
                card = pm.get("card", {})
                subscription.payment_method_last4 = card.get("last4")
            db.add(subscription)

        # Update seller cached tier
        seller_result = await db.execute(
            select(Seller).where(Seller.id == seller_id)
        )
        seller = seller_result.scalar_one()
        seller.subscription_tier = plan.slug

        # Billing event
        db.add(BillingEvent(
            seller_id=seller_id,
            subscription_id=subscription.id,
            invoice_id=invoice.id,
            event_type="payment.succeeded",
            data={
                "payment_id": payment_object["id"],
                "amount": invoice.total,
                "plan": plan.slug,
            },
            source="webhook",
        ))

        await db.commit()


async def charge_recurring(subscription_id: int):
    """Рекуррентное списание (вызывается из Celery)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one()

        if not subscription.payment_method_id:
            # Нет сохранённого метода оплаты — переводим в past_due
            subscription.status = "past_due"
            db.add(BillingEvent(
                seller_id=subscription.seller_id,
                subscription_id=subscription.id,
                event_type="payment.failed",
                data={"reason": "no_payment_method"},
                source="celery",
            ))
            await db.commit()
            return

        # Get plan price
        plan_result = await db.execute(
            select(Plan).where(Plan.id == subscription.plan_id)
        )
        plan = plan_result.scalar_one()

        # Calculate overage
        usage = await _get_current_usage(db, subscription.seller_id)
        overage_amount = _calculate_overage(plan, usage)

        total = plan.price_monthly + overage_amount

        # Apply discount if active
        if subscription.discount_percent > 0:
            if not subscription.discount_end_at or subscription.discount_end_at > datetime.now(timezone.utc):
                discount = total * subscription.discount_percent // 100
                total -= discount

        # Create invoice
        invoice = Invoice(
            seller_id=subscription.seller_id,
            subscription_id=subscription.id,
            invoice_number=f"INV-{datetime.now().strftime('%Y')}-{uuid4().hex[:8].upper()}",
            status="pending",
            subtotal=plan.price_monthly + overage_amount,
            total=total,
            idempotency_key=str(uuid4()),
            line_items=_build_line_items(plan, usage, overage_amount),
        )
        db.add(invoice)
        await db.flush()

        # YooKassa autopayment
        client = YooKassaClient()
        try:
            payment = client.create_recurring_payment(
                amount=total / 100,
                payment_method_id=subscription.payment_method_id,
                description=f"AgentIQ {plan.name} — автопродление",
                metadata={
                    "seller_id": subscription.seller_id,
                    "invoice_id": invoice.id,
                    "plan_slug": plan.slug,
                },
                idempotency_key=invoice.idempotency_key,
            )
            invoice.payment_id = payment.id
            invoice.payment_provider = "yookassa"
        except Exception as e:
            invoice.status = "failed"
            subscription.status = "past_due"
            db.add(BillingEvent(
                seller_id=subscription.seller_id,
                subscription_id=subscription.id,
                invoice_id=invoice.id,
                event_type="payment.failed",
                data={"error": str(e)},
                source="celery",
            ))

        await db.commit()
```

### YooKassa Client

```python
# app/billing/yookassa_client.py

from yookassa import Configuration, Payment
from app.config import get_settings
import uuid


class YooKassaClient:
    def __init__(self):
        settings = get_settings()
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

    def create_payment(
        self,
        amount: float,
        currency: str,
        description: str,
        save_payment_method: bool = False,
        metadata: dict = None,
        receipt: dict = None,
        idempotency_key: str = None,
    ) -> Payment:
        """Создать платёж с редиректом на страницу оплаты."""
        settings = get_settings()

        payment_data = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YOOKASSA_RETURN_URL,
            },
            "capture": True,  # Автоматическое подтверждение
            "description": description,
            "save_payment_method": save_payment_method,
            "metadata": metadata or {},
        }

        if receipt:
            payment_data["receipt"] = receipt

        return Payment.create(
            payment_data,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    def create_recurring_payment(
        self,
        amount: float,
        payment_method_id: str,
        description: str,
        metadata: dict = None,
        idempotency_key: str = None,
    ) -> Payment:
        """Рекуррентный платёж (автосписание по сохранённому методу)."""
        payment_data = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "payment_method_id": payment_method_id,
            "capture": True,
            "description": description,
            "metadata": metadata or {},
        }

        return Payment.create(
            payment_data,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
```

### Feature Gating (декораторы)

```python
# app/billing/feature_gate.py

from functools import wraps
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.seller import Seller
from app.billing.models import Subscription, Plan, UsageRecord
from app.middleware.auth import get_current_seller


# Plan hierarchy for comparison
PLAN_HIERARCHY = {"expired": 0, "trial": 2, "starter": 1, "pro": 2, "enterprise": 3}


def require_plan(min_plan: str):
    """
    Декоратор: требует минимальный тариф.

    Использование:
        @router.post("/chats/{chat_id}/analyze")
        @require_plan("starter")
        async def analyze_chat(chat_id: int, seller: Seller = Depends(get_current_seller)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract seller from kwargs (injected by Depends)
            seller = kwargs.get("seller")
            if not seller:
                # Try to find seller in args
                for arg in args:
                    if isinstance(arg, Seller):
                        seller = arg
                        break

            if not seller:
                raise HTTPException(status_code=401, detail="Authentication required")

            tier = seller.subscription_tier or "expired"

            if PLAN_HIERARCHY.get(tier, 0) < PLAN_HIERARCHY.get(min_plan, 0):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "plan_required",
                        "required_plan": min_plan,
                        "current_plan": tier,
                        "message": f"Для этой функции нужен тариф {min_plan.capitalize()} или выше",
                        "upgrade_url": "/app/billing",
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def check_usage_limit(
    seller_id: int,
    resource: str,
    db: AsyncSession,
    increment: int = 1,
) -> dict:
    """
    Проверить лимит использования и инкрементировать счётчик.

    Returns: {"allowed": True/False, "current": N, "limit": N, "overage": bool}

    Использование:
        check = await check_usage_limit(seller.id, "ai_responses", db)
        if not check["allowed"]:
            raise HTTPException(403, detail=check)
    """
    # Get subscription with plan
    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan)
        .where(Subscription.seller_id == seller_id)
    )
    row = result.one_or_none()

    if not row:
        return {"allowed": False, "current": 0, "limit": 0, "reason": "no_subscription"}

    subscription, plan = row

    if subscription.status not in ("active", "trialing"):
        return {"allowed": False, "current": 0, "limit": 0, "reason": "subscription_inactive"}

    # Get limit for resource
    limit_map = {
        "chats": plan.max_chats_monthly,
        "ai_responses": plan.max_ai_responses,
        "ai_analyses": plan.max_ai_analyses,
    }
    limit = limit_map.get(resource)

    if limit is None:  # NULL = unlimited
        return {"allowed": True, "current": 0, "limit": None, "overage": False}

    # Get current usage
    from datetime import date
    today = date.today()
    period_start = today.replace(day=1)

    usage_result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.seller_id == seller_id,
            UsageRecord.period_start == period_start,
        )
    )
    usage = usage_result.scalar_one_or_none()

    if not usage:
        # Create usage record for this month
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period_end = next_month - timedelta(days=1)
        usage = UsageRecord(
            seller_id=seller_id,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(usage)
        await db.flush()

    # Get current count
    count_map = {
        "chats": usage.chats_count,
        "ai_responses": usage.ai_responses_count,
        "ai_analyses": usage.ai_analyses_count,
    }
    current = count_map.get(resource, 0)

    # Check overage capability
    overage_price_map = {
        "ai_responses": plan.overage_ai_response,
    }
    has_overage = overage_price_map.get(resource) is not None

    if current + increment > limit and not has_overage:
        return {
            "allowed": False,
            "current": current,
            "limit": limit,
            "overage": False,
            "reason": "limit_reached",
        }

    # Increment
    if resource == "chats":
        usage.chats_count += increment
    elif resource == "ai_responses":
        usage.ai_responses_count += increment
        if current + increment > limit:
            usage.ai_responses_overage += increment
    elif resource == "ai_analyses":
        usage.ai_analyses_count += increment

    return {
        "allowed": True,
        "current": current + increment,
        "limit": limit,
        "overage": current + increment > limit,
    }
```

### Celery Tasks (биллинг)

```python
# app/billing/tasks.py

from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import select, and_

from app.tasks import celery_app
from app.tasks.sync import run_async
from app.database import AsyncSessionLocal
from app.billing.models import Subscription, Plan, BillingEvent
from app.billing import service

import logging
logger = logging.getLogger(__name__)


@celery_app.task(name="app.billing.tasks.process_recurring_payments")
def process_recurring_payments():
    """
    Ежедневно: найти подписки, у которых заканчивается период,
    и запустить рекуррентное списание.

    Запускать за 1 день до окончания (buffer для retry).
    """
    async def _process():
        async with AsyncSessionLocal() as db:
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == "active",
                        Subscription.current_period_end <= tomorrow,
                        Subscription.cancel_at_period_end == False,
                        Subscription.payment_method_id != None,
                    )
                )
            )
            subscriptions = result.scalars().all()

            logger.info(f"Found {len(subscriptions)} subscriptions to renew")

            for sub in subscriptions:
                try:
                    await service.charge_recurring(sub.id)
                except Exception as e:
                    logger.error(f"Recurring charge failed for sub {sub.id}: {e}")

    run_async(_process())


@celery_app.task(name="app.billing.tasks.expire_trials")
def expire_trials():
    """Ежедневно: перевести истёкшие trial в grace_period."""
    async def _expire():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)

            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == "trialing",
                        Subscription.trial_end <= now,
                    )
                )
            )
            trials = result.scalars().all()

            for sub in trials:
                sub.status = "grace_period"
                # Update seller tier
                from app.models.seller import Seller
                seller_result = await db.execute(
                    select(Seller).where(Seller.id == sub.seller_id)
                )
                seller = seller_result.scalar_one()
                seller.subscription_tier = "expired"

                db.add(BillingEvent(
                    seller_id=sub.seller_id,
                    subscription_id=sub.id,
                    event_type="trial.ended",
                    source="celery",
                ))

                logger.info(f"Trial expired for seller {sub.seller_id}")

            await db.commit()

    run_async(_expire())


@celery_app.task(name="app.billing.tasks.handle_grace_period")
def handle_grace_period():
    """Ежедневно: перевести grace_period → expired после 3 дней."""
    async def _handle():
        async with AsyncSessionLocal() as db:
            threshold = datetime.now(timezone.utc) - timedelta(days=3)

            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status.in_(["grace_period", "past_due"]),
                        Subscription.current_period_end <= threshold,
                    )
                )
            )
            subs = result.scalars().all()

            for sub in subs:
                sub.status = "expired"

                from app.models.seller import Seller
                seller_result = await db.execute(
                    select(Seller).where(Seller.id == sub.seller_id)
                )
                seller = seller_result.scalar_one()
                seller.subscription_tier = "expired"

                db.add(BillingEvent(
                    seller_id=sub.seller_id,
                    subscription_id=sub.id,
                    event_type="subscription.expired",
                    source="celery",
                ))

            await db.commit()

    run_async(_handle())


@celery_app.task(name="app.billing.tasks.send_billing_reminders")
def send_billing_reminders():
    """
    Ежедневно: отправить напоминания:
    - Trial: 7 дней до конца, 2 дня до конца
    - Подписка: 3 дня до продления (информирование)
    - Grace: каждый день
    """
    # TODO: интегрировать email-сервис (SendPulse, Unisender)
    pass
```

### Регистрация Celery Beat

```python
# Добавить в app/tasks/__init__.py → beat_schedule:

"process-recurring-payments-daily": {
    "task": "app.billing.tasks.process_recurring_payments",
    "schedule": 86400.0,  # Каждые 24 часа
    "options": {"expires": 3600},
},
"expire-trials-daily": {
    "task": "app.billing.tasks.expire_trials",
    "schedule": 86400.0,
},
"handle-grace-period-daily": {
    "task": "app.billing.tasks.handle_grace_period",
    "schedule": 86400.0,
},
"send-billing-reminders-daily": {
    "task": "app.billing.tasks.send_billing_reminders",
    "schedule": 86400.0,
},
```

### Подключение в main.py

```python
# app/main.py — добавить:

from app.billing.router import router as billing_router
from app.billing.webhook import router as webhook_router

app.include_router(billing_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
```

### Middleware: инъекция subscription в request

```python
# app/middleware/billing.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class BillingMiddleware(BaseHTTPMiddleware):
    """
    Добавляет subscription_tier в request.state для быстрого доступа.
    Не блокирует запросы — только инъектирует данные.
    Блокировка происходит на уровне декораторов @require_plan.
    """
    async def dispatch(self, request: Request, call_next):
        # subscription_tier уже есть в seller.subscription_tier (cached field)
        # Middleware нужен только если хотим inject без зависимости от auth
        response = await call_next(request)
        return response
```

---

## 7. Frontend

### Новые экраны

#### 7.1 Pricing Page (`/app/billing`)

```
┌──────────────────────────────────────────────────────────┐
│  ← Назад                              AgentIQ Billing   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Выберите тариф             [Ежемесячно] / Ежегодно -20% │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Starter    │  │  ★ Pro      │  │ Enterprise  │     │
│  │  2 990₽/мес │  │  6 990₽/мес │  │ По запросу  │     │
│  │             │  │             │  │             │     │
│  │ 1 кабинет   │  │ 3 кабинета  │  │ Без лимитов │     │
│  │ 500 чатов   │  │ 3000 чатов  │  │             │     │
│  │ 100 AI      │  │ 1000 AI     │  │ Приоритетная│     │
│  │             │  │             │  │ поддержка   │     │
│  │ [Выбрать]   │  │ [Выбрать]   │  │ [Связаться] │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                          │
│  Промокод: [______________] [Применить]                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### 7.2 Subscription Page (`/app/billing/subscription`)

```
┌──────────────────────────────────────────────────────────┐
│  Текущий тариф: Pro                  Активна до 15.04.26 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Использование этого месяца:                             │
│  ┌──────────────────────────────────┐                    │
│  │ Чаты       ████████░░ 2,450/3,000│                    │
│  │ AI-ответы  ██████░░░░   623/1,000│                    │
│  │ AI-анализ  ████░░░░░░ 1,200/3,000│                    │
│  │ Кабинеты   ██████████     2/3    │                    │
│  └──────────────────────────────────┘                    │
│                                                          │
│  Способ оплаты: •••• 4242    [Изменить]                  │
│                                                          │
│  [Сменить тариф]  [Отменить подписку]                    │
│                                                          │
│  История платежей:                                       │
│  ┌────────────────────────────────────────────┐          │
│  │ 15.03.26  INV-2026-A1B2C3  Pro  6,990₽ ✓  │          │
│  │ 15.02.26  INV-2026-D4E5F6  Pro  6,990₽ ✓  │          │
│  └────────────────────────────────────────────┘          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### 7.3 Paywall (inline, не модалка)

```
┌──────────────────────────────────────────────────────────┐
│  ⚡ AI-ответы доступны на тарифе Starter и выше          │
│                                                          │
│  Автоматические ответы на сообщения покупателей          │
│  экономят до 3 часов в день.                             │
│                                                          │
│  [Подключить Starter — 2 990₽/мес]                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### TypeScript типы

```typescript
// types/billing.ts

export interface Plan {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  price_monthly: number;      // kopecks
  price_annual: number | null;
  max_cabinets: number | null;
  max_chats_monthly: number | null;
  max_ai_responses: number | null;
  max_ai_analyses: number | null;
  max_managers: number | null;
  max_review_skus: number | null;
  features: Record<string, boolean>;
}

export interface Subscription {
  id: number;
  plan: Plan;
  status: 'trialing' | 'active' | 'past_due' | 'grace_period' | 'canceled' | 'expired';
  billing_cycle: 'monthly' | 'annual';
  current_period_start: string;
  current_period_end: string;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  payment_method_type: string | null;
  payment_method_last4: string | null;
  discount_percent: number;
}

export interface Usage {
  chats_count: number;
  chats_limit: number | null;
  ai_responses_count: number;
  ai_responses_limit: number | null;
  ai_analyses_count: number;
  ai_analyses_limit: number | null;
  period_start: string;
  period_end: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  status: string;
  total: number;
  currency: string;
  paid_at: string | null;
  line_items: Array<{description: string; quantity: number; total: number}>;
  created_at: string;
}

export interface CheckoutResponse {
  confirmation_url: string;
  payment_id: string;
  invoice_id: number;
}
```

### API layer (добавить в api.ts)

```typescript
// services/billingApi.ts

import api from './api';
import type { Plan, Subscription, Usage, Invoice, CheckoutResponse } from '../types/billing';

export const billingApi = {
  getPlans: async (): Promise<Plan[]> => {
    const response = await api.get<Plan[]>('/billing/plans');
    return response.data;
  },

  getSubscription: async (): Promise<Subscription> => {
    const response = await api.get<Subscription>('/billing/subscription');
    return response.data;
  },

  subscribe: async (planSlug: string, promoCode?: string): Promise<CheckoutResponse> => {
    const response = await api.post<CheckoutResponse>('/billing/subscribe', {
      plan_slug: planSlug,
      promo_code: promoCode,
    });
    return response.data;
  },

  changePlan: async (planSlug: string): Promise<{ message: string }> => {
    const response = await api.post('/billing/change-plan', { plan_slug: planSlug });
    return response.data;
  },

  cancelSubscription: async (reason?: string): Promise<Subscription> => {
    const response = await api.post<Subscription>('/billing/cancel', { reason });
    return response.data;
  },

  getUsage: async (): Promise<Usage> => {
    const response = await api.get<Usage>('/billing/usage');
    return response.data;
  },

  getInvoices: async (): Promise<Invoice[]> => {
    const response = await api.get<Invoice[]>('/billing/invoices');
    return response.data;
  },

  applyPromo: async (code: string): Promise<{ discount_percent: number }> => {
    const response = await api.post('/billing/apply-promo', { code });
    return response.data;
  },

  updatePaymentMethod: async (): Promise<CheckoutResponse> => {
    const response = await api.post<CheckoutResponse>('/billing/update-payment-method');
    return response.data;
  },
};
```

### Paywall Hook

```typescript
// hooks/useBilling.ts

import { useCallback } from 'react';
import { billingApi } from '../services/billingApi';

export function useBilling(currentTier: string | undefined) {
  const canAccess = useCallback((requiredTier: string): boolean => {
    const hierarchy: Record<string, number> = {
      expired: 0,
      starter: 1,
      trial: 2,
      pro: 2,
      enterprise: 3,
    };
    const current = hierarchy[currentTier || 'expired'] ?? 0;
    const required = hierarchy[requiredTier] ?? 0;
    return current >= required;
  }, [currentTier]);

  const handleUpgrade = useCallback(async (planSlug: string) => {
    const checkout = await billingApi.subscribe(planSlug);
    window.location.href = checkout.confirmation_url;
  }, []);

  return { canAccess, handleUpgrade };
}
```

---

## 8. Feature Gating

### Матрица фич по планам

| Фича | Expired | Starter | Pro / Trial | Enterprise |
|---|---|---|---|---|
| Просмотр чатов (read-only) | 10 последних | Все | Все | Все |
| Ответ на чаты | -- | Да | Да | Да |
| AI-анализ чата | -- | 200/мес | 3000/мес | Без лимита |
| AI-генерация ответа | -- | 100/мес | 1000/мес | Без лимита |
| SLA мониторинг | -- | Да | Да | Да |
| Кастомные SLA правила | -- | -- | Да | Да |
| Reviews Audit | -- | 1 артикул | 10 артикулов | Без лимита |
| Экспорт данных | Свои данные | -- | Да | Да |
| API доступ | -- | -- | -- | Да |
| Приоритетная поддержка | -- | -- | Да | Да |
| Кабинеты МП | 1 | 1 | 3 | Без лимита |
| Менеджеры (seats) | 1 | 1 | 5 | Без лимита |
| История | 0 | 30 дней | 365 дней | Без лимита |

### Где проверять в коде

```python
# Пример: endpoint отправки сообщения
# app/api/messages.py

@router.post("/messages")
@require_plan("starter")  # Декоратор — быстрая проверка tier
async def send_message(
    payload: MessageCreate,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    # Лимит проверяется внутри
    check = await check_usage_limit(seller.id, "chats", db)
    if not check["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "usage_limit_reached",
                "resource": "chats",
                **check,
            }
        )
    # ... send message logic


# Пример: AI-анализ
# app/api/chats.py

@router.post("/chats/{chat_id}/analyze")
@require_plan("starter")
async def analyze_chat(
    chat_id: int,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    check = await check_usage_limit(seller.id, "ai_analyses", db)
    if not check["allowed"]:
        raise HTTPException(status_code=429, detail=check)
    # ... analyze logic
```

### Soft vs Hard limits

| Ситуация | Тип | Действие |
|---|---|---|
| 80% лимита AI-ответов | Soft | UI-уведомление: "Осталось 20 AI-ответов" |
| 100% лимита (есть overages) | Soft | UI-предупреждение + продолжаем + считаем overage |
| 100% лимита (нет overages) | Hard | HTTP 429 + paywall в UI |
| Trial истёк | Soft (3 дня) | Grace: read-only чаты, нет AI |
| Подписка не оплачена | Soft (3 дня) | Grace: аналогично |
| Grace истёк | Hard | Только дашборд + настройки + экспорт данных |

---

## 9. Масштабирование

### Multi-tenancy

Текущая архитектура уже tenant-based: `seller_id` на всех таблицах. Подписка привязана к seller (1:1). Для мульти-кабинетности один seller подключает несколько маркетплейсов — это уже поддержано через поле `marketplace` в Chat.

**Будущее:** если один seller = несколько кабинетов одного маркетплейса (разные API ключи), нужна таблица `marketplace_connections`:

```sql
-- Фаза 3+
CREATE TABLE marketplace_connections (
    id          SERIAL PRIMARY KEY,
    seller_id   INTEGER NOT NULL REFERENCES sellers(id),
    marketplace VARCHAR(50) NOT NULL,
    name        VARCHAR(255),               -- "Основной WB", "WB Косметика"
    client_id   VARCHAR(255),
    api_key_encrypted TEXT,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
-- Биллинг считает COUNT(marketplace_connections) vs plan.max_cabinets
```

### Добавление нового маркетплейса

Биллинг не зависит от маркетплейсов. Limits на `chats_count` и `ai_responses_count` считаются глобально. Новый маркетплейс = новый connector + entries в `marketplace_connections`. Ноль изменений в billing.

### Добавление нового pricing tier

Просто INSERT в `plans`. Никаких миграций. Feature flags в JSONB. Limits — nullable Integer columns. Добавить новый лимит = `ALTER TABLE plans ADD COLUMN max_X INTEGER`.

### A/B тесты pricing

```sql
-- Добавить в plans
ALTER TABLE plans ADD COLUMN ab_group VARCHAR(20);
-- 'control', 'variant_a', 'variant_b'

-- При регистрации:
-- seller.ab_group = random.choice(['control', 'variant_a', 'variant_b'])
-- Показывать plans WHERE ab_group = seller.ab_group OR ab_group IS NULL
```

### Enterprise: Invoice billing

Enterprise клиенты платят по счёту (постоплата). Для них:
- `subscription.billing_cycle = 'invoice'`
- Invoice создаётся вручную или по Celery в конце месяца
- Статус `pending` пока не оплатят
- Не блокируем при неоплате — менеджер разбирается
- Отдельный флаг `plan.features.invoice_billing = true`

---

## 10. Безопасность и юридика РФ

### PCI DSS

| Что | Кто отвечает |
|---|---|
| Хранение карт | YooKassa (PCI DSS Level 1) |
| Токены платёжных методов | Мы храним `payment_method_id` (это НЕ карта) |
| Шифрование в transit | HTTPS (nginx + Let's Encrypt) |
| 3D-Secure | YooKassa |

**Правило: мы НИКОГДА не видим и не храним номера карт. Только `payment_method_id` от YooKassa.**

### Webhook Security

YooKassa не подписывает вебхуки. Верификация — по IP whitelist:

```python
# В webhook.py (production)
import ipaddress

YOOKASSA_NETWORKS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.154.128/25"),
]

def verify_yookassa_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in network for network in YOOKASSA_NETWORKS)
```

### Idempotency

Каждый платёж создаётся с `idempotency_key` (UUID). YooKassa гарантирует: повторный запрос с тем же ключом вернёт тот же результат. Invoice хранит `idempotency_key` с UNIQUE constraint.

### Audit Trail

Таблица `billing_events` — append-only. Без UPDATE и DELETE. Хранит ВСЕ действия с биллингом: создание подписки, оплата, отмена, смена плана, применение промокода. Поле `source` позволяет отличить действия пользователя от системных.

### 54-ФЗ и онлайн-кассы

| Вопрос | Ответ |
|---|---|
| Нужна ли нам касса? | Да, при продаже услуг физлицам онлайн |
| Кто отправляет чеки? | YooKassa (встроенная касса за 0 руб) |
| Что передаём? | `receipt` в API при создании платежа |
| `vat_code` | `1` (без НДС) для ИП на УСН, `4` (НДС 20%) для ООО на ОСНО |
| `payment_subject` | `service` |
| `payment_mode` | `full_payment` |
| ИП vs ООО | Разница только в `vat_code`. Подключение одинаковое |

### Чеклист безопасности

- [ ] HTTPS only для webhook endpoint
- [ ] IP whitelist для YooKassa webhooks
- [ ] `idempotency_key` на каждый платёж
- [ ] Никаких карт в нашей БД — только `payment_method_id`
- [ ] `receipt` в каждом платеже (54-ФЗ)
- [ ] `billing_events` append-only, без DELETE
- [ ] Rate limit на `/billing/subscribe` (1 req/10s per seller)
- [ ] Логирование всех webhook-вызовов
- [ ] Проверка `metadata.seller_id` при обработке webhook
- [ ] Не доверять `amount` из webhook — сверять с invoice

### Оферта

Необходимо разместить на сайте:
1. **Договор-оферту** на оказание услуг (SaaS)
2. **Политику конфиденциальности** (152-ФЗ)
3. **Согласие на рекуррентные платежи** — галочка при привязке карты

---

## 11. Implementation Roadmap

### Фаза 1: Базовый биллинг (2 недели)

**Неделя 1:**
- [ ] Создать `app/billing/` модуль (models, schemas, router)
- [ ] Alembic миграция для новых таблиц
- [ ] Seed `plans` (starter, pro, enterprise)
- [ ] `subscription_tier` field в Seller
- [ ] Trial creation при регистрации
- [ ] `GET /billing/plans` endpoint
- [ ] `GET /billing/subscription` endpoint

**Неделя 2:**
- [ ] YooKassa интеграция (create payment, webhook)
- [ ] `POST /billing/subscribe` + redirect flow
- [ ] Webhook handler (`payment.succeeded`, `payment.canceled`)
- [ ] Activation flow: webhook → subscription active → seller.subscription_tier updated
- [ ] Celery: `expire_trials`, `handle_grace_period`
- [ ] Frontend: pricing page, subscription page

### Фаза 2: Feature Gating (1 неделя)

- [ ] `@require_plan` декоратор
- [ ] `check_usage_limit` функция
- [ ] Добавить gates на existing endpoints (analyze, send_message)
- [ ] `UsageRecord` increment при каждом AI-запросе
- [ ] Frontend: paywall component, usage meter
- [ ] `GET /billing/usage` endpoint

### Фаза 3: Рекурренты и история (1 неделя)

- [ ] Celery: `process_recurring_payments`
- [ ] `POST /billing/cancel` + `POST /billing/reactivate`
- [ ] `GET /billing/invoices` + invoice generation
- [ ] Frontend: invoice history, cancel flow
- [ ] Email-уведомления (trial expiry, payment success, payment failed)

### Фаза 4: Промокоды и upgrade/downgrade (1 неделя)

- [ ] PromoCode CRUD (admin-only)
- [ ] `POST /billing/apply-promo`
- [ ] `POST /billing/change-plan` с prorate-расчётом
- [ ] Frontend: promo input, change plan modal
- [ ] Тесты: unit + integration для billing service

### Фаза 5: Polish (1 неделя)

- [ ] Webhook IP whitelist (production)
- [ ] Rate limiting на billing endpoints
- [ ] Оферта + политика конфиденциальности на лендинг
- [ ] Monitoring: alerting на failed payments
- [ ] Load testing: concurrent payments
- [ ] Документация API в Swagger

**Итого: 6 недель** от начала до production-ready биллинга.

### Dependencies

```
pip install yookassa==3.*
# requirements.txt:
yookassa>=3.0.0
```

### Environment Variables (production)

```bash
# .env
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_xxx
YOOKASSA_RETURN_URL=https://agentiq.ru/app/billing/success
TRIAL_DAYS=14
GRACE_PERIOD_DAYS=3
BILLING_ENABLED=true
```

---

## Appendix A: Prorate Calculation (смена тарифа mid-cycle)

```python
def calculate_prorate(
    old_plan_price: int,   # kopecks/month
    new_plan_price: int,   # kopecks/month
    days_remaining: int,
    days_in_period: int,
) -> int:
    """
    Upgrade: возвращает доплату (положительное число).
    Downgrade: возвращает 0 (применяется в конце периода).
    """
    if new_plan_price <= old_plan_price:
        return 0  # Downgrade — бесплатно, применяется в конце периода

    daily_diff = (new_plan_price - old_plan_price) / days_in_period
    prorate_amount = int(daily_diff * days_remaining)

    return max(prorate_amount, 0)


# Пример:
# Starter (299000 коп) → Pro (699000 коп), осталось 15 из 30 дней
# daily_diff = (699000 - 299000) / 30 = 13333 коп/день
# prorate = 13333 * 15 = 200000 коп = 2000 руб доплата
```

## Appendix B: Invoice Number Generation

```python
from datetime import datetime
import asyncio

async def generate_invoice_number(db: AsyncSession) -> str:
    """
    Format: INV-YYYY-NNNNNN
    Sequential per year, gap-free.
    """
    year = datetime.now().year
    result = await db.execute(
        text("""
            SELECT COUNT(*) + 1 FROM invoices
            WHERE invoice_number LIKE :pattern
        """),
        {"pattern": f"INV-{year}-%"},
    )
    seq = result.scalar()
    return f"INV-{year}-{seq:06d}"
```
