# Components — AgentIQ

**Last updated:** 2026-02-14
**Status:** Active

---

## 1. Buttons

### Primary Button
```css
.btn-primary {
  padding: 12px 24px;
  background: var(--accent-primary);
  color: #ffffff; /* Light theme */
  color: #0a1018; /* Dark theme (Reviews) */
  border-radius: 8px;
  font-size: var(--text-body);
  font-weight: var(--font-weight-semibold);
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn-primary:active {
  background: var(--accent-active);
  transform: translateY(0);
}
```

### Secondary Button
```css
.btn-secondary {
  padding: 12px 24px;
  background: transparent;
  color: var(--accent-primary);
  border: 1px solid var(--accent-primary);
  border-radius: 8px;
  font-size: var(--text-body);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: var(--overlay-light);
}
```

### Ghost Button (icon-only)
```css
.btn-ghost {
  padding: 8px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-ghost:hover {
  background: var(--overlay-medium);
}
```

### Button Sizes
```css
.btn-sm { padding: 8px 16px; font-size: 13px; }
.btn-md { padding: 12px 24px; font-size: 14px; } /* Default */
.btn-lg { padding: 16px 32px; font-size: 16px; }
```

---

## 2. Input Fields

### Text Input
```css
.input {
  padding: 12px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--overlay-medium);
  border-radius: 8px;
  font-size: 16px; /* >=16px на mobile для избежания iOS zoom */
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.1);
}

.input::placeholder {
  color: var(--text-tertiary);
}
```

### Textarea
```css
.textarea {
  padding: 12px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--overlay-medium);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-primary);
  resize: vertical;
  min-height: 120px;
  font-family: var(--font-primary);
}
```

### Error State
```css
.input.error {
  border-color: var(--error);
}

.input-error-msg {
  color: var(--error);
  font-size: var(--text-body-sm);
  margin-top: 4px;
}
```

---

## 3. Badges

### Status Badge
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: var(--text-caption);
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
}

/* Variants */
.badge.urgent {
  background: rgba(217, 48, 37, 0.1);
  color: var(--status-urgent);
}

.badge.high {
  background: rgba(249, 171, 0, 0.1);
  color: var(--status-high);
}

.badge.normal {
  background: rgba(26, 115, 232, 0.1);
  color: var(--status-normal);
}

.badge.low {
  background: rgba(95, 99, 104, 0.1);
  color: var(--status-low);
}
```

### Source Badge (WB API vs Fallback)
```css
.badge.wb-api {
  background: rgba(52, 168, 83, 0.1);
  color: var(--success);
}

