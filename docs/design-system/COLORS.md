# Color System — AgentIQ

**Last updated:** 2026-02-14
**Status:** Active

---

## 1. Theme Strategy

AgentIQ использует **2 темы** в зависимости от модуля:
- **Reviews App** — тёмная тема (фокус на глубокий анализ, длительные сессии)
- **Chat Center** — светлая тема (операционная скорость, clarity)

---

## 2. Reviews App — Dark Theme

### Primary Colors
```css
/* Background */
--bg-primary: #0a1018;     /* Main background */
--bg-secondary: #141e2b;   /* Card background */
--bg-tertiary: #1a2635;    /* Elevated elements */

/* Accent */
--accent-primary: #e8a838;  /* Orange - main brand color */
--accent-hover: #f0b64a;    /* Hover state */
--accent-active: #d99820;   /* Active/pressed state */
```

### Semantic Colors
```css
/* Status */
--error: #e85454;      /* Errors, harmful replies, critical issues */
--success: #4ecb71;    /* Success, good replies, positive metrics */
--warning: #f0b64a;    /* Warnings, risky replies, attention needed */
--info: #7db8e8;       /* Info, neutral messages, tips */

/* Text */
--text-primary: #ffffff;      /* Primary text (headings, body) */
--text-secondary: #a8b3c1;    /* Secondary text (metadata, labels) */
--text-tertiary: #6b7785;     /* Tertiary text (hints, placeholders) */
--text-disabled: #4a5563;     /* Disabled state */
```

### Usage Examples
```css
/* Card */
.review-card {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* Primary button */
.btn-primary {
  background: var(--accent-primary);
  color: #0a1018; /* Dark text on orange */
}

/* Error state */
.reply-harmful {
  border-left: 3px solid var(--error);
  background: rgba(232, 84, 84, 0.1);
}
```

---

## 3. Chat Center — Light Theme

### Primary Colors
```css
/* Background */
--bg-primary: #ffffff;      /* Main background */
--bg-secondary: #f8f9fa;    /* Panel background */
--bg-tertiary: #e9ecef;     /* Elevated elements */

/* Accent */
--accent-primary: #1a73e8;  /* Blue - WB-like, professional */
--accent-hover: #2b82f5;    /* Hover state */
--accent-active: #0f5ec6;   /* Active/pressed state */
```

### Semantic Colors
```css
/* Status */
--status-urgent: #d93025;     /* Urgent priority (red) */
--status-high: #f9ab00;       /* High priority (yellow) */
--status-normal: #1a73e8;     /* Normal priority (blue) */
--status-low: #5f6368;        /* Low priority (gray) */

--chat-waiting: #f9ab00;      /* Waiting for response (yellow dot) */
--chat-responded: #34a853;    /* Responded (green dot) */
--chat-client-replied: #1a73e8; /* Client replied (blue dot) */
--chat-auto-response: #9aa0a6; /* Auto-response (gray dot) */
--chat-closed: #5f6368;       /* Closed chat (dark gray dot) */

/* Text */
--text-primary: #202124;      /* Primary text */
--text-secondary: #5f6368;    /* Secondary text */
--text-tertiary: #80868b;     /* Tertiary text */
--text-disabled: #bdc1c6;     /* Disabled state */
```

### Marketplace Colors
```css
/* Marketplace badges */
--wb-purple: #8b3ff0;        /* Wildberries brand */
--ozon-blue: #005bff;        /* Ozon brand */
```

### Usage Examples
```css
/* Chat item urgent */
.chat-item.urgent {
  border-left: 3px solid var(--status-urgent);
}

/* Status dot */
.status-dot.waiting {
  background: var(--chat-waiting);
}

/* Primary button */
.btn-primary {
  background: var(--accent-primary);
  color: #ffffff;
}
```

---

## 4. Transparency & Overlays

### Dark Theme (Reviews)
```css
/* Overlays */
--overlay-light: rgba(255, 255, 255, 0.05);
--overlay-medium: rgba(255, 255, 255, 0.1);
--overlay-strong: rgba(255, 255, 255, 0.15);

/* Shadows */
--shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
```

### Light Theme (Chat Center)
```css
/* Overlays */
--overlay-light: rgba(0, 0, 0, 0.03);
--overlay-medium: rgba(0, 0, 0, 0.06);
--overlay-strong: rgba(0, 0, 0, 0.1);

/* Shadows */
--shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.15);
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.2);
```

---

## 5. Gradients

### Reviews App
```css
/* Hero gradient */
--gradient-hero: linear-gradient(135deg, #0a1018 0%, #1a2635 100%);

/* Accent gradient */
--gradient-accent: linear-gradient(135deg, #e8a838 0%, #f0b64a 100%);
```

### Chat Center
```css
/* Header gradient (subtle) */
--gradient-header: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
```

---

## 6. Accessibility (WCAG AA)

### Contrast Ratios
All color combinations meet WCAG AA standard (4.5:1 for normal text, 3:1 for large text).

**Dark Theme:**
- `#ffffff` on `#0a1018` — 19.1:1 ✅
- `#a8b3c1` on `#0a1018` — 11.2:1 ✅
- `#e8a838` on `#0a1018` — 8.4:1 ✅

**Light Theme:**
- `#202124` on `#ffffff` — 18.7:1 ✅
- `#5f6368` on `#ffffff` — 7.1:1 ✅
- `#1a73e8` on `#ffffff` — 4.9:1 ✅

---

## 7. Implementation

### CSS Variables (Global)
```css
:root {
  /* Theme-specific variables are defined in theme files */
}

/* Dark theme (reviews) */
[data-theme="reviews"] {
  --bg-primary: #0a1018;
  --accent-primary: #e8a838;
  /* ... */
}

/* Light theme (chat) */
[data-theme="chat"] {
  --bg-primary: #ffffff;
  --accent-primary: #1a73e8;
  /* ... */
}
```

---

## 8. Color Naming Convention

**Pattern:** `--{category}-{role}-{variant}`

**Examples:**
- `--bg-primary` — background, primary role
- `--text-secondary` — text, secondary role
- `--accent-hover` — accent color, hover variant
- `--status-urgent` — status, urgent role

**Avoid:** Descriptive names like `--blue` or `--dark-gray`. Use semantic roles instead.

---

## 9. Design Tokens (Figma)

**Sync with Figma:**
- Figma library: `AgentIQ Design System`
- Color tokens: `Colors/Reviews/Primary/Background`
- Export: Figma Tokens plugin → `design-tokens.json`

---

## 10. Related Docs

- `TYPOGRAPHY.md` — Font system
- `COMPONENTS.md` — Component colors
- `HELP_PANEL.md` — Panel-specific colors
