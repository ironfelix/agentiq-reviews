import { useCallback, useEffect, useState } from 'react';
import type {
  AISettings,
  AutoResponseChannel,
  PresetInfo,
  ScenarioConfig,
} from '../types';
import { settingsApi } from '../services/api';

/** Human-readable labels for scenario intents. */
const INTENT_LABELS: Record<string, { name: string; desc: string }> = {
  thanks: {
    name: 'Позитивные отзывы (4-5★)',
    desc: '«Спасибо за отзыв!» — благодарность, вариативный текст',
  },
  delivery_status: {
    name: 'WISMO — «Где мой заказ?»',
    desc: 'Шаблон: «Отследите в ЛК WB → Доставки»',
  },
  pre_purchase: {
    name: 'Pre-purchase вопросы',
    desc: 'Размер, наличие, совместимость — с контекстом из карточки товара',
  },
  sizing_fit: {
    name: 'Размер и посадка',
    desc: 'AI ответит с данными из размерной сетки товара',
  },
  availability: {
    name: 'Наличие товара',
    desc: 'Информация о наличии и поступлении',
  },
  compatibility: {
    name: 'Совместимость',
    desc: 'Совместим ли товар с указанным устройством/моделью',
  },
  refund_exchange: {
    name: 'Возврат / обмен',
    desc: 'Инструкция по возврату через ЛК WB',
  },
};

/** Descriptions for blocked scenarios (unique per intent). */
const BLOCK_INFO: Record<string, { name: string; desc: string }> = {
  defect_not_working: {
    name: 'Брак / дефект',
    desc: 'AI поможет составить ответ — решение за вами',
  },
  wrong_item: {
    name: 'Не тот товар',
    desc: 'AI предложит вариант ответа — отправка только вручную',
  },
  quality_complaint: {
    name: 'Жалоба на качество',
    desc: 'AI подготовит черновик — вы редактируете и решаете',
  },
};

/** Channel short labels for tags. */
const CHANNEL_TAG_LABELS: Record<string, string> = {
  review: 'отзывы',
  question: 'вопросы',
  chat: 'чаты',
};

const ALWAYS_BLOCK_INTENTS = new Set(['defect_not_working', 'wrong_item', 'quality_complaint']);

/** Order for displaying auto-eligible scenarios. */
const AUTO_SCENARIO_ORDER = [
  'thanks',
  'delivery_status',
  'pre_purchase',
  'sizing_fit',
  'availability',
  'compatibility',
  'refund_exchange',
];

const BLOCK_SCENARIO_ORDER = ['defect_not_working', 'wrong_item', 'quality_complaint'];

/** Preset emoji icons. */
const PRESET_ICONS: Record<string, string> = {
  safe: '\u{1F6E1}',
  balanced: '\u2696',
  max: '\u26A1',
};

