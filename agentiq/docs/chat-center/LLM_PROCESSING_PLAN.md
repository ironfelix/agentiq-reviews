# План обработки LLM для Chat Center

**Создан:** 2026-02-10
**Статус:** Исследование и планирование
**Автор:** Claude Code

---

## Краткое содержание

Документ анализирует текущее состояние LLM-обработки в Chat Center и предлагает улучшения для обработки пустых сообщений, тайминга AI-анализа и отображения AI-рекомендаций.

---

## 1. Анализ текущего состояния

### 1.1 Поток обработки сообщений

```
WB API Events → WBConnector.fetch_messages() → sync.py → Database
                                                   ↓
                                           analyze_pending_chats (Celery Beat, каждые 2 мин)
                                                   ↓
                                           AIAnalyzer.analyze_chat()
                                                   ↓
                                           Chat.ai_suggestion_text, Chat.ai_analysis_json
```

**Ключевые файлы:**
- `/backend/app/services/wb_connector.py` — интеграция с WB API
- `/backend/app/tasks/sync.py` — задачи синхронизации и триггеры AI-анализа
- `/backend/app/services/ai_analyzer.py` — интеграция с LLM (DeepSeek)
- `/backend/app/api/chats.py` — REST API с эндпоинтом ручного анализа

### 1.2 Что работает

| Функция | Статус | Расположение |
|---------|--------|--------------|
| Синхронизация сообщений из WB | Работает | `sync.py:_sync_wb()` |
| Задача AI-анализа | Работает | `sync.py:analyze_chat_with_ai()` |
| Периодический анализ | Работает | Celery Beat каждые 2 мин |
| Кнопка ручного анализа | Работает | `POST /api/chats/{id}/analyze` |
| AI-рекомендация в правой панели | Работает | `App.tsx` панель контекста |
| AI-рекомендация в ChatWindow | Работает | `ChatWindow.tsx:224-244` |
| Применение guardrails | Работает | `ai_analyzer.py:_apply_guardrails()` |

### 1.3 Что НЕ работает / требует улучшения

| Проблема | Влияние | Приоритет |
|----------|---------|-----------|
| Пустые сообщения не обрабатываются | Пользователи видят пустые сообщения | Высокий |
| Нет индикатора «Анализируется...» | Пользователи не знают, что анализ запущен | Средний |
| AI-рекомендации появляются через 2+ минуты | Плохой UX в реальном времени | Высокий |
| Нет плейсхолдеров для изображений | Путаница при сообщениях только с картинками | Средний |
| Вложения не отображаются | Потеря контекста из изображений | Средний |

---

## 2. Анализ проблем и решения

### 2.1 Пустые сообщения и изображения

#### Текущее поведение

**WB API возвращает:**
```json
{
  "message": {
    "text": "",
    "files": [{"fileName": "image.jpg", "downloadID": "abc123"}]
  }
}
```

**Текущий код в `wb_connector.py:205-224`:**
```python
messages.append({
    "text": event.get("message", {}).get("text", ""),
    "attachments": [
        {
            "type": "file",
            "file_name": f.get("fileName", ""),
            "download_id": f.get("downloadID", "")
        }
        for f in event.get("message", {}).get("files", [])
    ],
    ...
})
```

**Проблема:** Текст — пустая строка, вложения сохраняются, но не отображаются во фронтенде.

#### Предлагаемое решение

**Изменения бэкенда (`wb_connector.py`):**

```python
# Добавить после строки 224
def _normalize_message_text(text: str, attachments: list) -> str:
    """Генерирует отображаемый текст для сообщений с изображениями/файлами."""
    if text and text.strip():
        return text.strip()

    if attachments:
        file_count = len(attachments)
        if file_count == 1:
            return "[Изображение]"
        return f"[{file_count} изображений]"

    return ""  # Действительно пустое сообщение — будет отфильтровано
```

**Изменения фронтенда (`ChatWindow.tsx`):**

```tsx
// Добавить в renderMessages()
const getMessageContent = (message: Message) => {
  if (message.text && message.text.trim()) {
    return message.text;
  }

  if (message.attachments && message.attachments.length > 0) {
    const count = message.attachments.length;
    return (
      <div className="message-attachment-placeholder">
        <svg>...</svg>
        {count === 1 ? "Изображение" : `${count} изображений`}
        <span className="attachment-note">Изображения недоступны в API</span>
      </div>
    );
  }

  return <span className="empty-message">Пустое сообщение</span>;
};
```

