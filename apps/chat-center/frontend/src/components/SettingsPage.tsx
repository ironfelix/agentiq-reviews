import { useEffect, useMemo, useState, useCallback } from 'react';
import type { AISettings, AITone, AutoResponseChannel, User } from '../types';
import { settingsApi } from '../services/api';
import { PromoCodes } from './PromoCodes';

type SettingsTab = 'connections' | 'ai' | 'promo' | 'profile';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function formatSyncLabel(lastSyncAt?: string | null) {
  if (!lastSyncAt) return 'Последняя синхр. —';
  const dt = new Date(lastSyncAt);
  if (Number.isNaN(dt.getTime())) return 'Последняя синхр. —';
  const minutes = Math.round((Date.now() - dt.getTime()) / 60000);
  if (minutes <= 1) return 'Последняя синхр. только что';
  if (minutes < 60) return `Последняя синхр. ${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Последняя синхр. ${hours} ч назад`;
  const days = Math.round(hours / 24);
  return `Последняя синхр. ${days} д назад`;
}

const DEFAULT_AI_SETTINGS: AISettings = {
  tone: 'friendly',
  auto_replies_positive: false,
  ai_suggestions: true,
  auto_response_channels: ['review'],
  auto_response_nm_ids: [],
};

export function SettingsPage(props: {
  user: User;
  onOpenConnectOnboarding: () => void;
  onLogout: () => void;
}) {
  const { user, onOpenConnectOnboarding, onLogout } = props;

  // Read initial tab from URL hash (e.g., #settings-promo)
  const getInitialTab = (): SettingsTab => {
    const hash = window.location.hash;
    if (hash.startsWith('#settings-')) {
      const tabFromHash = hash.replace('#settings-', '') as SettingsTab;
      if (['connections', 'ai', 'promo', 'profile'].includes(tabFromHash)) {
        return tabFromHash;
      }
    }
    return 'connections';
  };

  const [tab, setTab] = useState<SettingsTab>(getInitialTab);

  const [aiSettings, setAISettings] = useState<AISettings>(DEFAULT_AI_SETTINGS);
  const [aiLoadState, setAILoadState] = useState<'idle' | 'loading' | 'error'>('idle');
  const [aiSaveState, setAISaveState] = useState<SaveState>('idle');
  const [aiError, setAIError] = useState<string | null>(null);
  const [nmIdsText, setNmIdsText] = useState<string>('');

  const isWbConnected = Boolean(user.has_api_credentials) && user.sync_status !== 'error';
  const wbStatusLabel = isWbConnected
    ? `Подключено · ${formatSyncLabel(user.last_sync_at)}`
    : user.sync_status === 'error'
      ? 'Ошибка синхронизации'
      : 'Не подключено';

  const wbStatusTone = isWbConnected ? 'connected' : 'disconnected';

  // Helper to change tab and update URL hash
  const changeTab = (newTab: SettingsTab) => {
    setTab(newTab);
    window.location.hash = `settings-${newTab}`;
  };

  useEffect(() => {
    if (tab !== 'ai') return;
    let cancelled = false;

    const load = async () => {
      setAILoadState('loading');
      setAIError(null);
      try {
        const res = await settingsApi.getAISettings();
        if (cancelled) return;
        const loaded = res.settings || DEFAULT_AI_SETTINGS;
        // Ensure new fields have defaults for backwards compatibility
        if (!loaded.auto_response_channels) loaded.auto_response_channels = ['review'];
        if (!loaded.auto_response_nm_ids) loaded.auto_response_nm_ids = [];
        setAISettings(loaded);
        setNmIdsText(loaded.auto_response_nm_ids.length > 0 ? loaded.auto_response_nm_ids.join(', ') : '');
        setAILoadState('idle');
      } catch {
        if (cancelled) return;
        setAILoadState('error');
        setAIError('Не удалось загрузить настройки AI');
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [tab]);

  const toneLabel = useMemo(() => {
    const map: Record<AITone, string> = {
      formal: 'Формальный',
      friendly: 'Дружелюбный',
      neutral: 'Нейтральный',
    };
    return map[aiSettings.tone];
  }, [aiSettings.tone]);

  const toggleChannel = useCallback((ch: AutoResponseChannel) => {
    setAISettings((prev) => {
      const channels = prev.auto_response_channels || [];
      const next = channels.includes(ch)
        ? channels.filter((c) => c !== ch)
        : [...channels, ch];
      return { ...prev, auto_response_channels: next };
    });
  }, []);

  const handleNmIdsChange = useCallback((value: string) => {
    setNmIdsText(value);
    // Parse comma-separated integers, ignoring invalid entries
    const parsed = value
      .split(/[,;\s]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && /^\d+$/.test(s))
      .map(Number);
    setAISettings((prev) => ({ ...prev, auto_response_nm_ids: parsed }));
  }, []);

  const saveAI = async () => {
    setAISaveState('saving');
    setAIError(null);
    try {
      const res = await settingsApi.updateAISettings({ settings: aiSettings });
      setAISettings(res.settings);
      setAISaveState('saved');
      window.setTimeout(() => setAISaveState('idle'), 1200);
    } catch {
      setAISaveState('error');
      setAIError('Не удалось сохранить настройки AI');
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-nav">
        <div className="settings-nav-title">Настройки</div>
        <button
          className={`settings-nav-item ${tab === 'connections' ? 'active' : ''}`}
          type="button"
          onClick={() => changeTab('connections')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
            <line x1="6" y1="6" x2="6.01" y2="6" />
            <line x1="6" y1="18" x2="6.01" y2="18" />
          </svg>
          Подключения
        </button>
        <button
          className={`settings-nav-item ${tab === 'ai' ? 'active' : ''}`}
          type="button"
          onClick={() => changeTab('ai')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
          AI-ассистент
        </button>
        <button
          className={`settings-nav-item ${tab === 'promo' ? 'active' : ''}`}
          type="button"
          onClick={() => changeTab('promo')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 12 20 22 4 22 4 12"/>
            <rect x="2" y="7" width="20" height="5"/>
            <line x1="12" y1="22" x2="12" y2="7"/>
            <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/>
            <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/>
          </svg>
          Промокоды
        </button>
        <button
          className={`settings-nav-item ${tab === 'profile' ? 'active' : ''}`}
          type="button"
          onClick={() => changeTab('profile')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          Профиль
        </button>
      </div>

      <div className="settings-content">
        {tab === 'connections' && (
          <div>
            <div className="settings-section-title">Подключения</div>
            <div className="settings-section-desc">
              Управляйте подключениями к маркетплейсам. AgentIQ синхронизирует чаты и обращения в фоне.
            </div>

            <div className="connection-card">
              <div className="connection-icon wb">W</div>
              <div className="connection-info">
                <div className="connection-name">Wildberries</div>
                <div className={`connection-status ${wbStatusTone}`}>
                  <div className="connection-status-dot" />
                  {wbStatusLabel}
                </div>
              </div>
              <button
                className={`connection-action ${isWbConnected ? '' : 'primary'}`}
                type="button"
                onClick={onOpenConnectOnboarding}
              >
                {isWbConnected ? 'Настроить' : 'Подключить'}
              </button>
            </div>

            <div className="connection-card">
              <div className="connection-icon ozon">Ozon</div>
              <div className="connection-info">
                <div className="connection-name">Ozon</div>
                <div className="connection-status disconnected">
                  <div className="connection-status-dot" />
                  Скоро
                </div>
              </div>
              <button className="connection-action" type="button" disabled>
                Подключить
              </button>
            </div>
          </div>
        )}

        {tab === 'ai' && (
          <div>
            <div className="settings-section-title">AI-ассистент</div>
            <div className="settings-section-desc">
              Настройте, как AI генерирует ответы. Изменения влияют на черновики ответов и подсказки.
            </div>

            {aiLoadState === 'loading' && (
              <div className="settings-inline-note">Загрузка настроек AI...</div>
            )}
            {aiLoadState === 'error' && (
              <div className="settings-inline-note error">{aiError || 'Ошибка загрузки'}</div>
            )}

            <div className="ai-setting-card">
              <div className="ai-setting-header">
                <div className="ai-setting-title">Тон ответов</div>
                <div className="ai-setting-pill">{toneLabel}</div>
              </div>
              <div className="ai-setting-desc">Выберите стиль общения AI с покупателями</div>
              <div className="tone-options">
                <button
                  type="button"
                  className={`tone-option ${aiSettings.tone === 'formal' ? 'active' : ''}`}
                  onClick={() => setAISettings((prev) => ({ ...prev, tone: 'formal' }))}
                >
                  <div className="tone-emoji">{'\u{1F454}'}</div>
                  <div className="tone-name">Формальный</div>
                </button>
                <button
                  type="button"
                  className={`tone-option ${aiSettings.tone === 'friendly' ? 'active' : ''}`}
                  onClick={() => setAISettings((prev) => ({ ...prev, tone: 'friendly' }))}
                >
                  <div className="tone-emoji">{'\u{1F60A}'}</div>
                  <div className="tone-name">Дружелюбный</div>
                </button>
                <button
                  type="button"
                  className={`tone-option ${aiSettings.tone === 'neutral' ? 'active' : ''}`}
                  onClick={() => setAISettings((prev) => ({ ...prev, tone: 'neutral' }))}
                >
                  <div className="tone-emoji">{'\u{1F4DD}'}</div>
                  <div className="tone-name">Нейтральный</div>
                </button>
              </div>
            </div>

            <div className="ai-setting-card">
              <div className="ai-setting-header">
                <div className="ai-setting-title">Авто-ответы</div>
                <button
                  type="button"
                  className={`toggle ${aiSettings.auto_replies_positive ? 'on' : ''}`}
                  aria-label="Toggle auto replies"
                  onClick={() =>
                    setAISettings((prev) => ({ ...prev, auto_replies_positive: !prev.auto_replies_positive }))
                  }
                />
              </div>
              <div className="ai-setting-desc">
                Автоматически отвечать на позитивные обращения (4-5★) без вашего участия. Ответы помечаются значком «АВТО».
              </div>

              {aiSettings.auto_replies_positive && (
                <div className="auto-response-options">
                  <div className="auto-response-section">
                    <div className="auto-response-label">Каналы для авто-ответов</div>
                    <div className="auto-response-channels">
                      <label className="channel-checkbox">
                        <input
                          type="checkbox"
                          checked={(aiSettings.auto_response_channels || []).includes('review')}
                          onChange={() => toggleChannel('review')}
                        />
                        <span className="channel-checkbox-mark" />
                        <span className="channel-checkbox-text">Отзывы</span>
                      </label>
                      <label className="channel-checkbox">
                        <input
                          type="checkbox"
                          checked={(aiSettings.auto_response_channels || []).includes('question')}
                          onChange={() => toggleChannel('question')}
                        />
                        <span className="channel-checkbox-mark" />
                        <span className="channel-checkbox-text">Вопросы</span>
                      </label>
                      <label className="channel-checkbox">
                        <input
                          type="checkbox"
                          checked={(aiSettings.auto_response_channels || []).includes('chat')}
                          onChange={() => toggleChannel('chat')}
                        />
                        <span className="channel-checkbox-mark" />
                        <span className="channel-checkbox-text">Чаты</span>
                      </label>
                    </div>
                  </div>

                  <div className="auto-response-section">
                    <div className="auto-response-label">Артикулы (необязательно)</div>
                    <input
                      type="text"
                      className="form-input auto-response-nm-input"
                      placeholder="Введите артикулы через запятую, напр. 123456, 789012"
                      value={nmIdsText}
                      onChange={(e) => handleNmIdsChange(e.target.value)}
                    />
                    <div className="auto-response-hint">
                      Пусто = все артикулы. Укажите 1-3 для тестового запуска.
                    </div>
                    {aiSettings.auto_response_nm_ids.length > 0 && (
                      <div className="auto-response-nm-tags">
                        {aiSettings.auto_response_nm_ids.map((nm) => (
                          <span key={nm} className="nm-tag">{nm}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="ai-setting-card">
              <div className="ai-setting-header">
                <div className="ai-setting-title">AI-подсказки</div>
                <button
                  type="button"
                  className={`toggle ${aiSettings.ai_suggestions ? 'on' : ''}`}
                  aria-label="Toggle AI suggestions"
                  onClick={() => setAISettings((prev) => ({ ...prev, ai_suggestions: !prev.ai_suggestions }))}
                />
              </div>
              <div className="ai-setting-desc">
                Показывать AI-рекомендацию ответа для каждого нового обращения. Вы можете отредактировать или отклонить подсказку.
              </div>
            </div>

            <div className="settings-save-row">
              <button className="form-save" type="button" onClick={saveAI} disabled={aiSaveState === 'saving'}>
                {aiSaveState === 'saving' ? 'Сохранение...' : 'Сохранить'}
              </button>
              {aiSaveState === 'saved' && <div className="settings-inline-note success">Сохранено</div>}
              {aiSaveState === 'error' && <div className="settings-inline-note error">{aiError || 'Ошибка'}</div>}
            </div>
          </div>
        )}

        {tab === 'promo' && (
          <PromoCodes user={user} />
        )}

        {tab === 'profile' && (
          <div>
            <div className="settings-section-title">Профиль</div>
            <div className="settings-section-desc">Основная информация о вашем аккаунте.</div>

            <div className="profile-form">
              <div className="form-field">
                <label className="form-label">Название компании</label>
                <input type="text" className="form-input" value={user.name} readOnly />
              </div>
              <div className="form-field">
                <label className="form-label">Email</label>
                <input type="email" className="form-input" value={user.email} readOnly />
              </div>
              <div className="settings-save-row">
                <button className="form-save danger" type="button" onClick={onLogout}>
                  Выйти
                </button>
                <div className="settings-inline-note">Управление профилем будет добавлено позже.</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
