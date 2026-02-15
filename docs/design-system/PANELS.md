# Panels — AgentIQ

**Last updated:** 2026-02-14
**Status:** Active

---

## 1. Panel Types

AgentIQ использует **3 типа панелей**:
1. **Help Panel** — контекстная справка (slide-out справа)
2. **Context Panel** — product/customer context (Chat Center, правая колонка)
3. **Advanced Filters** — расширенные фильтры (bottom sheet на mobile, slide-out на desktop)

---

## 2. Help Panel

### Purpose
Выезжающая контекстная панель для объяснения логики блока без ухода со страницы.

### Placement & Direction
**Единый стандарт:** панель всегда открывается **справа**.

### HTML Structure
```html
<div class="promo-help-panel" id="helpPanel">
  <button class="promo-help-close" onclick="closeHelpPanel()">×</button>

  <h2 class="promo-help-title">Как это работает?</h2>

  <div class="promo-help-section">
    <div class="promo-help-label">Что делать</div>
    <p class="promo-help-text">
      Объяснение действий, которые нужно совершить.
    </p>
  </div>

  <div class="promo-help-section">
    <div class="promo-help-label">Что меняется</div>
    <p class="promo-help-text">
      Объяснение ожидаемого эффекта.
    </p>
  </div>

  <div class="promo-help-warning">
    ⚠️ Важно: критичная информация для пользователя.
  </div>

  <a href="#" class="promo-help-link-ext" target="_blank">
    Подробнее в документации →
  </a>
</div>
```

### CSS
```css
.promo-help-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 400px;
  max-width: 90vw;
  height: 100vh;
  background: var(--bg-secondary);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.3);
  padding: 32px;
  overflow-y: auto;
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.3s ease;
}

.promo-help-panel.open {
  transform: translateX(0);
}

.promo-help-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: transparent;
  border: none;
  font-size: 32px;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color 0.2s ease;
}

.promo-help-close:hover {
  color: var(--text-primary);
}

.promo-help-title {
  font-size: var(--text-h2);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 24px;
}

.promo-help-section {
  margin-bottom: 24px;
}

.promo-help-label {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--accent-primary);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin-bottom: 8px;
}

.promo-help-text {
  font-size: var(--text-body);
  color: var(--text-secondary);
  line-height: var(--lh-normal);
}

.promo-help-warning {
  background: rgba(240, 182, 74, 0.1);
  border-left: 3px solid var(--warning);
  padding: 12px 16px;
  border-radius: 6px;
  font-size: var(--text-body-sm);
  color: var(--text-secondary);
  margin: 24px 0;
}

.promo-help-link-ext {
  display: inline-block;
  color: var(--accent-primary);
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  margin-top: 16px;
}

.promo-help-link-ext:hover {
  text-decoration: underline;
}
```

### Trigger Placement (Required)
Триггер открытия панели ставится в верхнюю строку блока:

```html
<div class="section-header">
  <h2>Контекст KPI</h2>
  <button class="btn-ghost" onclick="openHelpPanel('dashboardHelp')">
    <span class="tooltip">?
      <span class="tooltip-text">Как рассчитываются метрики?</span>
    </span>
  </button>
</div>
```

### Content Rules
- Писать человеческим языком, короткими абзацами
- Начинать с «Что делать» и «Что меняется»
- Для бизнес-блоков: объяснять связь действий и эффекта
- Формулы и методологию держать в отдельном разделе аналитики

### Mobile Behavior
```css
@media (max-width: 768px) {
  .promo-help-panel {
    width: 100%;
    max-width: 100vw;
  }
}
```

---

## 3. Context Panel (Chat Center)

### Purpose
Правая колонка в Chat Center для отображения product/customer context.