#### MVP-правила для пустых сообщений

1. **Если `text` пуст, но есть `attachments`** — показывать плейсхолдер «[Изображение]»
2. **Если `text` пуст И нет attachments** — фильтровать, не показывать в UI
3. **Для AI-анализа** — пропускать пустые сообщения, добавлять в контекст: «Клиент отправил изображение (недоступно)»
4. **Счётчик непрочитанных** — не увеличивать для действительно пустых сообщений
5. **Превью последнего сообщения** — показывать «[Изображение]», если текст пуст, но есть вложения

---

### 2.2 Тайминг определения интента и AI-анализа

#### Текущая реализация

```
sync_all_sellers (каждые 30с)
    → sync_seller_chats()
        → _upsert_chat_and_messages()

analyze_pending_chats (каждые 2 мин)
    → найти чаты где:
        - unread_count > 0
        - ai_suggestion_text IS NULL
        - chat_status IN ('waiting', 'client-replied')
    → analyze_chat_with_ai() для каждого (макс 10)
```

**Проблема:** Задержка 2 минуты — слишком долго для поддержки в реальном времени.

#### Анализ вариантов

| Вариант | Плюсы | Минусы | Задержка |
|---------|-------|--------|----------|
| **A: Анализ при синхронизации** | Мгновенно | Блокирует синхронизацию, риск таймаута | ~5с |
| **B: Анализ при открытии** | Только для просматриваемых чатов | Задержка при первом открытии | ~3с |
| **C: Фоновый после синхронизации (текущий)** | Неблокирующий | Задержка 2+ мин | ~120с |
| **D: Event-driven мгновенный** | Почти реальное время | Сложно, нужен WebSocket | ~5с |

#### Рекомендуемый подход: Гибридный (B + C)

**Фаза 1 (MVP):** Оставить фоновый анализ, добавить on-demand при открытии чата

```python
# В chats.py get_chat() или новый эндпоинт
@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int, ...):
    chat = await get_chat_by_id(chat_id, db)

    # Запустить анализ если нужно (неблокирующий)
    if chat.ai_suggestion_text is None and chat.unread_count > 0:
        analyze_chat_with_ai.delay(chat_id)
        chat.analysis_status = "pending"  # Новое поле

    return chat
```

**Фаза 2:** Уменьшить интервал Celery Beat до 30 секунд

```python
# В tasks/__init__.py
"analyze-pending-chats-every-30s": {
    "task": "app.tasks.sync.analyze_pending_chats",
    "schedule": 30.0,  # Было 120с
},
```

**Фаза 3:** WebSocket для обновлений в реальном времени (будущее)

#### Индикатор «Анализируется...»

**Бэкенд:** Добавить поле `analysis_status` в модель Chat

```python
# В models/chat.py
analysis_status = Column(String(20), default=None, nullable=True)
# Значения: null, "pending", "analyzing", "complete", "error"
```

**Фронтенд:** Показывать индикатор в панели контекста

```tsx
// В App.tsx панель контекста
{selectedChat?.analysis_status === 'pending' && (
  <div className="analysis-status">
    <div className="spinner" />
    Анализируется...
  </div>
)}
```

**Поток обновления:**
1. Чат открыт с `ai_suggestion_text = null` → установить `analysis_status = "pending"`
2. Celery-задача стартует → установить `analysis_status = "analyzing"`
3. Задача завершена → установить `analysis_status = "complete"`, заполнить `ai_suggestion_text`
4. Фронтенд получает обновление через polling или WebSocket

---

### 2.3 AI-рекомендации в ChatWindow

#### Текущее состояние

**AI-рекомендация УЖЕ отображается** в `ChatWindow.tsx:224-244`:

```tsx
{chat.ai_suggestion_text && (
  <div className="ai-suggestion" onClick={handleUseAISuggestion}>
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
  </div>
)}
```

**Почему может не появляться:**

1. **`ai_suggestion_text` равен null** — анализ ещё не запускался
2. **Анализ упал** — ошибка DeepSeek API, fallback не сохранён
3. **Чат не соответствует критериям** — `unread_count = 0` или `chat_status` не waiting
4. **Последнее сообщение от продавца** — анализ возвращает `recommendation: null` по дизайну

#### Диагностический чеклист

