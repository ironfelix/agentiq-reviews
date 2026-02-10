# AgentIQ — Инструкции для Claude Code

## 1. ПЕРЕД ЛЮБОЙ РАБОТОЙ — прочитай контекст

### Общий контекст проекта
- **`agentiq/docs/reviews/PROJECT_SUMMARY.md`** — архитектура, файлы, quickstart, API

### При работе с ответами на отзывы / communication analysis
- **`agentiq/docs/reviews/RESPONSE_GUARDRAILS.md`** — banned phrases, формат ответов
- **`agentiq/scripts/llm_analyzer.py:608-700`** — COMM_SYSTEM промпт + JSON формат
- **`agentiq/scripts/llm_analyzer.py:478-519`** — GUARDRAILS конфиг (banned phrases, лимиты)
- **`agentiq/docs/reviews/QUALITY_SCORE_FORMULA.md`** — формула quality_score (1-10)

### При работе с классификацией отзывов
- **`agentiq/docs/reviews/reasoning-rules.md`** — классификация, пороги, примеры
- **`agentiq/docs/reviews/CARD_FORMAT.md`** — формат карточек отчёта

### При работе с Chat Center
- **`agentiq/docs/chat-center/chat-center-real-data.html`** — ЭТАЛОН дизайна (HTML + 1110 строк CSS)
- **`agentiq/docs/chat-center/WB_CHAT_API_RESEARCH.md`** — исследование WB Chat API
- Прототипы: `agentiq/docs/prototypes/chat-center-final.html`

### При работе с лендингом
- **`agentiq/docs/prototypes/landing.html`** — основной source файл (~2050 строк)
- **`landing.html`** (корень репо) — копия для GitHub Pages, ВСЕГДА синхронизировать после изменений
- Деплой: `https://ironfelix.github.io/agentiq-reviews/landing.html`

---

## 2. Дизайн-система — ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ

### Reviews App (тёмная тема)
- Фон: `#0a1018`, карточки: `#141e2b`
- Акцент: `#e8a838` (оранжевый)
- Ошибки: `#e85454`, успех: `#4ecb71`, инфо: `#7db8e8`
- Шрифт: Montserrat, max-width: 560px

### Chat Center (светлая тема)
- Фон: `#ffffff`, акцент: `#1a73e8` (синий)
- Шрифт: Inter
- CSS: переменные, 1110 строк в прототипе
- HTML-структура:
  - `.chat-item`: marketplace-icon + chat-item-content > header/meta/preview
  - `.queue-section`: queue-header + список chat-item
  - `.message`: message-header (author + time) + message-content
  - `.ai-suggestion`: внутри chat-window, НЕ отдельная панель
- **ПРАВИЛО:** СНАЧАЛА читай HTML прототип, ПОТОМ копируй структуру и CSS

### Chat Center — Приоритизация и секции (КРИТИЧНО)
Три секции в левой панели, группировка по `sla_priority` + `chat_status`:

1. **«В работе»** — ТОЛЬКО `sla_priority === 'urgent'`
   - Красный dot (`.status-dot.waiting.risk`)
   - CSS класс `.urgent` на `.chat-item`
2. **«Ожидают ответа»** — НЕ urgent + (`chat_status === 'waiting'` ИЛИ `chat_status === 'client-replied'`)
   - Жёлтый dot (`.status-dot.waiting`) для waiting
   - Синий dot (`.status-dot.client-replied`) для client-replied
3. **«Все сообщения»** — `chat_status === 'responded'` ИЛИ `chat_status === 'auto-response'`
   - Зелёный dot (`.status-dot.responded`)
   - Серый dot (`.status-dot.auto-response`)

**НЕ ИСПОЛЬЗОВАТЬ `unread_count` для группировки!** Только `sla_priority` + `chat_status`.
**`high` priority ≠ urgent!** `high` идёт в «Ожидают ответа», НЕ в «В работе».