export function AutoResponseSettings(props: {
  aiSettings: AISettings;
  onSettingsChange: (settings: AISettings) => void;
}) {
  const { aiSettings, onSettingsChange } = props;

  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [applyingPreset, setApplyingPreset] = useState<string | null>(null);
  const [scope, setScope] = useState<'all' | 'specific'>(
    (aiSettings.auto_response_nm_ids || []).length > 0 ? 'specific' : 'all'
  );
  const [nmText, setNmText] = useState('');

  // Load presets on mount
  useEffect(() => {
    settingsApi.getAutoResponsePresets().then((res) => {
      setPresets(res.presets);
    }).catch(() => {});
  }, []);

  // Sync scope when nm_ids change externally (e.g. from preset)
  useEffect(() => {
    const ids = aiSettings.auto_response_nm_ids || [];
    setScope(ids.length > 0 ? 'specific' : 'all');
  }, [aiSettings.auto_response_nm_ids]);

  const scenarios = aiSettings.auto_response_scenarios || {};
  const channels = aiSettings.auto_response_channels || ['review'];

  const toggleMaster = useCallback(() => {
    onSettingsChange({
      ...aiSettings,
      auto_replies_positive: !aiSettings.auto_replies_positive,
    });
  }, [aiSettings, onSettingsChange]);

  const toggleChannel = useCallback((ch: AutoResponseChannel) => {
    const next = channels.includes(ch)
      ? channels.filter((c) => c !== ch)
      : [...channels, ch];
    onSettingsChange({ ...aiSettings, auto_response_channels: next as AutoResponseChannel[] });
  }, [aiSettings, channels, onSettingsChange]);

  const toggleScenario = useCallback((intent: string) => {
    if (ALWAYS_BLOCK_INTENTS.has(intent)) return;
    const current = scenarios[intent];
    if (!current) return;
    const updated: ScenarioConfig = { ...current, enabled: !current.enabled };
    onSettingsChange({
      ...aiSettings,
      auto_response_scenarios: { ...scenarios, [intent]: updated },
    });
  }, [aiSettings, scenarios, onSettingsChange]);

  const handleScopeChange = useCallback((newScope: 'all' | 'specific') => {
    setScope(newScope);
    if (newScope === 'all') {
      onSettingsChange({ ...aiSettings, auto_response_nm_ids: [] });
    }
  }, [aiSettings, onSettingsChange]);

  /** Commit current input text as tag(s) if valid. */
  const commitNmInput = useCallback(() => {
    const parsed = nmText
      .split(/[,;\s]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && /^\d+$/.test(s))
      .map(Number);
    if (parsed.length === 0) return;
    const existing = new Set(aiSettings.auto_response_nm_ids || []);
    const merged = [...(aiSettings.auto_response_nm_ids || [])];
    for (const id of parsed) {
      if (!existing.has(id)) {
        merged.push(id);
        existing.add(id);
      }
    }
    onSettingsChange({ ...aiSettings, auto_response_nm_ids: merged });
    setNmText('');
  }, [nmText, aiSettings, onSettingsChange]);

  /** Handle typing — commit on comma/semicolon. */
  const handleNmTextChange = useCallback((value: string) => {
    // If ends with comma/semicolon, commit immediately
    if (/[,;]\s*$/.test(value)) {
      const clean = value.replace(/[,;\s]+$/, '');
      setNmText(clean);
      // commit after state update
      const parsed = clean
        .split(/[,;\s]+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0 && /^\d+$/.test(s))
        .map(Number);
      if (parsed.length > 0) {
        const existing = new Set(aiSettings.auto_response_nm_ids || []);
        const merged = [...(aiSettings.auto_response_nm_ids || [])];
        for (const id of parsed) {
          if (!existing.has(id)) {
            merged.push(id);
            existing.add(id);
          }
        }
        onSettingsChange({ ...aiSettings, auto_response_nm_ids: merged });
        setNmText('');
      }
    } else {
      setNmText(value);
    }
  }, [aiSettings, onSettingsChange]);

  /** Handle Enter and Backspace. */
  const handleNmKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitNmInput();
    } else if (e.key === 'Backspace' && nmText === '') {
      // Remove last tag
      const ids = aiSettings.auto_response_nm_ids || [];
      if (ids.length > 0) {
        onSettingsChange({ ...aiSettings, auto_response_nm_ids: ids.slice(0, -1) });
      }
    }
  }, [nmText, aiSettings, onSettingsChange, commitNmInput]);

  const removeNmId = useCallback((id: number) => {
    const next = (aiSettings.auto_response_nm_ids || []).filter((n) => n !== id);
    onSettingsChange({ ...aiSettings, auto_response_nm_ids: next });
  }, [aiSettings, onSettingsChange]);

  const handleApplyPreset = useCallback(async (presetName: string) => {
    setApplyingPreset(presetName);
    try {
      const res = await settingsApi.applyPreset({ preset: presetName });
      onSettingsChange({
        ...aiSettings,
        auto_response_scenarios: res.scenarios,
        auto_response_channels: res.channels as AutoResponseChannel[],
        auto_replies_positive: true,
      });
      setActivePreset(presetName);
    } catch {
      // ignore
    } finally {
      setApplyingPreset(null);
    }
  }, [aiSettings, onSettingsChange]);

  const togglePromo = useCallback(() => {
    onSettingsChange({
      ...aiSettings,
      auto_response_promo_on_5star: !aiSettings.auto_response_promo_on_5star,
    });
  }, [aiSettings, onSettingsChange]);

  return (
    <div className="ar-card">
      {/* Master toggle */}
      <div className="ar-card-header">
        <div className="ar-card-title">Авто-ответы включены</div>
        <button
          type="button"
          className={`toggle ${aiSettings.auto_replies_positive ? 'on' : ''}`}
          aria-label="Toggle auto-response"
          onClick={toggleMaster}
        />
      </div>
      <div className="ar-card-desc">
        Мы отвечаем на обращения покупателей за вас. Каждый ответ проверяется на безопасность перед отправкой.
      </div>

      {/* Expanded settings */}
      {aiSettings.auto_replies_positive && (
        <div className="ar-expand">

          {/* Scope */}
          <div className="ar-section-block">
            <div className="ar-section-label">Область действия</div>
            <div className="ar-scope-options">
              <label className="ar-scope-radio">
                <input
                  type="radio"
                  name="ar-scope"
                  checked={scope === 'all'}
                  onChange={() => handleScopeChange('all')}
                />
                <div className="ar-radio-mark" />
                <div className="ar-radio-content">
                  <div className="ar-radio-title">Весь кабинет</div>
                  <div className="ar-radio-desc">Авто-ответы для всех артикулов</div>
                </div>
              </label>
              <label className="ar-scope-radio">
                <input
                  type="radio"
                  name="ar-scope"
                  checked={scope === 'specific'}
                  onChange={() => handleScopeChange('specific')}
                />
                <div className="ar-radio-mark" />
                <div className="ar-radio-content">
                  <div className="ar-radio-title">Конкретные артикулы</div>
                  <div className="ar-radio-desc">Только для выбранных товаров (идеально для тестового запуска)</div>
                </div>
              </label>
            </div>
            {scope === 'specific' && (
              <div className="ar-nm-wrap">
                <input
                  type="text"
                  className="ar-nm-input"
                  placeholder="Введите артикул и нажмите Enter"
                  value={nmText}
                  onChange={(e) => handleNmTextChange(e.target.value)}
                  onKeyDown={handleNmKeyDown}
                  onBlur={commitNmInput}
                />
                <div className="ar-nm-hint">Укажите 1-3 артикула для пилотного запуска</div>
                {(aiSettings.auto_response_nm_ids || []).length > 0 && (
                  <div className="ar-nm-tags">
                    {aiSettings.auto_response_nm_ids.map((nm) => (
                      <span key={nm} className="ar-nm-tag">
                        {nm}
                        <span className="ar-nm-tag-remove" onClick={() => removeNmId(nm)}>&times;</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Channels */}
          <div className="ar-section-block">
            <div className="ar-section-label">Каналы</div>
            <div className="ar-channel-grid">
              {(['review', 'question', 'chat'] as AutoResponseChannel[]).map((ch) => {
                const isChecked = channels.includes(ch);
                const labels: Record<string, string> = { review: 'Отзывы', question: 'Вопросы', chat: 'Чаты' };
                return (
                  <label
                    key={ch}
                    className={`ar-channel-check ${isChecked ? 'checked' : ''}`}
                    onClick={() => toggleChannel(ch)}
                  >
                    <input type="checkbox" checked={isChecked} readOnly />
                    <span className="ar-check-mark" />
                    <span className="ar-check-label">{labels[ch]}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Presets */}
          {presets.length > 0 && (
            <div className="ar-section-block">
              <div className="ar-section-label">Быстрая настройка</div>
              <div className="ar-preset-grid">
                {presets.map((p, i) => (
                  <div
                    key={p.name}
                    className={`ar-preset-card ${activePreset === p.name ? 'active' : ''}`}
                    onClick={() => !applyingPreset && handleApplyPreset(p.name)}
                  >
                    <div className="ar-preset-icon">{PRESET_ICONS[p.name] || '\u2699'}</div>
                    <div className="ar-preset-name">{p.label}</div>
                    <div className="ar-preset-desc">{p.description}</div>
                    {i === 0 && <div className="ar-preset-badge">Рекомендуем</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Scenarios */}
          <div className="ar-section-block">
            <div className="ar-section-label">
              Сценарии <span className="ar-section-label-sub">&mdash; тонкая настройка</span>
            </div>
            <div className="ar-scenario-grid">
              {/* Auto-eligible scenarios + promo after thanks */}
              {AUTO_SCENARIO_ORDER.flatMap((intent) => {
                const sc = scenarios[intent];
                if (!sc) return [];
                const info = INTENT_LABELS[intent];
                if (!info) return [];
                const isEnabled = sc.enabled;
                const row = (
                  <div
                    key={intent}
                    className={`ar-scenario-row ${isEnabled ? '' : 'disabled'}`}
                    onClick={() => toggleScenario(intent)}
                  >
                    <div className={`ar-scenario-check ${isEnabled ? 'checked' : ''}`} />
                    <div className="ar-scenario-info">
                      <div className="ar-scenario-name">{info.name}</div>
                      <div className="ar-scenario-desc">{info.desc}</div>
                      <div className="ar-scenario-channels">
                        {(sc.channels || []).map((ch) => (
                          <span key={ch} className="ar-ch-tag">{CHANNEL_TAG_LABELS[ch] || ch}</span>
                        ))}
                      </div>
                    </div>
                    <div className={`ar-scenario-badge ${isEnabled ? 'auto' : 'draft'}`}>
                      {isEnabled ? 'АВТО' : 'ЧЕРНОВИК'}
                    </div>
                  </div>
                );

                // Insert promo row right after thanks (matches prototype order)
                if (intent === 'thanks') {
                  const promoEnabled = aiSettings.auto_response_promo_on_5star;
                  return [row, (
                    <div
                      key="promo"
                      className={`ar-scenario-row ${promoEnabled ? '' : 'disabled'}`}
                      onClick={togglePromo}
                    >
                      <div className={`ar-scenario-check ${promoEnabled ? 'checked' : ''}`} />
                      <div className="ar-scenario-info">
                        <div className="ar-scenario-name">Промокод за 5★</div>
                        <div className="ar-scenario-desc">
                          Благодарность + промокод из <a href="#" className="ar-promo-link">Настройки → Промокоды</a>.{' '}
                          <strong className="ar-promo-warn">Ответ на отзыв публичный</strong>{' '}
                          &mdash; промокод увидят все посетители карточки
                        </div>
                        <div className="ar-scenario-channels">
                          <span className="ar-ch-tag">отзывы</span>
                        </div>
                      </div>
                      <div className={`ar-scenario-badge ${promoEnabled ? 'auto' : 'draft'}`}>
                        {promoEnabled ? 'АВТО' : 'ЧЕРНОВИК'}
                      </div>
                    </div>
                  )];
                }

                return [row];
              })}

              {/* Separator */}
              <div className="ar-scenario-separator">
                <span>Не обрабатываются автоматически</span>
              </div>

              {/* Blocked scenarios */}
              {BLOCK_SCENARIO_ORDER.map((intent) => {
                const sc = scenarios[intent];
                if (!sc) return null;
                const info = BLOCK_INFO[intent];
                if (!info) return null;
                return (
                  <div key={intent} className="ar-scenario-row review-row">
                    <div className="ar-scenario-info">
                      <div className="ar-scenario-name">{info.name}</div>
                      <div className="ar-scenario-desc">{info.desc}</div>
                      <div className="ar-scenario-channels">
                        {(sc.channels || []).map((ch) => (
                          <span key={ch} className="ar-ch-tag">{CHANNEL_TAG_LABELS[ch] || ch}</span>
                        ))}
                      </div>
                    </div>
                    <div className="ar-scenario-badge blocked">БЛОК</div>
                  </div>
                );
              })}
            </div>

            {/* State legend */}
            <div className="ar-state-row">
              <div className="ar-state-item"><div className="ar-state-dot green" /> АВТО &mdash; отправляется автоматически</div>
              <div className="ar-state-item"><div className="ar-state-dot yellow" /> ЧЕРНОВИК &mdash; AI готовит ответ, вы решаете</div>
              <div className="ar-state-item"><div className="ar-state-dot red" /> БЛОК &mdash; только вручную, авто-ответ не отправляется</div>
            </div>
          </div>

          {/* Safety notice */}
          <div className="ar-section-block">
            <div className="ar-safety-notice">
              <div className="ar-safety-icon">{'\u26A0\uFE0F'}</div>
              <div className="ar-safety-text">
                <strong>Безопасность:</strong> Негативные отзывы (1-3★) никогда не получают авто-ответ.
                Каждый текст перед отправкой проверяется &mdash; запрещённые фразы, обещания возвратов,
                упоминания AI блокируются автоматически. Пауза между ответами делает паттерн естественным.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