### HTML Structure
```html
<aside class="context-panel">
  <div class="context-panel-header">
    <h3>Контекст товара</h3>
    <button class="btn-ghost context-panel-close">×</button>
  </div>

  <div class="context-panel-body">
    <!-- Product card -->
    <div class="product-card">
      <img src="..." alt="Product" class="product-image">
      <h4 class="product-name">Название товара</h4>
      <div class="product-meta">
        <span class="badge">WB</span>
        <span class="product-nm">123456789</span>
      </div>
    </div>

    <!-- Recent interactions -->
    <div class="context-section">
      <h5 class="context-section-title">Последние обращения</h5>
      <div class="timeline">
        <!-- Timeline items -->
      </div>
    </div>

    <!-- Top complaints -->
    <div class="context-section">
      <h5 class="context-section-title">Частые жалобы</h5>
      <ul class="complaint-list">
        <li>Размер не соответствует</li>
        <li>Цвет темнее чем на фото</li>
      </ul>
    </div>
  </div>
</aside>
```

### CSS
```css
.context-panel {
  width: 320px;
  min-width: 320px;
  background: var(--bg-secondary);
  border-left: 1px solid var(--overlay-light);
  height: 100vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.context-panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--overlay-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.context-panel-header h3 {
  font-size: var(--text-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.context-panel-body {
  padding: 16px;
  flex: 1;
  overflow-y: auto;
}

.context-section {
  margin-bottom: 24px;
}

.context-section-title {
  font-size: var(--text-body);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 12px;
}

/* Product card */
.product-card {
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
}

.product-image {
  width: 100%;
  height: 200px;
  object-fit: cover;
  border-radius: 6px;
  margin-bottom: 12px;
}

.product-name {
  font-size: var(--text-body);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin-bottom: 8px;
}

.product-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: var(--text-caption);
  color: var(--text-tertiary);
}
```

### Mobile Behavior (Tablet)
На tablet (769-1024px) context panel скрыт по умолчанию, показывается по кнопке:

```css
@media (max-width: 1024px) {
  .context-panel {
    position: fixed;
    right: -320px;
    top: 0;
    z-index: 100;
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.3);
    transition: right 0.3s ease;
  }

  .context-panel.open {
    right: 0;
  }
}
```

### Mobile Behavior (Phone)
На mobile (<=768px) context panel открывается как full-screen overlay:

```css
@media (max-width: 768px) {
  .context-panel {
    width: 100%;
    min-width: 100%;
    right: -100%;
  }

  .context-panel.open {
    right: 0;
  }
}
```

---

## 4. Advanced Filters Panel

### Purpose
Расширенные фильтры для списка interactions (priority, source, channel, date range).

### Placement
- **Desktop:** Slide-out справа (похож на Help Panel)
- **Mobile:** Bottom sheet

### HTML Structure
```html
<div class="advanced-filters-panel" id="advancedFilters">
  <div class="filters-panel-header">
    <h3>Фильтры</h3>
    <button class="btn-ghost" onclick="closeAdvancedFilters()">×</button>
  </div>

  <div class="filters-panel-body">
    <!-- Filter groups -->
    <div class="filter-group">
      <label class="filter-label">Приоритет</label>
      <div class="filter-options">
        <label class="checkbox">
          <input type="checkbox" value="urgent">
          <span>Срочно</span>
        </label>
        <label class="checkbox">
          <input type="checkbox" value="high">
          <span>Высокий</span>
        </label>
        <label class="checkbox">
          <input type="checkbox" value="normal" checked>
          <span>Обычный</span>
        </label>
        <label class="checkbox">
          <input type="checkbox" value="low">
          <span>Низкий</span>
        </label>
      </div>
    </div>

    <div class="filter-group">
      <label class="filter-label">Источник данных</label>
      <div class="filter-options">
        <label class="checkbox">
          <input type="checkbox" value="wb_api" checked>
          <span>WB API</span>
        </label>
        <label class="checkbox">
          <input type="checkbox" value="wbcon_fallback">
          <span>Fallback</span>
        </label>
      </div>
    </div>

    <div class="filter-group">
      <label class="filter-label">Период</label>
      <input type="date" class="input" placeholder="От">
      <input type="date" class="input" placeholder="До">
    </div>
  </div>

  <div class="filters-panel-footer">
    <button class="btn-secondary" onclick="resetFilters()">Сбросить</button>
    <button class="btn-primary" onclick="applyFilters()">Применить</button>
  </div>
</div>
```