### Landing (тёмная тема)
- Фон: `#0a1018`, карточки: `#141e2b`, акцент: `#e8a838`
- Лого: `AGENT<span>IQ</span>` (span в цвете акцента)
- Favicon: inline SVG (data URI)
- Breakpoints: 400px, 640px, 768px
- Slider: overflow:hidden, scale(1.08) только на desktop

---

## 3. Критические правила генерации ответов

### "Как стоило ответить" = ГОТОВЫЙ ТЕКСТ
- Пиши **готовый текст ответа от лица продавца** в кавычках
- НЕ инструкции/размышления
- Правильно: `«Благодарим за отзыв! Нам жаль, что время работы не оправдало ожиданий...»`
- Неправильно: `«Стоило извиниться за недопонимание и вежливо объяснить...»`

### Banned phrases (НИКОГДА не писать)
- "вернём деньги", "гарантируем возврат/замену", "полный возврат", "бесплатную замену"
- "вы неправильно", "вы не так", "ваша вина", "сами виноваты"
- "обратитесь в поддержку" (= отписка)
- "ИИ", "бот", "нейросеть", "GPT", "ChatGPT", "автоматический ответ"

### Возврат/замена — ТОЛЬКО если покупатель сам попросил
- Триггеры: "возврат", "вернуть", "замена", "заменить", "обменять"
- Есть триггер → "Оформите возврат через ЛК WB как «не соответствует описанию»"
- Нет триггера → эмпатия + объяснение + помощь, БЕЗ упоминания возврата

---

## 4. Quality Score формула (ПРОЦЕНТНАЯ)

```
score = 10 - (harmful_pct × 0.1) - (risky_pct × 0.05) + (good_pct × 0.02)
```
- Процент от total_analyzed, НЕ абсолютное число
- Пример: 5 harmful из 202 (2.5%) → 10 - 0.25 = 9.75 → округление 10/10
- Контекст: «Спасибо!» на 5★ = acceptable, на 1★ = harmful (ignore)

---

## 5. WB API

### CDN (без авторизации)
Base: `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/`
- `V = nmId // 100000`, `P = nmId // 1000`
- `…/ru/card.json` → характеристики, описание
- `…/price-history.json` → копейки ÷ 100 = рубли

### WBCON Feedbacks API
- Base: `https://19-fb.wbcon.su/`, Auth: header `token: <JWT>`
- `POST /create_task_fb` → `GET /task_status` → `GET /get_results_fb`
- Пагинация: offset +100, ОБЯЗАТЕЛЬНЫЙ dedup по `fb_id` (дубликаты!)

---

## 6. Известные баги и паттерны

- **12-month filter** — feedbacks фильтруются за 366 дней (boundary case)
- **WBCON pagination** — offset возвращает дубликаты, dedup обязателен
- **Color normalization** — `color` может быть "4 шт. · 120 м", фильтровать через `is_color_variant()`
- **LLM distribution** — LLM может не классифицировать все отзывы, gap → `acceptable`
- **Celery timeout** — 300s для subprocess (DeepSeek бывает медленный)
- **Trend fallback** — 30-day window нужно >=3 отзывов, иначе split-half
- **f-string** — `!r` нельзя внутри f-string, используй temp var
- **venv** — system python нет dotenv, запускай через `source venv/bin/activate`

### Vite/Rollup build-time optimization (КРИТИЧНО!)
**Проблема:** Rollup оптимизирует `window.location.hostname` на момент сборки (localhost), поэтому runtime проверки не работают.

**НЕПРАВИЛЬНО** (будет захардкожен localhost):
```typescript
const isLocalhost = window.location.hostname === 'localhost';
const API_URL = isLocalhost ? 'http://localhost:8001/api' : '/api';
```