| Проверка | Ожидаемо | Фактически |
|----------|----------|------------|
| `chat.ai_suggestion_text` в ответе API | Строка или null | ? |
| `ai_analysis_json` заполнен | JSON-строка | ? |
| DeepSeek API ключ настроен | `DEEPSEEK_API_KEY` в .env | ? |
| Celery worker запущен | `celery -A app.tasks worker` | ? |
| Celery beat запущен | `celery -A app.tasks beat` | ? |

#### Исправления

**1. Всегда показывать AI-панель, индицировать статус:**

```tsx
// В ChatWindow.tsx
{chat.ai_suggestion_text ? (
  <div className="ai-suggestion" onClick={handleUseAISuggestion}>
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
  </div>
) : chat.unread_count > 0 ? (
  <div className="ai-suggestion ai-suggestion--pending">
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">
      <span className="spinner" /> Генерируется...
    </div>
  </div>
) : (
  <div className="ai-suggestion ai-suggestion--empty">
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text text-muted">
      Нет ожидающих сообщений
    </div>
  </div>
)}
```

**2. Запускать анализ при открытии чата, если отсутствует:**

```tsx
// В App.tsx handleSelectChat()
const handleSelectChat = useCallback(async (chat: Chat) => {
  setSelectedChat(chat);
  fetchMessages(chat.id);

  // Запустить AI-анализ если отсутствует и есть непрочитанные
  if (!chat.ai_suggestion_text && chat.unread_count > 0) {
    try {
      await chatApi.analyzeChat(chat.id, { async_mode: true });
    } catch (e) {
      console.warn('Не удалось запустить анализ:', e);
    }
  }
  ...
}, []);
```

**3. Обеспечить сохранение fallback-анализа:**

```python
# В ai_analyzer.py analyze_chat_for_db()
if analysis:
    chat.ai_analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
    chat.ai_suggestion_text = analysis.get("recommendation")
    # ^ Эта строка уже есть, но проверить если recommendation = null
    if not chat.ai_suggestion_text and analysis.get("intent"):
        # Сгенерировать fallback если LLM не вернул рекомендацию
        chat.ai_suggestion_text = analyzer._fallback_analysis(
            messages_data, chat.customer_name
        ).get("recommendation")
```

---

## 3. Лучшие практики индустрии

### 3.1 Тайминг определения интента

**Zendesk Answer Bot / Intercom Fin / Freshdesk Freddy:**

| Инструмент | Подход | Задержка |
|------------|--------|----------|
| Zendesk | Реальное время при наборе | <1с |
| Intercom | При отправке сообщения (webhook) | 2-3с |
| Freshdesk | Фоновый + on-demand | 5-10с |
| Gorgias | Реальное время со стримингом | <2с |

**Лучшая практика:** Анализировать при получении сообщения (webhook/event), а не периодическим polling.

### 3.2 Паттерны отображения AI-рекомендаций

**Распространённые паттерны:**

1. **Inline под сообщениями** (Intercom) — AI-рекомендация как «черновик» пузырём
2. **Боковая панель** (Zendesk) — панель контекста с рекомендацией + редактирование
3. **Быстрые действия** (Freshdesk) — кнопки для типовых ответов
4. **Стриминг ответа** (Gorgias) — посимвольное отображение

**Рекомендация для AgentIQ:**
- Основной: Inline в ChatWindow (текущая реализация)
- Вторичный: Панель контекста для редактирования
- Добавить: Кнопки быстрых действий для шаблонных ответов

### 3.3 Обработка вложений/медиа

**Подходы индустрии:**

1. **Миниатюры** — маленькое превью, клик для увеличения
2. **OCR/Vision анализ** — извлечение текста из изображений через GPT-4V
3. **Плейсхолдер со скачиванием** — «[Изображение] Нажмите для скачивания»
4. **Иконки типов файлов** — разные иконки для изображений, PDF и т.д.

**MVP-рекомендация:** Плейсхолдер с пояснением, в будущем: интеграция GPT-4V

### 3.4 Уверенность и редактирование

**Лучшие практики:**
- Показывать оценку уверенности (высокая/средняя/низкая)
- Разрешать редактирование одним кликом перед отправкой
- Отслеживать отредактированные рекомендации для улучшения модели
- Предоставлять несколько вариантов рекомендаций

---

## 4. План реализации

### Фаза 1: MVP-исправления (1-2 дня)

