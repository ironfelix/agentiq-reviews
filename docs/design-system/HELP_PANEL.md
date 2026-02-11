# Help Panel Component

## Purpose
`Help Panel` — это выезжающая контекстная панель для объяснения логики блока без ухода со страницы.

## Base Variant (Right)
Используется в `Промокоды`.

### Classes
- Контейнер: `promo-help-panel`
- Кнопка закрытия: `promo-help-close`
- Заголовок: `promo-help-title`
- Секция: `promo-help-section`
- Лейбл секции: `promo-help-label`
- Текст: `promo-help-text`
- Таблица параметров: `promo-help-table`
- Alert: `promo-help-warning`
- Внешняя ссылка: `promo-help-link-ext`

## Left Variant (Dashboard/Analytics)
Используется для KPI-контекста и операционных подсказок.

### Classes
- Контейнер: `promo-help-panel left`
- Внутренние элементы: те же, что у base variant

## Trigger Placement (Required)
Триггер открытия панели ставим в верхнюю строку блока, а не под карточками.

### Recommended layout
- Слева: заголовок/label блока (например, `Контекст KPI`)
- Справа: `?` tooltip + ссылка/кнопка `Как это работает?` или `Открыть контекст`

## Content Rules
- Писать человеческим языком, короткими абзацами.
- Начинать с `Что делать` и `Что меняется`.
- Для бизнес-блоков: объяснять связь действий и эффекта (`действие команды` -> `ожидаемое изменение`).
- Формулы и методологию держать в отдельном разделе аналитики, не в help panel.

## Usage Examples

### Promo (right)
```html
<button class="promo-help-link" onclick="document.getElementById('promoHelpPanel').classList.add('open')">Как это работает?</button>
<div class="promo-help-panel" id="promoHelpPanel">...</div>
```

### Dashboard KPI (left)
```html
<button class="promo-help-link" onclick="document.getElementById('dashboardContextPanel').classList.add('open')">Что влияет на выручку?</button>
<div class="promo-help-panel left" id="dashboardContextPanel">...</div>
```

## Integration Checklist
1. Добавить trigger в header-строку целевого блока.
2. Подключить panel с id и кнопкой закрытия.
3. Закрывать panel при смене экрана (`showScreen`) и смене таба (`showSettingsTab`).
4. Проверить mobile: `promo-help-panel.left` занимает ширину экрана.
5. Проверить z-index, чтобы панель была выше app shell.
