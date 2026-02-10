-- AgentIQ MVP+ Chat Center — PostgreSQL Schema
-- Version: 1.0
-- Date: 2026-02-08
-- Multi-marketplace chat center (Ozon, WB, Yandex)

-- ============================================
-- TABLE: sellers
-- Продавцы с credentials для маркетплейсов
-- ============================================

CREATE TABLE sellers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    marketplace VARCHAR(50) NOT NULL DEFAULT 'ozon',  -- ozon, wildberries, yandex, avito

    -- Credentials (encrypted)
    client_id VARCHAR(255),
    api_key_encrypted TEXT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT sellers_marketplace_check CHECK (marketplace IN ('ozon', 'wildberries', 'yandex', 'avito'))
);

CREATE INDEX idx_sellers_active ON sellers(is_active, marketplace);
CREATE INDEX idx_sellers_last_sync ON sellers(last_sync_at) WHERE is_active = TRUE;

COMMENT ON TABLE sellers IS 'Продавцы с подключенными аккаунтами маркетплейсов';
COMMENT ON COLUMN sellers.api_key_encrypted IS 'Encrypted with Fernet (symmetric encryption)';

-- ============================================
-- TABLE: chats
-- Чаты с покупателями (unified для всех маркетплейсов)
-- ============================================

CREATE TABLE chats (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    marketplace VARCHAR(50) NOT NULL,

    -- External IDs
    marketplace_chat_id VARCHAR(255) NOT NULL,  -- chat_id из API маркетплейса
    order_id VARCHAR(100),                      -- order_number (для Ozon, Яндекс)
    product_id VARCHAR(100),                    -- nmId для WB, SKU для Ozon

    -- Customer info
    customer_name VARCHAR(255),                 -- "Иван П." (partially hidden)
    customer_id VARCHAR(100),                   -- external customer ID

    -- Chat status
    status VARCHAR(50) DEFAULT 'open',          -- open, closed, resolved
    unread_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    first_message_at TIMESTAMP,

    -- SLA
    sla_deadline_at TIMESTAMP,                  -- calculated deadline based on rules
    sla_priority VARCHAR(20) DEFAULT 'normal',  -- urgent, high, normal, low

    -- Metadata
    metadata JSONB,                             -- flexible field for marketplace-specific data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT chats_status_check CHECK (status IN ('open', 'closed', 'resolved')),
    CONSTRAINT chats_priority_check CHECK (sla_priority IN ('urgent', 'high', 'normal', 'low')),
    UNIQUE(seller_id, marketplace_chat_id)      -- avoid duplicates
);

CREATE INDEX idx_chats_seller ON chats(seller_id, status, last_message_at DESC);
CREATE INDEX idx_chats_unread ON chats(seller_id, unread_count) WHERE unread_count > 0;
CREATE INDEX idx_chats_sla ON chats(sla_deadline_at) WHERE status = 'open' AND sla_deadline_at IS NOT NULL;
CREATE INDEX idx_chats_marketplace ON chats(marketplace, status);
CREATE INDEX idx_chats_updated ON chats(updated_at DESC);

COMMENT ON TABLE chats IS 'Чаты с покупателями (unified для всех маркетплейсов)';
COMMENT ON COLUMN chats.metadata IS 'JSONB для marketplace-specific полей (posting_number, etc.)';

-- ============================================
-- TABLE: messages
-- Сообщения в чатах
-- ============================================

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,

    -- External ID
    external_message_id VARCHAR(255) NOT NULL,  -- message_id из API

    -- Direction & Content
    direction VARCHAR(20) NOT NULL,             -- incoming (от покупателя), outgoing (от продавца)
    text TEXT,
    attachments JSONB,                          -- [{"type": "image", "url": "...", "file_name": "..."}]

    -- Author (для incoming)
    author_type VARCHAR(20),                    -- customer, seller, system
    author_id VARCHAR(100),

    -- Status
    status VARCHAR(20) DEFAULT 'sent',          -- pending, sent, delivered, read, failed
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,

    -- Timestamps
    sent_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT messages_direction_check CHECK (direction IN ('incoming', 'outgoing')),
    CONSTRAINT messages_author_check CHECK (author_type IN ('customer', 'seller', 'system', NULL)),
    CONSTRAINT messages_status_check CHECK (status IN ('pending', 'sent', 'delivered', 'read', 'failed')),
    UNIQUE(chat_id, external_message_id)        -- avoid duplicates
);

CREATE INDEX idx_messages_chat ON messages(chat_id, sent_at DESC);
CREATE INDEX idx_messages_unread ON messages(is_read, sent_at DESC) WHERE direction = 'incoming';
CREATE INDEX idx_messages_status ON messages(status) WHERE status IN ('pending', 'failed');

COMMENT ON TABLE messages IS 'Сообщения в чатах (incoming + outgoing)';
COMMENT ON COLUMN messages.attachments IS 'JSONB array of attachments';

-- ============================================
-- TABLE: sla_rules
-- Правила SLA для автоматического расчета deadlines
-- ============================================

