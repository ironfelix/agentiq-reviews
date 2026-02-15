# AgentIQ Design System

**Last updated:** 2026-02-14
**Status:** Active — Complete design system documentation

---

## 📋 Table of Contents

1. [Colors](#colors) — `COLORS.md`
2. [Typography](#typography) — `TYPOGRAPHY.md`
3. [Components](#components) — `COMPONENTS.md`
4. [Panels](#panels) — `PANELS.md`
5. [Principles](#principles)

---

## 🎨 Colors

**File:** `COLORS.md`

Comprehensive color system for both themes:
- **Reviews App** — Dark theme (`#0a1018` background, `#e8a838` accent)
- **Chat Center** — Light theme (`#ffffff` background, `#1a73e8` accent)

**Includes:**
- Primary colors (background, accent)
- Semantic colors (success, error, warning, info)
- Status colors (urgent, high, normal, low)
- Chat status colors (waiting, responded, client-replied)
- Transparency & overlays
- Gradients
- Accessibility (WCAG AA compliance)

[→ Read COLORS.md](./COLORS.md)

---

## ✍️ Typography

**File:** `TYPOGRAPHY.md`

Font system and type scale:
- **Reviews App** — Montserrat (modern geometric sans-serif)
- **Chat Center** — Inter (designed for UI)

**Includes:**
- Font families & weights
- Type scale (h1-h4, body, caption)
- Line heights & letter spacing
- Text truncation patterns
- Responsive typography
- Accessibility (minimum sizes, font smoothing)

[→ Read TYPOGRAPHY.md](./TYPOGRAPHY.md)

---

## 🧩 Components

**File:** `COMPONENTS.md`

Complete UI component library:
- **Buttons** — Primary, secondary, ghost (icon-only)
- **Input fields** — Text input, textarea, error states
- **Badges** — Status, source (WB API vs fallback), marketplace
- **Cards** — Base card, chat item, interaction card
- **Status dots** — Chat statuses with animations
- **Filter pills** — Horizontal scrollable filters
- **Dropdown** — Menu component
- **Tooltip** — Hover tooltips
- **Loading states** — Spinner, skeleton placeholders
- **Empty states** — No data screens
- **Toast notifications** — Success, error, warning, info
- **Progress bar** — Determinate & indeterminate
- **Divider** — Horizontal rule with optional text
- **Modals** — Overlay dialogs

[→ Read COMPONENTS.md](./COMPONENTS.md)

---

## 📱 Panels

**File:** `PANELS.md`

Panel components and patterns:
1. **Help Panel** — Contextual help (slide-out right)
2. **Context Panel** — Product/customer context (Chat Center)
3. **Advanced Filters** — Extended filters (slide-out on desktop, bottom sheet on mobile)

**Includes:**
- HTML structure & CSS
- Mobile behavior (responsive, touch-friendly)
- State management (JavaScript, React)
- Accessibility (keyboard navigation, focus trap)
- Panel overlay

[→ Read PANELS.md](./PANELS.md)

---

## 📐 Principles

### 1. Consistency
Один визуальный язык компонентов для всех разделов:
- `Главная` (Dashboard)
- `Аналитика` (Analytics)
- `Промокоды` (Promo Codes)
- `Настройки` (Settings)
- `Чаты` (Chat Center)

### 2. Context Near Action
Триггер открытия панели (Help, Context, Filters) всегда ставится в верхнюю строку соответствующего блока.

**Example:**
```html
<div class="section-header">
  <h2>Качество ответов</h2>
  <button onclick="openHelpPanel()">Как это работает?</button>
</div>
```

### 3. Clarity Over Complexity
- Писать простым языком (без длинных формул в UI)
- Использовать semantic naming (`.btn-primary`, не `.blue-button`)
- Минимум вложенности (max 3 уровня)

### 4. Mobile-First
- Responsive breakpoints: 400px, 640px, 768px, 1024px
- Touch targets: минимум 44x44px
- Input font-size: >=16px (avoid iOS zoom)
- Panels: slide-out → bottom sheet на mobile

### 5. Accessibility
- WCAG AA compliance (4.5:1 contrast ratio)
- Keyboard navigation (Tab, Escape)
- ARIA labels для screen readers
- Focus trap в модалах и панелях

### 6. Performance
- Font loading: `font-display: swap`
- Preload critical fonts
- CSS animations: use `transform` and `opacity` (GPU accelerated)
- Lazy load images

---

## 🛠 Implementation

### CSS Variables (Global)
All design tokens are defined as CSS custom properties:

```css
:root {
  /* Colors */
  --bg-primary: #ffffff;
  --accent-primary: #1a73e8;
  --text-primary: #202124;

  /* Typography */
  --font-primary: 'Inter', sans-serif;
  --text-body: 14px;
  --lh-normal: 1.5;

  /* Spacing */
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

### Theme Switching
```html
<body data-theme="chat"> <!-- or "reviews" -->
```

```css
[data-theme="chat"] {
  --bg-primary: #ffffff;
  --accent-primary: #1a73e8;
}

[data-theme="reviews"] {
  --bg-primary: #0a1018;
  --accent-primary: #e8a838;
}
```

---

## 📦 Design Tokens (Figma)

**Figma Library:** `AgentIQ Design System`

**Export:**
- Colors → `design-tokens/colors.json`
- Typography → `design-tokens/typography.json`
- Spacing → `design-tokens/spacing.json`

**Tool:** Figma Tokens plugin

---

## 📚 Related Documentation

### Prototypes
- `docs/prototypes/app-screens-v3-ru.html` — Full app flow (source of truth)
- `docs/prototypes/landing.html` — Landing page design
- `docs/chat-center/chat-center-real-data.html` — Chat Center live example

### Architecture
- `docs/architecture/architecture.md` — System architecture
- `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` — Unified communications plan

### Development
- `CLAUDE.md` — Developer instructions (Claude Code)
- `CODEX.md` — Developer instructions (GitHub Copilot)

---

## 🚀 Quick Start

1. **Read the core docs:**
   - `COLORS.md` — Color system
   - `TYPOGRAPHY.md` — Font system
   - `COMPONENTS.md` — UI components

2. **Copy CSS variables to your project:**
   ```html
   <link rel="stylesheet" href="/design-system/tokens.css">
   ```

3. **Use components:**
   ```html
   <button class="btn-primary">Primary Button</button>
   <div class="badge urgent">Срочно</div>
   ```

4. **Follow principles:**
   - Consistency
   - Context near action
   - Clarity over complexity
   - Mobile-first
   - Accessibility

---

## 📝 Contribution Guidelines

When adding new components:
1. Document HTML structure
2. Provide CSS implementation
3. Include mobile behavior
4. Add accessibility notes
5. Link to related docs
6. Update this README

---

## ✅ Checklist for New Components

- [ ] HTML structure documented
- [ ] CSS implementation provided
- [ ] Desktop styles defined
- [ ] Mobile responsive (<=768px)
- [ ] Tablet responsive (769-1024px)
- [ ] Accessibility (ARIA, keyboard nav)
- [ ] Touch targets (>=44x44px)
- [ ] Dark theme variant (if applicable)
- [ ] Light theme variant (if applicable)
- [ ] Usage examples
- [ ] Related docs linked