| Задача | Файл | Приоритет |
|--------|------|-----------|
| Обработка пустых сообщений с вложениями | `wb_connector.py`, `ChatWindow.tsx` | Высокий |
| Добавить индикатор «Анализируется...» | `ChatWindow.tsx`, `App.tsx` | Высокий |
| Запускать анализ при открытии чата | `App.tsx` | Высокий |
| Обеспечить сохранение fallback-рекомендации | `ai_analyzer.py` | Высокий |

### Фаза 2: Улучшения UX (3-5 дней)

| Задача | Файл | Приоритет |
|--------|------|-----------|
| Уменьшить интервал анализа до 30с | `tasks/__init__.py` | Средний |
| Добавить поле `analysis_status` в Chat | `models/chat.py`, `schemas/chat.py` | Средний |
| Показывать статус анализа в UI | `App.tsx`, `ChatWindow.tsx` | Средний |
| Плейсхолдеры вложений с иконками | `ChatWindow.tsx`, `index.css` | Средний |

### Фаза 3: Реальное время (будущее)

| Задача | Сложность | Влияние |
|--------|-----------|---------|
| WebSocket для live-обновлений | Высокая | Высокое |
| GPT-4V для анализа изображений | Средняя | Среднее |
| Стриминг AI-ответов | Средняя | Высокое |
| Несколько вариантов рекомендаций | Средняя | Среднее |

---

## 5. Краткие MVP-правила

### Пустые сообщения

```
ЕСЛИ text.trim() == "" И attachments.length > 0:
    display_text = "[Изображение]" или "[{n} изображений]"
    for_ai_context = "Клиент отправил изображение (содержимое недоступно)"
    increment_unread = true

ЕСЛИ text.trim() == "" И attachments.length == 0:
    display_text = null (отфильтровать)
    increment_unread = false
```

### Тайминг AI-анализа

```
ПРИ sync_complete:
    запустить analyze_pending_chats async (каждые 30с)

ПРИ chat_open:
    ЕСЛИ ai_suggestion_text == null И unread_count > 0:
        запустить analyze_chat_with_ai async
        показать "Анализируется..."

ПРИ analysis_complete:
    обновить chat.ai_suggestion_text
    обновить chat.analysis_status = "complete"
    обновить UI (polling или WebSocket)
```

### Отображение AI-рекомендаций

```
ЕСЛИ ai_suggestion_text != null:
    показать рекомендацию в ChatWindow (кликабельную для использования)
    показать детали в панели контекста

ЕСЛИ ai_suggestion_text == null И unread_count > 0:
    показать плейсхолдер "Генерируется..."

ЕСЛИ ai_suggestion_text == null И unread_count == 0:
    показать "Нет ожидающих сообщений"
```

---

## 6. Технический долг и заметки

1. **Курсор синхронизации не сохраняется** — каждая синхронизация начинается сначала (см. `sync.py:117-121`)
2. **Таймаут DeepSeek** — 30с может быть мало для сложных чатов
3. **Нет retry при ошибке анализа** — неудачные анализы не повторяются автоматически
4. **Polling vs WebSocket** — текущий polling (10с) неэффективен

---

## 7. Метрики успеха

| Метрика | Текущее | Цель |
|---------|---------|------|
| Время до первой AI-рекомендации | ~2 мин | <10с |
| Доля чатов с рекомендацией | Неизвестно | >90% ожидающих чатов |
| Путаница с пустыми сообщениями | Высокая | Ноль |
| Жалобы на отсутствие рекомендаций | Неизвестно | <5% |

---

## Приложение: Ссылки на код

### Ключевые файлы

| Файл | Назначение |
|------|------------|
| `backend/app/tasks/sync.py` | Celery-задачи синхронизации и анализа |
| `backend/app/services/wb_connector.py` | Клиент WB API |
| `backend/app/services/ai_analyzer.py` | Интеграция с DeepSeek LLM |
| `backend/app/api/chats.py` | REST API эндпоинты |
| `frontend/src/components/ChatWindow.tsx` | Отображение сообщений чата |
| `frontend/src/App.tsx` | Главное приложение с панелью контекста |

### API-эндпоинты

| Эндпоинт | Метод | Назначение |
|----------|-------|------------|
| `/api/chats` | GET | Список чатов с фильтрами |
| `/api/chats/{id}` | GET | Получить один чат |
| `/api/chats/{id}/analyze` | POST | Запустить AI-анализ |
| `/api/chats/{id}/messages` | GET | Получить сообщения чата |
| `/api/messages` | POST | Отправить сообщение |