CREATE TABLE sla_rules (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,

    -- Rule config
    name VARCHAR(255) NOT NULL,
    condition_type VARCHAR(50) NOT NULL,        -- keyword, chat_type, rating, time_based
    condition_value TEXT,                       -- JSON or string (e.g., "брак|возврат|дефект")
    deadline_minutes INTEGER NOT NULL,          -- SLA deadline в минутах
    priority INTEGER DEFAULT 100,               -- higher = more priority (100 = normal)

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT sla_rules_condition_check CHECK (condition_type IN ('keyword', 'chat_type', 'rating', 'time_based', 'unread_count'))
);

CREATE INDEX idx_sla_rules_seller ON sla_rules(seller_id, is_active);
CREATE INDEX idx_sla_rules_priority ON sla_rules(priority DESC) WHERE is_active = TRUE;

COMMENT ON TABLE sla_rules IS 'Правила SLA для автоматического расчета deadlines';
COMMENT ON COLUMN sla_rules.priority IS 'Higher number = higher priority (evaluated first)';

-- Example SLA rules:
INSERT INTO sla_rules (seller_id, name, condition_type, condition_value, deadline_minutes, priority, is_active) VALUES
(1, 'Срочные жалобы (брак, возврат)', 'keyword', 'брак|возврат|дефект|бракованный|некачественный', 120, 200, TRUE),
(1, 'Низкий рейтинг (1-2★)', 'rating', '1-2', 60, 180, TRUE),
(1, 'Вопросы о доставке', 'keyword', 'доставка|трек|когда придет|где заказ', 240, 150, TRUE),
(1, 'Обычные вопросы', 'chat_type', 'question', 480, 100, TRUE),
(1, 'Положительные отзывы (4-5★)', 'rating', '4-5', 1440, 50, TRUE);

-- ============================================
-- TABLE: filters
-- Сохранённые фильтры пользователей
-- ============================================

CREATE TABLE filters (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,

    -- Filter config
    name VARCHAR(100) NOT NULL,
    filters JSONB NOT NULL,                     -- {"unread_only": true, "status": "open", "marketplace": "ozon"}
    is_default BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(seller_id, name)
);

CREATE INDEX idx_filters_seller ON filters(seller_id, is_default);

COMMENT ON TABLE filters IS 'Сохранённые фильтры пользователей для быстрого доступа';
COMMENT ON COLUMN filters.filters IS 'JSONB с параметрами фильтра';

-- Example saved filters:
INSERT INTO filters (seller_id, name, filters, is_default) VALUES
(1, 'Срочные непрочитанные', '{"unread_only": true, "sla_priority": "urgent", "sort": "sla_deadline"}', TRUE),
(1, 'Все открытые', '{"status": "open", "sort": "last_message_at"}', FALSE),
(1, 'Только Ozon', '{"marketplace": "ozon", "status": "open"}', FALSE);

-- ============================================
-- TABLE: chat_sync_state
-- Состояние синхронизации для polling (incremental sync)
-- ============================================

CREATE TABLE chat_sync_state (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    marketplace VARCHAR(50) NOT NULL,

    -- Sync state
    last_sync_at TIMESTAMP NOT NULL,
    last_message_timestamp TIMESTAMP,           -- для incremental sync (since_timestamp)
    last_message_id VARCHAR(255),               -- для incremental sync (from_message_id)

    -- Error tracking
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    last_error_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(seller_id, marketplace)
);

CREATE INDEX idx_sync_state_seller ON chat_sync_state(seller_id, marketplace);
CREATE INDEX idx_sync_state_errors ON chat_sync_state(error_count) WHERE error_count > 0;

COMMENT ON TABLE chat_sync_state IS 'Состояние синхронизации для polling (incremental sync)';

-- ============================================
-- TABLE: ai_suggestions
-- История AI suggestions для анализа и кэширования
-- ============================================

CREATE TABLE ai_suggestions (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,

    -- Suggestion
    suggested_text TEXT NOT NULL,
    reasoning TEXT,                             -- почему эта suggestion была сгенерирована
    confidence FLOAT,                           -- 0.0-1.0

    -- Status
    status VARCHAR(20) DEFAULT 'pending',       -- pending, accepted, rejected, edited
    edited_text TEXT,                           -- если пользователь отредактировал

    -- Model info
    model_name VARCHAR(50),                     -- "deepseek-chat"
    model_version VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    used_at TIMESTAMP,

    CONSTRAINT ai_suggestions_status_check CHECK (status IN ('pending', 'accepted', 'rejected', 'edited'))
);

CREATE INDEX idx_ai_suggestions_chat ON ai_suggestions(chat_id, created_at DESC);
CREATE INDEX idx_ai_suggestions_status ON ai_suggestions(status, created_at DESC);

COMMENT ON TABLE ai_suggestions IS 'История AI suggestions для анализа и кэширования';
COMMENT ON COLUMN ai_suggestions.confidence IS 'Confidence score 0.0-1.0 from AI model';

-- ============================================
-- VIEWS
-- ============================================

-- View: Urgent chats (SLA истекает в течение 30 минут)
CREATE OR REPLACE VIEW v_urgent_chats AS
SELECT
    c.*,
    s.name AS seller_name,
    EXTRACT(EPOCH FROM (c.sla_deadline_at - NOW()))/60 AS minutes_remaining
