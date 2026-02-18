import { useState, useEffect, useCallback } from 'react';

const DISMISS_KEY = 'agentiq_ar_topbar_dismissed';
const DISMISS_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

function isDismissed(): boolean {
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const dismissedAt = Number(raw);
    if (Number.isNaN(dismissedAt)) return false;
    return Date.now() - dismissedAt < DISMISS_DURATION_MS;
  } catch {
    return false;
  }
}

function persistDismiss(): void {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch { /* ignore quota errors */ }
}

interface AutoResponseTopBarProps {
  autoResponseEnabled: boolean;
  onNavigateToSettings: () => void;
}

export function AutoResponseTopBar({ autoResponseEnabled, onNavigateToSettings }: AutoResponseTopBarProps) {
  const [dismissed, setDismissed] = useState(() => isDismissed());

  // Re-check dismissal on mount (in case 7 days passed)
  useEffect(() => {
    setDismissed(isDismissed());
  }, []);

  const handleDismiss = useCallback(() => {
    persistDismiss();
    setDismissed(true);
  }, []);

  // Don't show if auto-responses are already enabled or user dismissed
  if (autoResponseEnabled || dismissed) {
    return null;
  }

  return (
    <div className="ar-topbar">
      <div className="ar-topbar-content">
        <div className="ar-topbar-icon">{'\u26A1'}</div>
        <div className="ar-topbar-text">
          <strong>Экономьте до 3 часов в день</strong> — включите авто-ответы на частые обращения
        </div>
      </div>
      <div className="ar-topbar-actions">
        <button className="ar-topbar-btn primary" type="button" onClick={onNavigateToSettings}>
          Настроить
        </button>
        <button className="ar-topbar-dismiss" type="button" title="Скрыть" onClick={handleDismiss}>
          {'\u00D7'}
        </button>
      </div>
    </div>
  );
}