### CSS (Desktop)
```css
.advanced-filters-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 400px;
  height: 100vh;
  background: var(--bg-primary);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.3s ease;
  display: flex;
  flex-direction: column;
}

.advanced-filters-panel.open {
  transform: translateX(0);
}

.filters-panel-header {
  padding: 20px;
  border-bottom: 1px solid var(--overlay-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.filter-group {
  margin-bottom: 24px;
}

.filter-label {
  display: block;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 12px;
}

.filter-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.filters-panel-footer {
  padding: 20px;
  border-top: 1px solid var(--overlay-light);
  display: flex;
  gap: 12px;
}
```

### CSS (Mobile — Bottom Sheet)
```css
@media (max-width: 768px) {
  .advanced-filters-panel {
    top: auto;
    bottom: 0;
    width: 100%;
    height: auto;
    max-height: 80vh;
    border-radius: 16px 16px 0 0;
    transform: translateY(100%);
  }

  .advanced-filters-panel.open {
    transform: translateY(0);
  }

  /* Handle для свайпа */
  .filters-panel-header::before {
    content: '';
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    width: 40px;
    height: 4px;
    background: var(--overlay-medium);
    border-radius: 2px;
  }
}
```

---

## 5. Panel Overlay

Для всех панелей используется единый overlay:

```html
<div class="panel-overlay" id="panelOverlay" onclick="closePanels()"></div>
```

```css
.panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.panel-overlay.open {
  opacity: 1;
  pointer-events: auto;
}
```

---

## 6. Panel State Management

### JavaScript (Vanilla)
```javascript
// Open panel
function openPanel(panelId) {
  const panel = document.getElementById(panelId);
  const overlay = document.getElementById('panelOverlay');

  panel.classList.add('open');
  overlay.classList.add('open');

  // Prevent body scroll on mobile
  document.body.style.overflow = 'hidden';
}

// Close panel
function closePanel(panelId) {
  const panel = document.getElementById(panelId);
  const overlay = document.getElementById('panelOverlay');

  panel.classList.remove('open');
  overlay.classList.remove('open');

  // Restore body scroll
  document.body.style.overflow = '';
}

// Close all panels
function closePanels() {
  document.querySelectorAll('.promo-help-panel, .advanced-filters-panel').forEach(panel => {
    panel.classList.remove('open');
  });
  document.getElementById('panelOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closePanels();
});
```

### React (Chat Center)
```tsx
const [isPanelOpen, setIsPanelOpen] = useState(false);

const openPanel = () => {
  setIsPanelOpen(true);
  document.body.style.overflow = 'hidden';
};

const closePanel = () => {
  setIsPanelOpen(false);
  document.body.style.overflow = '';
};

useEffect(() => {
  const handleEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape') closePanel();
  };
  document.addEventListener('keydown', handleEscape);
  return () => document.removeEventListener('keydown', handleEscape);
}, []);
```

---

## 7. Accessibility

### Keyboard Navigation
```html
<div
  class="promo-help-panel"
  id="helpPanel"
  role="dialog"
  aria-labelledby="helpPanelTitle"
  aria-modal="true"
>
  <h2 id="helpPanelTitle" class="promo-help-title">Как это работает?</h2>
  <!-- Content -->
</div>
```

### Focus Trap
При открытии панели фокус должен перемещаться внутрь панели и оставаться там до закрытия.

```javascript
function trapFocus(element) {
  const focusableElements = element.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  element.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  });

  firstElement.focus();
}
```

---

## 8. Related Docs

- `COMPONENTS.md` — Base components
- `LAYOUTS.md` — Panel placement in layouts
- `../chat-center/chat-center-real-data.html` — Live example (Chat Center)
- `../prototypes/app-screens-v3-ru.html` — Full app flow