FROM chats c
JOIN sellers s ON c.seller_id = s.id
WHERE
    c.status = 'open'
    AND c.sla_deadline_at IS NOT NULL
    AND c.sla_deadline_at <= NOW() + INTERVAL '30 minutes'
ORDER BY c.sla_deadline_at ASC;

COMMENT ON VIEW v_urgent_chats IS 'Срочные чаты (SLA истекает в течение 30 минут)';

-- View: Chat summary (для UI списка чатов)
CREATE OR REPLACE VIEW v_chat_summary AS
SELECT
    c.id,
    c.seller_id,
    c.marketplace,
    c.marketplace_chat_id,
    c.customer_name,
    c.status,
    c.unread_count,
    c.last_message_at,
    c.sla_deadline_at,
    c.sla_priority,
    s.name AS seller_name,
    m.text AS last_message_text,
    m.direction AS last_message_direction,
    CASE
        WHEN c.sla_deadline_at IS NOT NULL AND c.sla_deadline_at <= NOW() THEN 'expired'
        WHEN c.sla_deadline_at IS NOT NULL AND c.sla_deadline_at <= NOW() + INTERVAL '30 minutes' THEN 'urgent'
        ELSE 'normal'
    END AS sla_status
FROM chats c
JOIN sellers s ON c.seller_id = s.id
LEFT JOIN LATERAL (
    SELECT text, direction
    FROM messages
    WHERE chat_id = c.id
    ORDER BY sent_at DESC
    LIMIT 1
) m ON TRUE
ORDER BY c.last_message_at DESC;

COMMENT ON VIEW v_chat_summary IS 'Сводка по чатам для UI списка (с последним сообщением)';

-- ============================================
-- TRIGGERS
-- ============================================

-- Trigger: Update updated_at на изменение записи
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sellers_updated_at BEFORE UPDATE ON sellers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_chats_updated_at BEFORE UPDATE ON chats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_sla_rules_updated_at BEFORE UPDATE ON sla_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_filters_updated_at BEFORE UPDATE ON filters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger: Update chat.updated_at при добавлении нового сообщения
CREATE OR REPLACE FUNCTION update_chat_on_new_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chats
    SET
        last_message_at = NEW.sent_at,
        unread_count = CASE
            WHEN NEW.direction = 'incoming' THEN unread_count + 1
            ELSE unread_count
        END,
        updated_at = NOW()
    WHERE id = NEW.chat_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chat_on_message AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION update_chat_on_new_message();

COMMENT ON TRIGGER trigger_update_chat_on_message ON messages IS 'Обновляет chat.last_message_at и unread_count';

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function: Calculate SLA deadline для чата
CREATE OR REPLACE FUNCTION calculate_sla_deadline(p_chat_id INTEGER)
RETURNS TIMESTAMP AS $$
DECLARE
    v_seller_id INTEGER;
    v_first_message TEXT;
    v_created_at TIMESTAMP;
    v_best_rule RECORD;
    v_deadline TIMESTAMP;
BEGIN
    -- Получить chat info
    SELECT seller_id, metadata->>'first_message', first_message_at
    INTO v_seller_id, v_first_message, v_created_at
    FROM chats
    WHERE id = p_chat_id;

    -- Найти подходящее правило SLA (highest priority)
    SELECT * INTO v_best_rule
    FROM sla_rules
    WHERE
        seller_id = v_seller_id
        AND is_active = TRUE
        AND (
            (condition_type = 'keyword' AND v_first_message ~* condition_value)
            OR condition_type != 'keyword'
        )
    ORDER BY priority DESC
    LIMIT 1;

    -- Рассчитать deadline
    IF v_best_rule IS NOT NULL THEN
        v_deadline := v_created_at + (v_best_rule.deadline_minutes || ' minutes')::INTERVAL;
    ELSE
        -- Default: 24 часа
        v_deadline := v_created_at + INTERVAL '24 hours';
    END IF;

    RETURN v_deadline;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_sla_deadline(INTEGER) IS 'Рассчитывает SLA deadline для чата на основе правил';

-- ============================================
-- SEED DATA (для тестирования)
-- ============================================

-- Test seller
INSERT INTO sellers (name, email, marketplace, client_id, api_key_encrypted, is_active) VALUES
('Test Seller', 'test@example.com', 'ozon', '123456', 'encrypted_api_key_here', TRUE);

-- ============================================
-- GRANTS (опционально)
-- ============================================

-- Grant permissions для приложения
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agentiq_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agentiq_app;

-- ============================================
-- MIGRATION NOTES
-- ============================================

-- Для будущих маркетплейсов (WB, Яндекс, Avito):
-- 1. Добавить значение в sellers.marketplace constraint
-- 2. Адаптировать metadata JSONB для специфичных полей
-- 3. Создать соответствующий connector класс в backend

-- Для масштабирования:
-- 1. Партиционирование messages по sent_at (по месяцам)
-- 2. Архивирование старых чатов (status = closed + 90 дней)
-- 3. Read replicas для аналитики

-- End of schema.sql
