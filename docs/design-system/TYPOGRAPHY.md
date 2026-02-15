# Typography — AgentIQ

**Last updated:** 2026-02-14
**Status:** Active

---

## 1. Font Families

### Reviews App — Montserrat
```css
--font-primary: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

**Why Montserrat:**
- Modern geometric sans-serif
- Excellent readability для long-form content (analysis reports)
- Strong personality для brand identity

**Weights used:**
- 400 (Regular) — body text
- 500 (Medium) — labels, metadata
- 600 (Semibold) — headings, CTAs
- 700 (Bold) — hero headings, emphasis

**Loading:**
```html
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
```

---

### Chat Center — Inter
```css
--font-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

**Why Inter:**
- Designed for UI (optimal at small sizes)
- Superior legibility для operational interfaces
- Neutral, professional tone

**Weights used:**
- 400 (Regular) — body text
- 500 (Medium) — labels, buttons
- 600 (Semibold) — headings
- 700 (Bold) — emphasis (rarely used)

**Loading:**
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

---

## 2. Type Scale

### Desktop (>=769px)

```css
/* Headings */
--text-h1: 32px;    /* Hero headings */
--text-h2: 24px;    /* Section headings */
--text-h3: 20px;    /* Subsection headings */
--text-h4: 18px;    /* Card headings */

/* Body */
--text-body-lg: 16px;   /* Large body (primary content) */
--text-body: 14px;      /* Default body text */
--text-body-sm: 13px;   /* Small body (metadata, labels) */
--text-caption: 12px;   /* Captions, hints */

/* Line Heights */
--lh-tight: 1.25;   /* Headings */
--lh-normal: 1.5;   /* Body text */
--lh-relaxed: 1.75; /* Long-form content */
```

### Mobile (<=768px)

```css
/* Headings (scaled down) */
--text-h1: 28px;
--text-h2: 22px;
--text-h3: 18px;
--text-h4: 16px;

/* Body (same, but ensure >=16px for inputs to avoid iOS zoom) */
--text-body-lg: 16px;
--text-body: 14px;
--text-body-sm: 13px;
--text-caption: 12px;
```

---

## 3. Usage Examples

### Reviews App — Dark Theme

```css
/* Hero heading */
.hero-title {
  font-family: var(--font-primary);
  font-size: var(--text-h1);
  font-weight: 700;
  line-height: var(--lh-tight);
  color: var(--text-primary);
}

/* Section heading */
.section-heading {
  font-size: var(--text-h2);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

/* Body text */
.body-text {
  font-size: var(--text-body);
  font-weight: 400;
  line-height: var(--lh-normal);
  color: var(--text-secondary);
}

/* Metadata */
.metadata {
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--text-tertiary);
}
```

### Chat Center — Light Theme

```css
/* Chat message */
.message-content {
  font-family: var(--font-primary);
  font-size: var(--text-body);
  line-height: var(--lh-normal);
  color: var(--text-primary);
}

/* Chat item subject */
.chat-item-subject {
  font-size: var(--text-body-lg);
  font-weight: 500;
  color: var(--text-primary);
}

/* Timestamp */
.message-time {
  font-size: var(--text-caption);
  font-weight: 400;
  color: var(--text-tertiary);
}
```

---

## 4. Font Weights — Semantic Naming

```css
--font-weight-regular: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
```

**Usage rules:**
- **Regular (400):** Body text, descriptions, long-form content
- **Medium (500):** Labels, metadata, subtle emphasis
- **Semibold (600):** Headings, buttons, primary CTAs
- **Bold (700):** Hero headings, strong emphasis (use sparingly)

---

## 5. Letter Spacing

```css
/* Headings */
--ls-tight: -0.02em;  /* Large headings (h1, h2) */
--ls-normal: 0;       /* Body text, h3, h4 */

/* All caps */
--ls-wide: 0.05em;    /* Uppercase labels, badges */
```

**Example:**
```css
.badge {
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  font-size: var(--text-caption);
  font-weight: var(--font-weight-semibold);
}
```

---

## 6. Text Truncation

### Single Line
```css
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

### Multi-line (2 lines)
```css
.truncate-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

**Usage:**
- Chat preview: 2 lines max
- Product names: 1 line max
- Review text: 3-4 lines max (expandable)

---

## 7. Responsive Typography

### Mobile-First Approach
```css
/* Base (mobile) */
body {
  font-size: 14px;
}

/* Tablet (>=768px) */
@media (min-width: 768px) {
  body {
    font-size: 14px; /* Same */
  }
}

/* Desktop (>=1024px) */
@media (min-width: 1024px) {
  .hero-title {
    font-size: 36px; /* Larger on desktop */
  }
}
```

### Fluid Typography (Optional)
```css
/* Fluid scale between 320px and 1920px */
--text-h1-fluid: clamp(28px, 2vw + 24px, 36px);
```

---

## 8. Accessibility

### Minimum Sizes
- **Body text:** 14px minimum (WCAG AA)
- **Mobile inputs:** 16px minimum (avoid iOS zoom)
- **Captions:** 12px acceptable for metadata

### Contrast
- **Light theme:** Minimum 4.5:1 ratio (AA standard)
- **Dark theme:** Minimum 4.5:1 ratio

### Font Smoothing
```css
body {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

---

## 9. Code Font (Optional)

For technical displays (API keys, error codes):
```css
--font-mono: 'SF Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
```

**Usage:**
```css
.api-key {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--overlay-light);
  padding: 4px 8px;
  border-radius: 4px;
}
```

---

## 10. Performance

### Font Loading Strategy
```css
/* Preload critical fonts */
<link rel="preload" href="/fonts/Inter-Regular.woff2" as="font" type="font/woff2" crossorigin>

/* font-display: swap для избежания FOIT */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter-Regular.woff2') format('woff2');
  font-display: swap;
  font-weight: 400;
}
```

### Subsetting (Optional)
- Google Fonts автоматически subset для кириллицы:
  `?family=Inter:wght@400;500;600&subset=cyrillic`

---

## 11. Related Docs

- `COLORS.md` — Text colors
- `COMPONENTS.md` — Component typography
- `LAYOUTS.md` — Max-width constraints
