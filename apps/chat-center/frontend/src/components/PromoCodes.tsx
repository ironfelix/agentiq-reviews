import { useEffect, useMemo, useState } from 'react';

import type { PromoChannels, PromoCode, PromoConfig, User } from '../types';
import { settingsApi } from '../services/api';

const STORAGE_KEY = 'agentiq_promo_codes_v1';
const STORAGE_CONFIG_KEY = 'agentiq_promo_config_v1';
const MAX_PROMOS = 10;

function nowIso() {
  return new Date().toISOString();
}

function loadPromoCodes(): PromoCode[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function savePromoCodes(items: PromoCode[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // ignore
  }
}

function loadPromoConfig(): PromoConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_CONFIG_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const record = parsed as Partial<PromoConfig>;
    return {
      ai_offer_enabled: Boolean(record.ai_offer_enabled),
      warn_reviews_enabled: Boolean(record.warn_reviews_enabled),
    };
  } catch {
    return null;
  }
}

function savePromoConfig(cfg: PromoConfig) {
  try {
    localStorage.setItem(STORAGE_CONFIG_KEY, JSON.stringify(cfg));
  } catch {
    // ignore
  }
}

function defaultChannels(): PromoChannels {
  return {
    chat_positive: true,
    chat_negative: true,
    chat_questions: true,
    reviews_positive: false,
    reviews_negative: false,
  };
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

const DEFAULT_CONFIG: PromoConfig = {
  ai_offer_enabled: true,
  warn_reviews_enabled: true,
};

export function PromoCodes(props: { user: User }) {
  const { user } = props;
  const [items, setItems] = useState<PromoCode[]>(() => loadPromoCodes());
  const [config, setConfig] = useState<PromoConfig>(() => loadPromoConfig() || DEFAULT_CONFIG);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');

  const [draftCode, setDraftCode] = useState('');
  const [draftDiscount, setDraftDiscount] = useState('10%');
  const [draftExpires, setDraftExpires] = useState('до конца месяца');
  const [draftScope, setDraftScope] = useState<'all' | 'selected'>('all');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoadError(null);
      try {
        const res = await settingsApi.getPromoSettings();
        if (cancelled) return;
        setItems(Array.isArray(res.promo_codes) ? res.promo_codes : []);
        setConfig(res.config || DEFAULT_CONFIG);
        setIsLoaded(true);
      } catch {
        // Fallback to local cache.
        if (cancelled) return;
        setIsLoaded(true);
        setLoadError('Не удалось загрузить промокоды с сервера. Показаны локальные данные браузера.');
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    savePromoCodes(items);
    savePromoConfig(config);

    // Debounced autosave to backend.
    setSaveState((prev) => (prev === 'saving' ? prev : 'idle'));
    const handle = window.setTimeout(async () => {
      try {
        setSaveState('saving');
        await settingsApi.updatePromoSettings({
          promo_codes: items.slice(0, MAX_PROMOS),
          config,
        });
        setSaveState('saved');
        window.setTimeout(() => setSaveState('idle'), 1200);
      } catch {
        setSaveState('error');
      }
    }, 700);
    return () => window.clearTimeout(handle);
  }, [items, config, isLoaded]);

  const activeCount = useMemo(() => items.filter((p) => p.active).length, [items]);

  const toggleChannel = (promoId: string, key: keyof PromoChannels) => {
    setItems((prev) =>
      prev.map((p) => {
        if (p.id !== promoId) return p;
        return {
          ...p,
          updated_at: nowIso(),
          channels: { ...p.channels, [key]: !p.channels[key] },
        };
      })
    );
  };

  const deletePromo = (promoId: string) => {
    setItems((prev) => prev.filter((p) => p.id !== promoId));
    if (expandedId === promoId) setExpandedId(null);
  };

  const addPromo = () => {
    const code = draftCode.trim().toUpperCase();
    if (!code) return;
    const ts = nowIso();
    const promo: PromoCode = {
      id: `promo_${Math.random().toString(16).slice(2)}_${Date.now()}`,
      code,
      discount_label: draftDiscount.trim() || '—',
      expires_label: draftExpires.trim() || 'без срока',
      scope_label: draftScope === 'all' ? 'Все товары' : 'Выбранные артикулы',
      sent_count: 0,
      active: true,
      channels: defaultChannels(),
      created_at: ts,
      updated_at: ts,
    };
    setItems((prev) => [promo, ...prev].slice(0, MAX_PROMOS));
    setDraftCode('');
    setShowAddForm(false);
  };

  return (
    <div className="settings-content promo-page" style={{ padding: 32, maxWidth: 780 }}>
      <div className="settings-section-title">Промокоды</div>
      <div className="promo-cabinet-selector">
        <div className="promo-cabinet-icon">W</div>
        <div className="promo-cabinet-info">
          <div className="promo-cabinet-name">{user.name}</div>
          <div className="promo-cabinet-mp">{user.marketplace || 'wildberries'}</div>
        </div>
      </div>

      <div className="settings-section-desc">
        Промокоды создаются в ЛК Wildberries. Здесь вы указываете их для AI, чтобы он мог предлагать промокод в ответах, когда это уместно.
      </div>

      {loadError && <div className="settings-inline-note error" style={{ marginTop: 10 }}>{loadError}</div>}

      <div className="promo-desc-row">
        <div className="promo-count" style={{ marginBottom: 0 }}>
          Активные промокоды ({activeCount} из {MAX_PROMOS})
        </div>
        <div className="promo-top-actions">
          {saveState === 'saving' && <span className="promo-save-pill">Сохранение...</span>}
          {saveState === 'saved' && <span className="promo-save-pill ok">Сохранено</span>}
          {saveState === 'error' && <span className="promo-save-pill bad">Ошибка сохранения</span>}
          <button className="promo-help-link" type="button" onClick={() => setHelpOpen(true)}>
            Как это работает?
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="promo-empty">
          <div className="promo-empty-title">Пока нет промокодов</div>
          <div className="promo-empty-desc">
            Добавьте хотя бы один промокод, чтобы AI мог подставлять его в релевантные ответы.
          </div>
        </div>
      ) : (
        <div className="promo-list">
          {items.map((promo) => {
            const expanded = expandedId === promo.id;
            return (
              <div
                key={promo.id}
                className={`promo-card${expanded ? ' expanded' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => setExpandedId(expanded ? null : promo.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') setExpandedId(expanded ? null : promo.id);
                }}
              >
                <div className="promo-card-header">
                  <div className="promo-code-name">{promo.code}</div>
                  <div className={`promo-badge ${promo.active ? 'active' : 'expired'}`}>
                    {promo.active ? 'Активен' : 'Истёк'}
                  </div>
                </div>
                <div className="promo-meta">
                  Скидка {promo.discount_label} · {promo.expires_label} · {promo.scope_label}
                </div>
                <div className="promo-channels">
                  <span
                    className={`promo-channel ${promo.channels.chat_positive ? 'on' : ''}`}
                    onClick={(e) => { e.stopPropagation(); toggleChannel(promo.id, 'chat_positive'); }}
                  >
                    Чаты: позитив
                  </span>
                  <span
                    className={`promo-channel ${promo.channels.chat_negative ? 'on' : ''}`}
                    onClick={(e) => { e.stopPropagation(); toggleChannel(promo.id, 'chat_negative'); }}
                  >
                    Чаты: негатив
                  </span>
                  <span
                    className={`promo-channel ${promo.channels.chat_questions ? 'on' : ''}`}
                    onClick={(e) => { e.stopPropagation(); toggleChannel(promo.id, 'chat_questions'); }}
                  >
                    Чаты: вопросы
                  </span>
                  <span
                    className={`promo-channel ${promo.channels.reviews_positive ? 'on' : ''}`}
                    onClick={(e) => { e.stopPropagation(); toggleChannel(promo.id, 'reviews_positive'); }}
                  >
                    Отзывы: позитив
                  </span>
                  <span
                    className={`promo-channel ${promo.channels.reviews_negative ? 'on' : ''}`}
                    onClick={(e) => { e.stopPropagation(); toggleChannel(promo.id, 'reviews_negative'); }}
                  >
                    Отзывы: негатив
                  </span>
                </div>
                <div className="promo-card-footer">
                  <div className="promo-sends">Отправлено: {promo.sent_count} раз</div>
                  <div className="promo-actions">
                    <button
                      type="button"
                      className="promo-action-btn danger"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Удалить промокод ${promo.code}?`)) deletePromo(promo.id);
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!showAddForm ? (
        <button type="button" className="promo-add-btn" onClick={() => setShowAddForm(true)} disabled={items.length >= MAX_PROMOS}>
          + Добавить промокод
        </button>
      ) : (
        <div className="promo-card promo-add-form">
          <div className="promo-card-header">
            <div className="promo-code-name">Новый промокод</div>
          </div>
          <div className="promo-form-grid">
            <label className="promo-form-field">
              <div className="promo-form-label">Код</div>
              <input
                className="promo-form-input"
                value={draftCode}
                placeholder="THANKS10"
                onChange={(e) => setDraftCode(e.target.value)}
              />
            </label>
            <label className="promo-form-field">
              <div className="promo-form-label">Скидка</div>
              <input
                className="promo-form-input"
                value={draftDiscount}
                onChange={(e) => setDraftDiscount(e.target.value)}
              />
            </label>
            <label className="promo-form-field">
              <div className="promo-form-label">Срок</div>
              <input
                className="promo-form-input"
                value={draftExpires}
                onChange={(e) => setDraftExpires(e.target.value)}
              />
            </label>
            <div className="promo-form-field">
              <div className="promo-form-label">Товары</div>
              <div className="promo-radio-row">
                <label className="promo-radio">
                  <input
                    type="radio"
                    name="promo-scope"
                    checked={draftScope === 'all'}
                    onChange={() => setDraftScope('all')}
                  />
                  Все товары
                </label>
                <label className="promo-radio">
                  <input
                    type="radio"
                    name="promo-scope"
                    checked={draftScope === 'selected'}
                    onChange={() => setDraftScope('selected')}
                  />
                  Выбранные артикулы
                </label>
              </div>
            </div>
          </div>
          <div className="promo-form-actions">
            <button type="button" className="promo-form-save" onClick={addPromo} disabled={!draftCode.trim()}>
              Сохранить
            </button>
            <button
              type="button"
              className="promo-form-cancel"
              onClick={() => {
                setShowAddForm(false);
                setDraftCode('');
              }}
            >
              Отмена
            </button>
          </div>
          <div className="promo-form-footnote">
            Промокоды хранятся на сервере (и кэшируются в браузере), чтобы AI мог использовать их в подсказках.
          </div>
        </div>
      )}

      <div className="promo-divider" />

      <div className="promo-count">Настройки автоподстановки</div>

      <div className="ai-setting-card">
        <div className="ai-setting-header">
          <div className="ai-setting-title">AI предлагает промокод в ответах</div>
          <button
            type="button"
            className={`toggle ${config.ai_offer_enabled ? 'on' : ''}`}
            aria-label="Toggle promo offers"
            onClick={() => setConfig((prev) => ({ ...prev, ai_offer_enabled: !prev.ai_offer_enabled }))}
          />
        </div>
        <div className="ai-setting-desc">
          AI добавит промокод в черновик ответа, когда это уместно. Вы увидите его перед отправкой и сможете убрать.
        </div>
      </div>

      <div className="ai-setting-card">
        <div className="ai-setting-header">
          <div className="ai-setting-title">Предупреждать об отзывах</div>
          <button
            type="button"
            className={`toggle ${config.warn_reviews_enabled ? 'on' : ''}`}
            aria-label="Toggle reviews warning"
            onClick={() => setConfig((prev) => ({ ...prev, warn_reviews_enabled: !prev.warn_reviews_enabled }))}
          />
        </div>
        <div className="ai-setting-desc">
          Показывать напоминание, что промокод в ответе на отзыв виден всем посетителям карточки товара.
        </div>
      </div>

      <div className={`promo-help-panel${helpOpen ? ' open' : ''}`} role="dialog" aria-modal="true">
        <button className="promo-help-close" type="button" onClick={() => setHelpOpen(false)} aria-label="Close">
          &times;
        </button>
        <div className="promo-help-title">Как работают промокоды</div>

        <div className="promo-help-section">
          <div className="promo-help-label">Создание</div>
          <div className="promo-help-text">
            Промокоды создаются в личном кабинете WB. AgentIQ не создаёт промокоды за вас.
            Здесь вы просто фиксируете “какие промокоды у вас есть” и где их можно использовать.
          </div>
        </div>

        <div className="promo-help-section">
          <div className="promo-help-label">Как применяется</div>
          <div className="promo-help-text">
            Покупатель вводит код в корзине на WB. Код многоразовый, его может использовать любой покупатель.
            AI может предложить промокод только в релевантном контексте. Для WB чата промокоды считаются P3 и по умолчанию запрещены,
            кроме узких окон (запрос покупателя / компенсация кейса).
          </div>
        </div>

        <div className="promo-help-warning">
          Важно: нельзя стимулировать отзывы (“за 5 звезд дадим промокод”). И нельзя уводить покупателя на сторонние ресурсы.
        </div>
      </div>
    </div>
  );
}
