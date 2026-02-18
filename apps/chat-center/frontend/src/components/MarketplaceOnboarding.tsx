import { useState } from 'react';
import type { User } from '../types';

interface MarketplaceOnboardingProps {
  user: User;
  isConnecting?: boolean;
  isRetryingSync?: boolean;
  loadedCount?: number;
  onConnectMarketplace: (apiKey: string) => Promise<void>;
  onSkip: () => void;
  onContinue: () => void;
  onRetrySync?: () => Promise<void>;
}

export function MarketplaceOnboarding({
  user,
  isConnecting,
  isRetryingSync,
  onConnectMarketplace,
  onSkip,
  onContinue,
  onRetrySync,
  loadedCount,
}: MarketplaceOnboardingProps) {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const isSyncing = user.sync_status === 'syncing';
  const isConnected = Boolean(user.has_api_credentials) && user.sync_status !== 'error';
  const canContinue = Boolean(user.has_api_credentials) && user.sync_status !== 'syncing';
  const canConnect = !user.has_api_credentials || user.sync_status === 'error';
  const title = isConnected
    ? 'Wildberries подключен'
    : user.sync_status === 'error'
      ? 'Ошибка синхронизации Wildberries'
      : 'Подключите маркетплейс';
  const description = isConnected
    ? 'Можно перейти в сообщения и начать обработку обращений.'
    : user.sync_status === 'error'
      ? (user.sync_error || 'Проверьте API-ключ и повторите синхронизацию.')
      : 'Все сообщения покупателей в одном месте. Видно что срочно, ничего не теряется.';

  const handleConnect = async () => {
    if (!apiKey || apiKey.trim().length < 10) {
      setError('Введите корректный API-ключ Wildberries');
      return;
    }
    setError('');
    try {
      await onConnectMarketplace(apiKey.trim());
    } catch {
      setError('Не удалось подключить ключ. Проверьте API-ключ и права доступа.');
    }
  };

  if (isSyncing) {
    const progressPct = loadedCount && loadedCount > 0
      ? Math.min(95, Math.round((loadedCount / Math.max(loadedCount * 1.5, 100)) * 100))
      : undefined;
    return (
      <div className="onboarding sync-screen">
        <div className="sync-animation"></div>
        <div className="sync-title">Подключаемся к Wildberries</div>
        <div className="sync-desc">Проверяем API-ключ и загружаем чаты, отзывы и вопросы</div>
        <div className="sync-progress">
          <div
            className="sync-progress-bar"
            style={progressPct !== undefined ? { width: `${progressPct}%`, animation: 'none' } : undefined}
          />
        </div>
        <div className="sync-stats">
          <div className="sync-stat">
            <div className="sync-stat-value">
              {loadedCount && loadedCount > 0
                ? `Загружено: ${loadedCount} сообщений`
                : 'Загрузка данных из Wildberries'}
            </div>
            <div className="sync-stat-label">остальные данные догрузятся в фоне</div>
          </div>
        </div>
        <button className="btn-cta" type="button" style={{ maxWidth: 320 }} onClick={onContinue}>
          Перейти к сообщениям
        </button>
        <button className="btn-skip" type="button" onClick={onSkip}>
          Пропустить и открыть демо
        </button>
      </div>
    );
  }

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-logo">AGENT<span>IQ</span></div>
        <div className="onboarding-subtitle">AI-платформа для маркетплейсов</div>

        <div className="onboarding-step-indicator">
          <div className="step-dot active"></div>
          <div className="step-dot"></div>
        </div>

        <div className="onboarding-title">{title}</div>
        <div className="onboarding-desc">{description}</div>

        <div className="marketplace-buttons">
          <div className="marketplace-btn selected">
            <div className="mp-icon wb">W</div>
            <div className="mp-info">
              <div className="mp-name">Wildberries</div>
              <div className="mp-desc">Чаты, отзывы, вопросы</div>
            </div>
          </div>
          <div className="marketplace-btn disabled">
            <div className="mp-icon ozon">Ozon</div>
            <div className="mp-info">
              <div className="mp-name">Ozon</div>
              <div className="mp-desc">Чаты, отзывы, вопросы</div>
            </div>
            <div className="mp-badge">Скоро</div>
          </div>
        </div>

        {canConnect && (
          <div className="api-key-section">
            <div className="api-key-label">API-ключ Wildberries</div>
            <div className="api-key-input-row">
              <input
                id="wb-api-key"
                className="api-key-field"
                type="text"
                placeholder="Вставьте ключ из ЛК продавца"
                value={apiKey}
                onChange={(event) => {
                  setApiKey(event.target.value);
                  setError('');
                }}
                disabled={Boolean(isConnecting)}
              />
            </div>
            <div className="api-key-hint">
              Создайте ключ в{' '}
              <a
                href="https://seller.wildberries.ru/supplier-settings/access-to-api"
                target="_blank"
                rel="noreferrer noopener"
              >
                Настройки → Доступ к API
              </a>{' '}
              с правами на коммуникации
            </div>
          </div>
        )}

        {error && <div className="onboarding-error">{error}</div>}

        {canConnect && (
          <button type="button" className="btn-cta" onClick={handleConnect} disabled={Boolean(isConnecting)}>
            {isConnecting ? 'Подключение...' : 'Подключить и загрузить чаты'}
          </button>
        )}

        {user.sync_status === 'error' && onRetrySync && (
          <button type="button" className="btn-skip" onClick={() => onRetrySync()} disabled={Boolean(isRetryingSync)}>
            {isRetryingSync ? 'Повтор...' : 'Повторить синхронизацию'}
          </button>
        )}

        {canContinue && (
          <button type="button" className="btn-cta" onClick={onContinue}>
            Перейти к сообщениям
          </button>
        )}

        <button type="button" className="btn-skip" onClick={onSkip}>
          Пропустить, посмотрю сначала
        </button>
      </div>
    </div>
  );
}