**ПРАВИЛЬНО** (используй interceptor для runtime проверки):
```typescript
const api = axios.create({ headers: { 'Content-Type': 'application/json' } });

api.interceptors.request.use((config) => {
  if (!config.baseURL) {
    const loc = window['location']; // indirect access prevents optimization
    const hostname = loc.hostname;
    config.baseURL = (hostname === 'localhost' || hostname === '127.0.0.1')
      ? 'http://localhost:8001/api'
      : '/api';
  }
  return config;
});
```

---

## 7. Структура comm-*.html (шаблон отчёта)

Порядок секций (эталон: `communication-loss-282955222.html`):
1. **Качество ответов** — verdict, gauge, stats (4 категории), loss-box ₽/мес
2. **Скорость ответа** — медиана/среднее для негатива и всех
3. **Качество ответов (breakdown)** — горизонтальные бары
4. **[Fashion]** Размер, ткань, цвет — таблица с тегами
5. **ТОП-3 худших** — цитата + тег + expandable "Как стоило ответить"
6. **Что видит покупатель** — perception list
7. **Скрытые проблемы в позитиве** — 4-5★ с жалобами
8. **Что делать** — "Почему важно" + numbered action list

---

## 8. Серверы и деплой

### VPS (dev/staging)
- **IP:** `79.137.175.164`
- **Домен (prod):** `agentiq.ru` (SSL через Let's Encrypt)
- **SSH ключ:** `~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem`
- **SSH команда:** `ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164`

### Prod URLs
- **Landing:** `https://agentiq.ru/`
- **App (Chat Center):** `https://agentiq.ru/app/`
- **API:** `https://agentiq.ru/api/`

### Структура на сервере
- `/var/www/agentiq/landing.html` — лендинг (корень `/`)
- `/var/www/agentiq/app/` — React SPA (`/app`)
- `/var/www/agentiq/assets/` — JS/CSS бандлы
- `/opt/agentiq/` — backend код + venv
- **Systemd сервис:** `agentiq-chat` (`sudo systemctl restart agentiq-chat`)
- **База:** PostgreSQL `agentiq_chat` (user: `agentiq`)

### Запуск локально
```bash
# Backend
cd agentiq/apps/chat-center/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001

# Frontend
cd agentiq/apps/chat-center/frontend
npm run dev -- --host 0.0.0.0
```

### Деплой frontend на prod
```bash
# 1. Собрать
cd agentiq/apps/chat-center/frontend
npm run build

# 2. Залить
rsync -avz --delete -e "ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem" \
  dist/ ubuntu@79.137.175.164:/tmp/agentiq-deploy/

# 3. Переместить
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164 "
  mv /tmp/agentiq-deploy/index.html /tmp/agentiq-deploy/landing.html
  sudo rm -rf /var/www/agentiq/assets/*
  sudo cp -r /tmp/agentiq-deploy/* /var/www/agentiq/
  sudo chown -R www-data:www-data /var/www/agentiq/
"
```

### Seed demo данных на prod
```bash
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo -u postgres psql -d agentiq_chat
# SQL INSERT statements...
```

### nginx конфиг
- Файл: `/etc/nginx/sites-enabled/agentiq`
- Landing: `location = / { try_files /landing.html =404; }`
- App: `location /app/ { alias /var/www/agentiq/app/; try_files $uri /app/index.html; }`
- API: `location /api/ { proxy_pass http://127.0.0.1:8001/api/; }`

### Celery (фоновые задачи)
**Сервисы:**
- `agentiq-celery` — worker (2 процесса)
- `agentiq-celery-beat` — scheduler для периодических задач

**Команды:**
```bash
sudo systemctl status agentiq-celery      # Статус worker
sudo systemctl status agentiq-celery-beat # Статус scheduler
sudo systemctl restart agentiq-celery     # Перезапуск
sudo journalctl -u agentiq-celery -f      # Логи в реальном времени
```

**Периодические задачи (beat_schedule):**
- `sync_all_sellers` — каждые 30 сек (синхронизация чатов с WB/Ozon)
- `check_sla_escalation` — каждые 5 мин (эскалация SLA)
- `analyze_pending_chats` — каждые 2 мин (AI анализ новых чатов)

**Файлы сервисов:**
- `/etc/systemd/system/agentiq-celery.service`
- `/etc/systemd/system/agentiq-celery-beat.service`

---

## 9. Workflow-правила

- **Landing sync:** после каждого изменения `agentiq/docs/prototypes/landing.html` → скопировать в `landing.html` (корень) + `frontend/public/landing.html` → push
- **Screenshots:** `screenshots/` папка, обработка через shots.so (transparent bg, perspective)
- **Не изобретай CSS** — копируй из прототипов и дизайн-системы
- **Не добавляй эмоджи** — если пользователь явно не попросил
- **Коммиты** — только когда пользователь просит, не proactively

---

## 10. Тестирование — ОБЯЗАТЕЛЬНО для критичных фич

### Когда писать автотесты
**Всегда пиши pytest тесты для:**
- API endpoints (auth, chats, messages, sync)
- Бизнес-логика (синхронизация чатов, AI анализ, SLA приоритизация)
- Интеграции с внешними API (WB Connector, Ozon Connector)
- Любые изменения в критичных путях (авторизация, отправка сообщений)

### Структура тестов (best practices)
```
backend/tests/
├── conftest.py          # Fixtures: test_client, auth_token, test_user_data
├── test_api.py          # API endpoint tests
├── test_auth.py         # Auth-specific tests
├── test_sync.py         # Sync task tests
├── test_wb_connector.py # WB API integration tests
└── test_ai_analyzer.py  # AI analysis tests
```

### Паттерн теста
```python
def test_feature_does_something(client, auth_token):
    """Описание что тестируем."""
    # Arrange
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Act
    response = client.post("/api/endpoint", json={...}, headers=headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["field"] == expected_value
```

### Запуск тестов
```bash
cd agentiq/apps/chat-center/backend
source venv/bin/activate
pytest -v                    # Все тесты
pytest -v tests/test_api.py  # Один файл
pytest -v -k "test_auth"     # По имени
```

### Покрытие (coverage)
- **Цель:** 80%+ для критичных модулей
- Проверка: `pytest --cov=app --cov-report=html`

---

## 11. Tech Debt и временные решения

### TODO: Требует доработки

#### Sync система (apps/chat-center/backend/app/tasks/sync.py)
- [ ] **Cursor persistence:** сейчас `last_cursor = None` — не сохраняется между синхронизациями
  - Нужно: хранить cursor в отдельной таблице `sync_state` или в `seller.sync_cursor`
  - Строка: `sync.py:114` — `# TODO: Store cursor in separate table or seller metadata`

#### Celery (apps/chat-center/backend/)
- [x] **Celery Beat:** настроен на проде (systemd сервисы agentiq-celery, agentiq-celery-beat)
  - Синхронизация каждые 30 сек, AI анализ каждые 2 мин, SLA эскалация каждые 5 мин

#### База данных
- [ ] **Миграции:** нет Alembic, колонки добавляются вручную
  - Нужно: настроить `alembic init` и автомиграции
  - При добавлении полей нужно `ALTER TABLE` на проде

#### Frontend
- [ ] **Error boundaries:** нет обработки ошибок React
- [ ] **Offline support:** нет кэширования / service worker

### Известные ограничения

#### WB Chat API
- **Нет order_id:** чат нельзя связать с заказом автоматически
  - Workaround: спрашивать номер заказа у покупателя
- **Нет unread_count:** считаем локально по `is_read = false`
- **Нет webhooks:** только polling каждые 60 сек

#### Безопасность
- [ ] **bcrypt версия:** требуется `bcrypt < 5.0` из-за несовместимости с passlib
  - Файл: `requirements.txt` — `bcrypt==4.3.0`