.badge.wbcon-fallback {
  background: rgba(240, 182, 74, 0.1);
  color: var(--warning);
}
```

### Marketplace Badge
```css
.badge.marketplace {
  background: var(--wb-purple);
  color: #ffffff;
  padding: 6px 12px;
  border-radius: 6px;
}
```

---

## 4. Cards

### Base Card (Reviews App)
```css
.card {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

### Chat Item Card (Chat Center)
```css
.chat-item {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--bg-primary);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 0.2s ease;
}

.chat-item:hover {
  background: var(--bg-secondary);
}

.chat-item.active {
  background: var(--overlay-light);
  border-left-color: var(--accent-primary);
}

.chat-item.urgent {
  border-left-color: var(--status-urgent);
}
```

### Interaction Card (Unified)
```css
.interaction-card {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.interaction-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.interaction-card-subject {
  font-size: var(--text-body-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.interaction-card-meta {
  display: flex;
  gap: 8px;
  font-size: var(--text-body-sm);
  color: var(--text-tertiary);
}
```

---

## 5. Status Dots

```css
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

/* Chat statuses */
.status-dot.waiting {
  background: var(--chat-waiting);
}

.status-dot.responded {
  background: var(--chat-responded);
}

.status-dot.client-replied {
  background: var(--chat-client-replied);
}

.status-dot.auto-response {
  background: var(--chat-auto-response);
}

.status-dot.closed {
  background: var(--chat-closed);
}

/* With animation (urgent) */
.status-dot.waiting.risk {
  background: var(--status-urgent);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

---

## 6. Filter Pills

```css
.filters {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
}

.filters::-webkit-scrollbar {
  display: none; /* Chrome/Safari */
}

.filter-pill {
  padding: 8px 16px;
  background: var(--bg-secondary);
  border-radius: 20px;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.filter-pill:hover {
  background: var(--overlay-medium);
}

.filter-pill.active {
  background: var(--accent-primary);
  color: #ffffff;
}
```

---

## 7. Dropdown

```css
.dropdown {
  position: relative;
  display: inline-block;
}

.dropdown-trigger {
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--bg-secondary);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  min-width: 200px;
  padding: 8px 0;
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.dropdown.open .dropdown-menu {
  opacity: 1;
  pointer-events: auto;
}

.dropdown-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.dropdown-item:hover {
  background: var(--overlay-light);
}
```

---

## 8. Tooltip

```css
.tooltip {
  position: relative;
  display: inline-block;
}

.tooltip-text {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: var(--text-body-sm);
  white-space: nowrap;
  box-shadow: var(--shadow-md);
  transition: opacity 0.2s ease;
  z-index: 1000;
}

.tooltip:hover .tooltip-text {
  visibility: visible;
  opacity: 1;
}

/* Arrow */
.tooltip-text::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--bg-tertiary);
}
```

---

## 9. Loading States

### Spinner
```css
.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--overlay-light);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### Skeleton (placeholder loading)
```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--overlay-light) 0%,
    var(--overlay-medium) 50%,
    var(--overlay-light) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  to { background-position: -200% 0; }
}

.skeleton-text {
  height: 16px;
  margin: 8px 0;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}
```

---

## 10. Empty States

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  text-align: center;
}

.empty-state-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state-title {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-state-description {
  font-size: var(--text-body);
  color: var(--text-secondary);
  max-width: 400px;
}

.empty-state-cta {
  margin-top: 24px;
}
```

---

## 11. Toast Notifications

```css
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  padding: 16px 20px;
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 300px;
  max-width: 400px;
  z-index: 1000;
  animation: slideInUp 0.3s ease;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Variants */
.toast.success { border-left: 4px solid var(--success); }
.toast.error { border-left: 4px solid var(--error); }
.toast.warning { border-left: 4px solid var(--warning); }
.toast.info { border-left: 4px solid var(--info); }
```

---

## 12. Progress Bar

```css
.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--overlay-light);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent-primary);
  transition: width 0.3s ease;
}

/* Indeterminate (loading) */
.progress-bar-fill.indeterminate {
  width: 30%;
  animation: indeterminate 1.5s infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
```

---

## 13. Divider

```css
.divider {
  height: 1px;
  background: var(--overlay-light);
  margin: 16px 0;
}

.divider-text {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 16px 0;
}

.divider-text::before,
.divider-text::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid var(--overlay-light);
}

.divider-text span {
  padding: 0 12px;
  font-size: var(--text-body-sm);
  color: var(--text-tertiary);
}
```

---

## 14. Modals

```css
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.modal-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.modal {
  background: var(--bg-primary);
  border-radius: 12px;
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  transform: scale(0.95);
  transition: transform 0.3s ease;
}

.modal-overlay.open .modal {
  transform: scale(1);
}

.modal-header {
  padding: 24px;
  border-bottom: 1px solid var(--overlay-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-body {
  padding: 24px;
}

.modal-footer {
  padding: 24px;
  border-top: 1px solid var(--overlay-light);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
```

---

## 15. Related Docs

- `COLORS.md` — Component colors
- `TYPOGRAPHY.md` — Text styles
- `PANELS.md` — Panel components (Help, Context, etc.)
- `LAYOUTS.md` — Layout constraints
