import { useEffect, useMemo, useState } from 'react';
import { FolderStrip } from './FolderStrip';
import type { Chat, ChatFilters, InteractionQualityMetricsResponse } from '../types';

interface ChatListProps {
  chats: Chat[];
  selectedChatId: number | null;
  onSelectChat: (chat: Chat) => void;
  onFiltersChange: (filters: ChatFilters) => void;
  pipeline?: InteractionQualityMetricsResponse['pipeline'] | null;
  activeChannel: 'all' | 'review' | 'question' | 'chat';
  onChannelChange: (channel: 'all' | 'review' | 'question' | 'chat') => void;
  userName?: string;
  onLogout?: () => void;
  onConnectMarketplace?: (apiKey: string) => Promise<void>;
  isConnecting?: boolean;
  isLoadingChats?: boolean;
  hasApiCredentials?: boolean;
  syncStatus?: 'idle' | 'syncing' | 'success' | 'error' | null;
  syncError?: string | null;
  lastSyncAt?: string | null;
  onRetrySync?: () => Promise<void>;
  isRetryingSync?: boolean;
  isConnectionSkipped?: boolean;
  onOpenConnectOnboarding?: () => void;
  loadingProgress?: { loaded: number; total: number } | null;
}

export function ChatList({
  chats,
  selectedChatId,
  onSelectChat,
  onFiltersChange,
  pipeline,
  activeChannel,
  onChannelChange,
  userName,
  onLogout,
  onConnectMarketplace,
  isConnecting,
  isLoadingChats,
  hasApiCredentials,
  syncStatus,
  syncError,
  lastSyncAt,
  onRetrySync,
  isRetryingSync,
  isConnectionSkipped,
  onOpenConnectOnboarding,
  loadingProgress,
}: ChatListProps) {
  const [activeFilter, setActiveFilter] = useState<'all' | 'urgent' | 'unanswered' | 'resolved'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showApiKeyForm, setShowApiKeyForm] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiKeyError, setApiKeyError] = useState('');

  const channelScopedChats = useMemo(() => {
    if (activeChannel === 'all') {
      return chats;
    }
    return chats.filter((chat) => chat.channel_type === activeChannel);
  }, [chats, activeChannel]);

  const pipelineByChannel = useMemo(() => {
    const map: Record<string, { total: number; needs: number; responded: number }> = {};
    if (!pipeline || !Array.isArray(pipeline.by_channel)) return map;
    for (const item of pipeline.by_channel) {
      const channel = typeof item.channel === 'string' ? item.channel : 'unknown';
      map[channel] = {
        total: Number(item.interactions_total || 0),
        needs: Number(item.needs_response_total || 0),
        responded: Number(item.responded_total || 0),
      };
    }
    return map;
  }, [pipeline]);

  const scopedPipelineCounts = useMemo(() => {
    if (!pipeline) return null;
    if (activeChannel === 'all') {
      return {
        total: Number(pipeline.interactions_total || 0),
        needs: Number(pipeline.needs_response_total || 0),
        responded: Number(pipeline.responded_total || 0),
      };
    }
    const item = pipelineByChannel[activeChannel];
    return item
      ? { total: item.total, needs: item.needs, responded: item.responded }
      : null;
  }, [pipeline, pipelineByChannel, activeChannel]);

  const isSlaOverdue = (chat: Chat) => {
    if (!chat.sla_deadline_at) return false;
    if (chat.chat_status === 'responded' || chat.chat_status === 'auto-response' || chat.chat_status === 'closed') {
      return false;
    }
    const deadline = new Date(chat.sla_deadline_at);
    if (Number.isNaN(deadline.getTime())) return false;
    return deadline.getTime() < Date.now();
  };

  // Filter chats based on active filter
  const filteredChats = useMemo(() => {
    let filtered = channelScopedChats;

    if (activeFilter === 'unanswered') {
      filtered = filtered.filter(chat => chat.unread_count > 0);
    } else if (activeFilter === 'urgent') {
      filtered = filtered.filter(chat =>
        chat.sla_priority === 'urgent' ||
        chat.sla_priority === 'high' ||
        isSlaOverdue(chat)
      );
    } else if (activeFilter === 'resolved') {
      filtered = filtered.filter(chat =>
        chat.chat_status === 'responded' ||
        chat.chat_status === 'auto-response' ||
        chat.chat_status === 'closed'
      );
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(chat =>
        chat.customer_name?.toLowerCase().includes(query) ||
        chat.marketplace_chat_id.toLowerCase().includes(query) ||
        chat.order_id?.toLowerCase().includes(query) ||
        chat.product_name?.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [channelScopedChats, activeFilter, searchQuery]);

  useEffect(() => {
    const filters: ChatFilters = {};
    const normalizedQuery = searchQuery.trim();
    if (activeFilter === 'unanswered') filters.has_unread = true;
    if (normalizedQuery) filters.search = normalizedQuery;
    if (activeChannel !== 'all') filters.channel = activeChannel;
    onFiltersChange(filters);
  }, [activeFilter, activeChannel, onFiltersChange, searchQuery]);

  // Group chats into 3 queues matching prototype:
  // 1. "В работе" — only urgent priority (red dot risk)
  // 2. "Ожидают ответа" — waiting/client-replied (not urgent)
  // 3. "Все сообщения" — responded/auto-response
  const inWorkChats = filteredChats.filter(c =>
    (c.sla_priority === 'urgent' || isSlaOverdue(c)) &&
    c.chat_status !== 'responded' &&
    c.chat_status !== 'auto-response' &&
    c.chat_status !== 'closed'
  );
  const waitingChats = filteredChats.filter(c =>
    c.sla_priority !== 'urgent' &&
    !isSlaOverdue(c) &&
    (c.chat_status === 'waiting' || c.chat_status === 'client-replied')
  );
  const allMessagesChats = filteredChats.filter(c =>
    c.chat_status === 'responded' ||
    c.chat_status === 'auto-response' ||
    c.chat_status === 'closed'
  );

  // Handle filter change
  const handleFilterChange = (filter: 'all' | 'urgent' | 'unanswered' | 'resolved') => {
    setActiveFilter(filter);
  };

  const handleChannelChange = (channel: 'all' | 'review' | 'question' | 'chat') => {
    onChannelChange(channel);
  };

  // Handle search
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
  };

  // Get time string
  const getTimeString = (dateString: string | null) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diff = now.getTime() - date.getTime();
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));

      if (days === 0) {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      } else if (days < 7) {
        return `${days}д`;
      } else {
        return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
      }
    } catch {
      return '';
    }
  };

  // Get status dot classes based on chat_status and priority
  const getStatusDotClass = (chat: Chat) => {
    const isUrgent = chat.sla_priority === 'urgent';
    const isOverdue = isSlaOverdue(chat);
    const chatStatus = chat.chat_status || 'waiting';

    if (isOverdue && (chatStatus === 'waiting' || chatStatus === 'client-replied')) return 'status-dot waiting risk';
    if (chatStatus === 'waiting' && isUrgent) return 'status-dot waiting risk';
    if (chatStatus === 'waiting') return 'status-dot waiting';
    if (chatStatus === 'client-replied') return 'status-dot client-replied';
    if (chatStatus === 'responded') return 'status-dot responded';
    if (chatStatus === 'auto-response') return 'status-dot auto-response';
    return 'status-dot responded';
  };

  // Get status text for meta line
  const getStatusText = (chat: Chat) => {
    const chatStatus = chat.chat_status || 'waiting';
    if (isSlaOverdue(chat)) return 'SLA просрочен';
    if (chatStatus === 'waiting') return 'Ожидает ответа';
    if (chatStatus === 'client-replied') return 'Клиент ответил';
    if (chatStatus === 'responded') return 'Отвечено';
    if (chatStatus === 'auto-response') return 'Авто-ответ';
    return '';
  };

  // Build meta text: "Чат · ProductName · StatusText"
  const getMetaText = (chat: Chat) => {
    const channelLabel = chat.channel_type === 'review'
      ? 'Отзыв'
      : chat.channel_type === 'question'
      ? 'Вопрос'
      : 'Чат';
    const parts = [channelLabel];
    if (chat.product_name) parts.push(chat.product_name);
    const statusText = getStatusText(chat);
    if (statusText) parts.push(statusText);
    return parts.join(' · ');
  };

  // Get preview: use last_message_preview from backend
  const getPreview = (chat: Chat) => {
    return chat.last_message_preview || '';
  };

  // Render chat item
  const renderChatItem = (chat: Chat) => {
    const isActive = selectedChatId === chat.id;
    const isUrgent = chat.sla_priority === 'urgent';
    const hasUnread = chat.unread_count > 0;

    return (
      <div
        key={chat.id}
        className={`chat-item ${isUrgent ? 'urgent' : ''} ${isActive ? 'active' : ''}`}
        draggable="true"
        data-chat-id={chat.id}
        data-status={chat.chat_status || 'waiting'}
        onClick={() => onSelectChat(chat)}
      >
        <div className="marketplace-icon wb">W</div>
        <div className="chat-item-content">
          <div className="chat-item-header">
            <span className="chat-item-name">{chat.customer_name || 'Клиент'}</span>
            {hasUnread && <span className="unread-badge">{chat.unread_count}</span>}
            <span className="chat-item-time">{getTimeString(chat.last_message_at)}</span>
          </div>
          <div className="chat-item-meta">
            <span className={getStatusDotClass(chat)}></span>
            {getMetaText(chat)}
          </div>
          <div className="chat-item-preview">{getPreview(chat)}</div>
        </div>
      </div>
    );
  };

  const unreadCount = scopedPipelineCounts ? scopedPipelineCounts.needs : channelScopedChats.filter(c => c.unread_count > 0).length;
  const urgentCount = channelScopedChats.filter(c => c.sla_priority === 'urgent' || isSlaOverdue(c)).length;
  const resolvedCount = scopedPipelineCounts
    ? scopedPipelineCounts.responded
    : channelScopedChats.filter(c =>
        c.chat_status === 'responded' ||
        c.chat_status === 'auto-response' ||
        c.chat_status === 'closed'
      ).length;
  const activeChannelLabel = activeChannel === 'review'
    ? 'Отзывы'
    : activeChannel === 'question'
    ? 'Вопросы'
    : activeChannel === 'chat'
    ? 'Чаты'
    : 'Все каналы';
  const allCount = scopedPipelineCounts ? scopedPipelineCounts.total : channelScopedChats.length;

  return (
    <section className="chat-list">
      <div className="chat-list-header">
        <div className="chat-list-title-row">
          <h1 className="chat-list-title">Сообщения</h1>
          {userName && (
            <div className="user-menu">
              <span className="user-name">{userName}</span>
              {onLogout && (
                <button className="logout-btn" onClick={onLogout} title="Выйти">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="14" height="14">
                    <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3M11 11l3-3-3-3M6 8h8"/>
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Channel tabs (mobile only — desktop uses FolderStrip.desktop beside chat-list) */}
        <FolderStrip
          variant="mobile"
          activeChannel={activeChannel}
          onChannelChange={handleChannelChange}
          pipeline={pipeline}
          totalChats={chats.length}
        />

        {/* Search */}
        <div className="search-wrapper">
          <input
            type="text"
            className="search-box"
            placeholder="Поиск..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
          <button
            className="filter-icon-btn"
            title="Расширенные фильтры"
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="14" height="14">
              <path d="M2 3h12M4 6h8M6 9h4M7 12h2"/>
            </svg>
          </button>
        </div>

        {hasApiCredentials && (syncStatus === 'syncing' || syncStatus === 'error') && (
          <div className={`sync-banner ${syncStatus}`}>
            <div className="sync-banner-main">
              {syncStatus === 'syncing' ? (
                <>
                  <span className="sync-spinner"></span>
                  <span>Синхронизация данных в процессе...</span>
                </>
              ) : (
                <>
                  <span className="sync-banner-dot"></span>
                  <span>{syncError || 'Синхронизация завершилась с ошибкой'}</span>
                </>
              )}
            </div>
            {syncStatus === 'error' && onRetrySync && (
              <button
                className="sync-retry-btn"
                onClick={() => onRetrySync()}
                disabled={Boolean(isRetryingSync)}
              >
                {isRetryingSync ? '...' : 'Повторить'}
              </button>
            )}
          </div>
        )}

        {/* Pills Filters */}
        <div className="filters-container">
          <div className="filters-scroll">
            <button
              className={`filter-pill ${activeFilter === 'all' ? 'active' : ''}`}
              onClick={() => handleFilterChange('all')}
            >
              Все <span className="count">{allCount}</span>
            </button>
            <button
              className={`filter-pill ${activeFilter === 'urgent' ? 'active' : ''}`}
              onClick={() => handleFilterChange('urgent')}
            >
              Срочно <span className="count">{urgentCount}</span>
            </button>
            <button
              className={`filter-pill ${activeFilter === 'unanswered' ? 'active' : ''}`}
              onClick={() => handleFilterChange('unanswered')}
            >
              Без ответа <span className="count">{unreadCount}</span>
            </button>
            <button
              className={`filter-pill ${activeFilter === 'resolved' ? 'active' : ''}`}
              onClick={() => handleFilterChange('resolved')}
            >
              Обработаны <span className="count">{resolvedCount}</span>
            </button>
          </div>
        </div>

        {/* Advanced Filters */}
        {showAdvancedFilters && (
          <div className="advanced-filters">
            <div className="filter-group">
              <div className="filter-group-label">Период</div>
              <div className="date-range-compact">
                <input type="date" className="date-input-compact" />
                <span className="date-separator">—</span>
                <input type="date" className="date-input-compact" />
              </div>
            </div>

            <div className="filter-group">
              <div className="filter-group-label">Платформа</div>
              <div className="platform-chips">
                <button className="platform-chip active" data-platform="wb">WB</button>
              </div>
            </div>

            <div className="filter-actions">
              <button className="btn-clear" onClick={() => setShowAdvancedFilters(false)}>Сбросить</button>
              <button className="btn-apply" onClick={() => setShowAdvancedFilters(false)}>Применить</button>
            </div>
          </div>
        )}
      </div>

      {/* Queues — 3 sections like prototype */}
      <div className="chat-list-content">
        {isLoadingChats ? (
          /* Loading state - show spinner while fetching chats */
          <div className="empty-state">
            <div className="empty-state-icon syncing">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" width="48" height="48">
                <path d="M24 8v8M24 32v8M8 24h8M32 24h8M12.7 12.7l5.6 5.6M29.7 29.7l5.6 5.6M12.7 35.3l5.6-5.6M29.7 18.3l5.6-5.6" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="empty-state-title">Загрузка чатов...</div>
          </div>
        ) : chats.length === 0 && activeFilter === 'all' && activeChannel === 'all' && !searchQuery ? (
          /* No chats at all — show connection/sync empty state */
          <div className="empty-state">
            {hasApiCredentials ? (
              syncStatus === 'error' ? (
                <>
                  <div className="empty-state-icon error">
                    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" width="48" height="48">
                      <circle cx="24" cy="24" r="20"/>
                      <path d="M24 14v12M24 32v2" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div className="empty-state-title">Ошибка синхронизации</div>
                  <div className="empty-state-text">
                    {syncError || 'Не удалось загрузить чаты. Проверьте API-ключ.'}
                  </div>
                  <button className="empty-state-btn" onClick={() => setShowApiKeyForm(true)}>
                    Изменить API-ключ
                  </button>
                  {onRetrySync && (
                    <button
                      className="btn-secondary"
                      onClick={() => onRetrySync()}
                      disabled={Boolean(isRetryingSync)}
                    >
                      {isRetryingSync ? 'Повтор...' : 'Повторить синк'}
                    </button>
                  )}
                </>
              ) : syncStatus === 'success' && lastSyncAt ? (
                <>
                  <div className="empty-state-icon success">
                    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" width="48" height="48">
                      <circle cx="24" cy="24" r="20"/>
                      <path d="M16 24l6 6 12-12" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div className="empty-state-title">Обращений пока нет</div>
                  <div className="empty-state-text">
                    Wildberries подключён. Когда покупатели напишут — чаты появятся здесь.
                  </div>
                  <div className="sync-status success">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M4 8l3 3 5-5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>Синхронизировано</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="empty-state-icon syncing">
                    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" width="48" height="48">
                      <path d="M24 8v8M24 32v8M8 24h8M32 24h8M12.7 12.7l5.6 5.6M29.7 29.7l5.6 5.6M12.7 35.3l5.6-5.6M29.7 18.3l5.6-5.6" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div className="empty-state-title">Wildberries подключён</div>
                  <div className="empty-state-text">
                    Синхронизация чатов... Это может занять несколько минут при первом подключении.
                  </div>
                  <div className="sync-status">
                    <div className="sync-spinner"></div>
                    <span>Загрузка чатов из Wildberries</span>
                  </div>
                </>
              )
            ) : !showApiKeyForm ? (
              <>
                <div className="empty-state-icon">
                  <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                    <rect x="6" y="10" width="36" height="28" rx="3"/>
                    <path d="M6 18h36M14 26h12M14 32h8"/>
                  </svg>
                </div>
                <div className="empty-state-title">Обращений пока нет</div>
                <div className="empty-state-text">
                  {isConnectionSkipped
                    ? 'Демо-режим активирован. Подключите Wildberries, когда будете готовы к реальным данным.'
                    : 'Подключите кабинет Wildberries, чтобы видеть сообщения покупателей'}
                </div>
                {onOpenConnectOnboarding ? (
                  <button className="empty-state-btn" onClick={onOpenConnectOnboarding}>
                    Подключить Wildberries
                  </button>
                ) : (
                  <button className="empty-state-btn" onClick={() => setShowApiKeyForm(true)}>
                    Подключить Wildberries
                  </button>
                )}
              </>
            ) : (
              <div className="api-key-form">
                <div className="empty-state-title">Подключение Wildberries</div>
                <div className="empty-state-text" style={{ marginBottom: '16px' }}>
                  Введите API-ключ из личного кабинета WB
                </div>
                <input
                  type="text"
                  className="api-key-input"
                  placeholder="API-ключ Wildberries"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setApiKeyError('');
                  }}
                  disabled={isConnecting}
                />
                {apiKeyError && <div className="api-key-error">{apiKeyError}</div>}
                <div className="api-key-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      setShowApiKeyForm(false);
                      setApiKey('');
                      setApiKeyError('');
                    }}
                    disabled={isConnecting}
                  >
                    Отмена
                  </button>
                  <button
                    className="empty-state-btn"
                    onClick={async () => {
                      if (!apiKey || apiKey.length < 10) {
                        setApiKeyError('Введите корректный API-ключ');
                        return;
                      }
                      if (onConnectMarketplace) {
                        try {
                          await onConnectMarketplace(apiKey);
                          setShowApiKeyForm(false);
                          setApiKey('');
                        } catch {
                          setApiKeyError('Не удалось подключить. Проверьте ключ.');
                        }
                      }
                    }}
                    disabled={isConnecting || !apiKey}
                  >
                    {isConnecting ? 'Подключение...' : 'Подключить'}
                  </button>
                </div>
                <div className="api-key-hint">
                  <a href="https://seller.wildberries.ru/supplier-settings/access-to-api" target="_blank" rel="noopener noreferrer">
                    Где взять API-ключ?
                  </a>
                </div>
              </div>
            )}
          </div>
        ) : filteredChats.length === 0 ? (
          /* Has data but none match current filter */
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                <circle cx="20" cy="20" r="14"/>
                <path d="M30 30l10 10" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="empty-state-title">
              Нет обращений по фильтру
            </div>
            <div className="empty-state-text">
              {activeFilter === 'urgent' && 'Нет срочных чатов — все под контролем'}
              {activeFilter === 'unanswered' && 'Нет чатов без ответа — отличная работа'}
              {activeFilter === 'resolved' && 'Нет обработанных обращений'}
              {activeFilter === 'all' && activeChannel !== 'all' && `В канале "${activeChannelLabel}" пока нет данных`}
            </div>
            <button className="empty-state-btn" onClick={() => handleFilterChange('all')}>
              Показать все обращения
            </button>
          </div>
        ) : (
          <>
            {inWorkChats.length > 0 && (
              <div className="queue-section">
                <div className="queue-header">
                  <div className="queue-label">В работе</div>
                  <div className="queue-count">{inWorkChats.length}</div>
                </div>
                {inWorkChats.map(renderChatItem)}
              </div>
            )}

            {waitingChats.length > 0 && (
              <div className="queue-section">
                <div className="queue-header">
                  <div className="queue-label">Ожидают ответа</div>
                  <div className="queue-count">{waitingChats.length}</div>
                </div>
                {waitingChats.map(renderChatItem)}
              </div>
            )}

            {allMessagesChats.length > 0 && (
              <div className="queue-section">
                <div className="queue-header">
                  <div className="queue-label">Все сообщения</div>
                  <div className="queue-count">{allMessagesChats.length}</div>
                </div>
                {allMessagesChats.map(renderChatItem)}
              </div>
            )}

            {/* Apple Mail–style sync banner at bottom */}
            {loadingProgress && loadingProgress.loaded < loadingProgress.total && (
              <div className="chat-list-sync-banner">
                <div className="chat-list-sync-spinner"></div>
                <span>Загрузка... {loadingProgress.loaded} из ~{loadingProgress.total} чатов</span>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
