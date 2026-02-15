import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { ChatList } from './components/ChatList';
import { ChatWindow } from './components/ChatWindow';
import { FolderStrip } from './components/FolderStrip';
import { Login } from './components/Login';
import { MarketplaceOnboarding } from './components/MarketplaceOnboarding';
import { SettingsPage } from './components/SettingsPage';
import { authApi, chatApi, getToken, interactionsApi } from './services/api';
import { usePolling } from './hooks/usePolling';
import type {
  AIAnalysis,
  Chat,
  ChatFilters,
  Interaction,
  InteractionFilters,
  InteractionOpsAlertsResponse,
  InteractionPilotReadinessResponse,
  InteractionQualityHistoryResponse,
  InteractionQualityMetricsResponse,
  InteractionTimelineResponse,
  Message,
  User,
} from './types';

function parseAIAnalysis(jsonStr: string | null): AIAnalysis | null {
  if (!jsonStr) return null;
  try {
    const raw = JSON.parse(jsonStr);
    const categories = raw.categories || [];
    return {
      intent: raw.intent || (categories.length > 0 ? categories[0] : '—'),
      sentiment: typeof raw.sentiment === 'object'
        ? (raw.sentiment?.negative ? 'negative' : 'neutral')
        : (raw.sentiment || 'neutral'),
      sentimentLabel: typeof raw.sentiment === 'object'
        ? raw.sentiment?.label
        : null,
      urgency: typeof raw.urgency === 'object'
        ? (raw.urgency?.urgent ? 'high' : 'normal')
        : (raw.urgency || 'normal'),
      urgencyLabel: typeof raw.urgency === 'object'
        ? raw.urgency?.label
        : null,
      categories,
      recommendation: raw.recommendation || null,
      recommendation_reason: raw.recommendation_reason,
      needs_escalation: raw.needs_escalation || raw.urgency?.urgent || false,
      escalation_reason: raw.escalation_reason,
      sla_priority: raw.sla_priority || 'normal',
      analyzed_at: raw.analyzed_at || new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function getStringField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function getNumberField(record: Record<string, unknown>, key: string): number | null {
  const value = record[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function toSlaPriority(priority: string | null): Chat['sla_priority'] {
  if (priority === 'critical' || priority === 'urgent') return 'urgent';
  if (priority === 'high') return 'high';
  if (priority === 'low') return 'low';
  return 'normal';
}

function interactionToChat(interaction: Interaction): Chat {
  const extra = asRecord(interaction.extra_data);
  const draft = asRecord(extra.last_ai_draft);
  const draftText = getStringField(draft, 'text');
  const draftIntent = getStringField(draft, 'intent');
  const draftSentiment = getStringField(draft, 'sentiment');
  const draftPriority = getStringField(draft, 'sla_priority');
  const slaDueAt = getStringField(extra, 'sla_due_at');
  const productName = (() => {
    // Chats: extra_data has clean product_name (subject is composite "Чат с покупателем · Customer · Product")
    if (interaction.channel === 'chat') {
      return getStringField(extra, 'product_name') || null;
    }
    // Reviews/questions: subject has prefix "Отзыв X★ · " / "Вопрос по товару · " — strip it
    const subj = interaction.subject || '';
    const stripped = subj
      .replace(/^Отзыв\s+\d★?\s*·\s*/, '')
      .replace(/^Вопрос по товару\s*·\s*/, '');
    if (stripped) return stripped;
    return interaction.nm_id ? `Арт. ${interaction.nm_id}` : null;
  })();
  const customerName = getStringField(extra, 'user_name')
    || getStringField(extra, 'customer_name')
    || interaction.customer_id
    || 'Покупатель';

  const analysisJson = draftText
    ? JSON.stringify({
        intent: draftIntent || interaction.channel,
        sentiment: draftSentiment || 'neutral',
        urgency: draftPriority || interaction.priority,
        categories: [interaction.channel],
        recommendation: draftText,
        recommendation_reason: getStringField(draft, 'recommendation_reason'),
        needs_escalation: (draftPriority || interaction.priority) === 'high',
        sla_priority: draftPriority || interaction.priority,
        analyzed_at: new Date().toISOString(),
      })
    : null;

  return {
    id: interaction.id,
    seller_id: interaction.seller_id,
    marketplace: interaction.marketplace,
    channel_type: interaction.channel,
    marketplace_chat_id: interaction.external_id,
    order_id: interaction.order_id,
    product_id: interaction.nm_id,
    customer_name: customerName,
    customer_id: interaction.customer_id,
    status: interaction.status,
    unread_count: interaction.needs_response ? 1 : 0,
    last_message_at: interaction.occurred_at || interaction.updated_at,
    first_message_at: interaction.occurred_at || interaction.created_at,
    sla_deadline_at: slaDueAt,
    sla_priority: toSlaPriority(interaction.priority),
    ai_suggestion_text: draftText,
    ai_analysis_json: analysisJson,
    last_message_preview: (() => {
      const text = typeof interaction.text === 'string' ? interaction.text.trim() : '';
      if (text) return text;
      if (interaction.channel === 'review' && typeof interaction.rating === 'number') {
        return `(только оценка: ${interaction.rating}★)`;
      }
      return interaction.subject;
    })(),
    product_name: productName,
    product_article: interaction.product_article || interaction.nm_id,
    chat_status: (() => {
      if (interaction.status === 'closed') return 'closed';
      // For chats: use backend-canonical chat_status from extra_data
      const backendStatus = getStringField(extra, 'chat_status');
      if (backendStatus && ['waiting', 'responded', 'client-replied', 'auto-response', 'closed'].includes(backendStatus)) {
        return backendStatus;
      }
      // For reviews/questions: derive from reply presence + needs_response
      const hasReply = Boolean(getStringField(extra, 'last_reply_text'));
      const isAutoResponse = Boolean(extra.is_auto_response);
      if (isAutoResponse) return 'auto-response';
      if (hasReply && !interaction.needs_response) return 'responded';
      if (hasReply && interaction.needs_response) return 'client-replied';
      // Answered but no reply text (e.g. WB isAnswered=true with empty answerText)
      if (!interaction.needs_response) return 'responded';
      return 'waiting';
    })(),
    closed_at: interaction.status === 'closed' ? interaction.updated_at : null,
    source: interaction.source || null,
    created_at: interaction.created_at,
    updated_at: interaction.updated_at,
  };
}

function buildMessagesFromInteraction(interaction: Interaction): Message[] {
  const extra = asRecord(interaction.extra_data);
  const replyText = getStringField(extra, 'last_reply_text');
  const incomingSentAt = interaction.occurred_at || interaction.created_at || new Date().toISOString();
  const incomingText = (() => {
    const text = typeof interaction.text === 'string' ? interaction.text.trim() : '';
    if (text) return text;
    if (interaction.channel === 'review' && typeof interaction.rating === 'number') {
      return `Отзыв без текста (только оценка: ${interaction.rating}★)`;
    }
    return interaction.subject || 'Сообщение отсутствует';
  })();

  const incoming: Message = {
    id: interaction.id * 1000 + 1,
    chat_id: interaction.id,
    external_message_id: `interaction_${interaction.id}_incoming`,
    direction: 'incoming',
    text: incomingText,
    attachments: null,
    author_type: 'customer',
    author_id: interaction.customer_id,
    status: 'sent',
    is_read: true,
    read_at: incomingSentAt,
    sent_at: incomingSentAt,
    created_at: incomingSentAt,
  };

  if (!replyText) {
    return [incoming];
  }

  const outgoingSentAt = interaction.updated_at || new Date().toISOString();
  const outgoing: Message = {
    id: interaction.id * 1000 + 2,
    chat_id: interaction.id,
    external_message_id: `interaction_${interaction.id}_outgoing`,
    direction: 'outgoing',
    text: replyText,
    attachments: null,
    author_type: 'seller',
    author_id: null,
    status: 'sent',
    is_read: true,
    read_at: outgoingSentAt,
    sent_at: outgoingSentAt,
    created_at: outgoingSentAt,
  };

  return [incoming, outgoing];
}

function buildInteractionFilters(filters: ChatFilters) {
  const params: InteractionFilters = {};
  if (filters.channel) params.channel = filters.channel;
  if (filters.search) params.search = filters.search;
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  if (filters.sla_priority) params.priority = filters.sla_priority;
  if (filters.status) params.status = filters.status;
  if (filters.has_unread) params.needs_response = true;
  return params;
}

type LinkCandidateView = {
  channel: string;
  externalId: string | null;
  confidence: number;
  explanation: string | null;
  reasoningSignals: string[];
};

const SKIP_CONNECT_STORAGE_KEY = 'agentiq_connect_skipped';
const INTERACTIONS_CACHE_KEY = 'agentiq_interactions_cache';
const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes

function saveInteractionsToCache(channelKey: string, interactions: Interaction[], allLoaded?: boolean) {
  try {
    const existing = JSON.parse(sessionStorage.getItem(INTERACTIONS_CACHE_KEY) || '{}');
    existing[channelKey] = { ts: Date.now(), items: interactions, allLoaded: !!allLoaded };
    sessionStorage.setItem(INTERACTIONS_CACHE_KEY, JSON.stringify(existing));
  } catch { /* quota exceeded or serialization error, ignore */ }
}

function loadInteractionsFromCache(channelKey: string): { items: Interaction[]; allLoaded: boolean } | null {
  try {
    const cache = JSON.parse(sessionStorage.getItem(INTERACTIONS_CACHE_KEY) || '{}');
    const entry = cache[channelKey];
    if (entry && Date.now() - entry.ts < CACHE_TTL_MS) {
      return { items: entry.items, allLoaded: !!entry.allLoaded };
    }
  } catch { /* corrupted cache, ignore */ }
  return null;
}

function clearInteractionsCache() {
  try {
    sessionStorage.removeItem(INTERACTIONS_CACHE_KEY);
  } catch { /* ignore */ }
}

function normalizeConfidence(raw: unknown): number {
  if (typeof raw !== 'number' || Number.isNaN(raw)) return 0;
  if (raw > 1) return Math.max(0, Math.min(1, raw / 100));
  return Math.max(0, Math.min(1, raw));
}

function confidenceTier(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.85) return 'high';
  if (confidence >= 0.65) return 'medium';
  return 'low';
}

function extractLinkCandidates(interaction: Interaction | null): LinkCandidateView[] {
  if (!interaction) return [];
  const extra = asRecord(interaction.extra_data);
  const rawCandidates = extra.link_candidates;
  if (!Array.isArray(rawCandidates)) return [];

  const candidates: LinkCandidateView[] = [];
  for (const item of rawCandidates) {
    const record = asRecord(item);
    const confidence = normalizeConfidence(record.confidence);
    const channel = getStringField(record, 'channel') || 'unknown';
    const externalId = getStringField(record, 'external_id');
    const explanation = getStringField(record, 'explanation');
    const rawSignals = record.reasoning_signals;
    const reasoningSignals = Array.isArray(rawSignals)
      ? rawSignals.filter((signal): signal is string => typeof signal === 'string' && signal.trim().length > 0)
      : [];

    candidates.push({
      channel,
      externalId,
      confidence,
      explanation,
      reasoningSignals,
    });
  }

  return candidates.sort((a, b) => b.confidence - a.confidence);
}

function formatRate(rate: number | undefined): string {
  if (typeof rate !== 'number' || Number.isNaN(rate)) return '0%';
  return `${Math.round(rate * 100)}%`;
}

function normalizeIntegerInput(raw: string, fallback: number, min: number, max: number): number {
  const parsed = Number.parseInt(raw.trim(), 10);
  if (Number.isNaN(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [activeWorkspace, setActiveWorkspace] = useState<'messages' | 'analytics' | 'settings' | 'dashboard'>(() => {
    try {
      const saved = sessionStorage.getItem('agentiq_workspace');
      if (saved === 'messages' || saved === 'analytics' || saved === 'settings' || saved === 'dashboard') return saved;
    } catch { /* ignore */ }
    return 'messages';
  });
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [dismissedSyncOnboarding, setDismissedSyncOnboarding] = useState(false);
  const [connectionSkipped, setConnectionSkipped] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SKIP_CONNECT_STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });
  const [selectedInteractionId, setSelectedInteractionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [filters, setFilters] = useState<ChatFilters>({});
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isLoadingQuality, setIsLoadingQuality] = useState(false);
  const [isLoadingQualityHistory, setIsLoadingQualityHistory] = useState(false);
  const [isLoadingOpsAlerts, setIsLoadingOpsAlerts] = useState(false);
  const [isLoadingPilotReadiness, setIsLoadingPilotReadiness] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isRetryingSync, setIsRetryingSync] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'chat' | 'context'>('list');
  const [activeChannel, setActiveChannelRaw] = useState<'all' | 'review' | 'question' | 'chat'>('all');
  const [interactionCache, setInteractionCache] = useState<Record<string, Interaction[]>>({});
  // Progressive loading state
  const [syncLoadedCount, setSyncLoadedCount] = useState(0);
  const [syncAutoTransitioned, setSyncAutoTransitioned] = useState(false);
  const [paginationMeta, setPaginationMeta] = useState<Record<string, {
    total: number; loadedPages: number; isLoadingMore: boolean; allLoaded: boolean;
  }>>({});
  const interactionCacheRef = useRef(interactionCache);
  interactionCacheRef.current = interactionCache;
  const cacheRestoredRef = useRef(false);
  const interactions = interactionCache[activeChannel] || [];
  const handleChannelChange = useCallback((channel: 'all' | 'review' | 'question' | 'chat') => {
    setActiveChannelRaw(channel);
    const hasCachedData = (interactionCacheRef.current[channel]?.length ?? 0) > 0;
    if (!hasCachedData && channel !== 'all') {
      // Pre-populate from 'all' cache by filtering client-side
      const allCache = interactionCacheRef.current['all'] || [];
      const filtered = allCache.filter(i => i.channel === channel);
      if (filtered.length > 0) {
        setInteractionCache(prev => ({ ...prev, [channel]: filtered }));
        setIsLoadingChats(false);
      } else {
        // Try sessionStorage cache before showing spinner
        const sessionCached = loadInteractionsFromCache(channel);
        if (sessionCached && sessionCached.items.length > 0) {
          setInteractionCache(prev => ({ ...prev, [channel]: sessionCached.items }));
          setIsLoadingChats(false);
        } else {
          setIsLoadingChats(true);
        }
      }
    } else {
      setIsLoadingChats(false);
    }
  }, []);
  const [qualityMetrics, setQualityMetrics] = useState<InteractionQualityMetricsResponse | null>(null);
  const [qualityHistory, setQualityHistory] = useState<InteractionQualityHistoryResponse | null>(null);
  const [opsAlerts, setOpsAlerts] = useState<InteractionOpsAlertsResponse | null>(null);
  const [pilotReadiness, setPilotReadiness] = useState<InteractionPilotReadinessResponse | null>(null);
  const [timeline, setTimeline] = useState<InteractionTimelineResponse | null>(null);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);
  const [pilotMinReplyActivityInput, setPilotMinReplyActivityInput] = useState('1');
  const [pilotReplyWindowDaysInput, setPilotReplyWindowDaysInput] = useState('30');
  const [pilotReadinessParams, setPilotReadinessParams] = useState({
    minReplyActivity: 1,
    replyActivityWindowDays: 30,
  });

  // Persist active workspace to sessionStorage
  useEffect(() => {
    try { sessionStorage.setItem('agentiq_workspace', activeWorkspace); } catch { /* ignore */ }
  }, [activeWorkspace]);

  const chats = useMemo(() => interactions.map(interactionToChat), [interactions]);
  const selectedChat = useMemo(
    () => chats.find((chat) => chat.id === selectedInteractionId) || null,
    [chats, selectedInteractionId]
  );
  const selectedInteraction = useMemo(
    () => interactions.find((item) => item.id === selectedInteractionId) || null,
    [interactions, selectedInteractionId]
  );
  const selectedExtra = useMemo(
    () => asRecord(selectedInteraction?.extra_data),
    [selectedInteraction]
  );

  const aiAnalysis = useMemo(
    () => (selectedChat ? parseAIAnalysis(selectedChat.ai_analysis_json) : null),
    [selectedChat]
  );
  const linkCandidates = useMemo(
    () => extractLinkCandidates(selectedInteraction),
    [selectedInteraction]
  );

  const questionIntent = useMemo(
    () => getStringField(selectedExtra, 'question_intent'),
    [selectedExtra]
  );
  const questionPriorityReason = useMemo(
    () => getStringField(selectedExtra, 'priority_reason'),
    [selectedExtra]
  );
  const questionSlaDueAt = useMemo(
    () => getStringField(selectedExtra, 'sla_due_at'),
    [selectedExtra]
  );
  const questionSlaTargetMinutes = useMemo(
    () => getNumberField(selectedExtra, 'sla_target_minutes'),
    [selectedExtra]
  );

  const upsertInteraction = useCallback((interaction: Interaction) => {
    setInteractionCache((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        if (key === 'all' || key === interaction.channel) {
          const list = next[key];
          const idx = list.findIndex((item) => item.id === interaction.id);
          if (idx >= 0) {
            next[key] = [...list];
            next[key][idx] = interaction;
          } else {
            next[key] = [interaction, ...list];
          }
        }
      }
      return next;
    });
  }, []);

  // Check auth on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getToken();
      if (token) {
        try {
          const me = await authApi.getMe();
          setUser(me);
        } catch {
          // Token invalid, continue as logged out
        }
      }
      setIsCheckingAuth(false);
    };
    checkAuth();
  }, []);

  const handleLogin = useCallback((loggedInUser: User) => {
    setUser(loggedInUser);
    setActiveWorkspace('messages');
    setIsSidebarCollapsed(false);
    setDismissedSyncOnboarding(false);
  }, []);

  const handleLogout = useCallback(() => {
    authApi.logout();
    setUser(null);
    setActiveWorkspace('messages');
    setIsSidebarCollapsed(false);
    setDismissedSyncOnboarding(false);
    setInteractionCache({});
    setSelectedInteractionId(null);
    setMessages([]);
    setTimeline(null);
    setConnectionSkipped(false);
    clearInteractionsCache();
    try {
      localStorage.removeItem(SKIP_CONNECT_STORAGE_KEY);
      sessionStorage.removeItem('agentiq_workspace');
      sessionStorage.removeItem('agentiq_pagination_loaded');
    } catch {
      // ignore
    }
  }, []);

  const handleConnectMarketplace = useCallback(async (apiKey: string) => {
    setIsConnecting(true);
    try {
      const updatedUser = await authApi.connectMarketplace(apiKey);
      setUser(updatedUser);
      setDismissedSyncOnboarding(false);
      if (updatedUser.has_api_credentials && updatedUser.sync_status !== 'error') {
        setConnectionSkipped(false);
        try {
          localStorage.removeItem(SKIP_CONNECT_STORAGE_KEY);
        } catch {
          // ignore
        }
      }
    } finally {
      setIsConnecting(false);
    }
  }, []);

  const handleSkipConnection = useCallback(() => {
    setConnectionSkipped(true);
    setActiveWorkspace('messages');
    try {
      localStorage.setItem(SKIP_CONNECT_STORAGE_KEY, '1');
    } catch {
      // ignore
    }
  }, []);

  const handleResumeConnection = useCallback(() => {
    setConnectionSkipped(false);
    try {
      localStorage.removeItem(SKIP_CONNECT_STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  const handleRetrySync = useCallback(async () => {
    if (!user) return;
    setIsRetryingSync(true);
    try {
      await authApi.triggerSync({ includeInteractions: true });
      const updatedUser = await authApi.getMe();
      setUser(updatedUser);
    } catch (error) {
      console.error('Failed to trigger sync:', error);
      alert('Не удалось запустить синхронизацию. Попробуйте позже.');
    } finally {
      setIsRetryingSync(false);
    }
  }, [user]);

  const fetchInteractions = useCallback(async () => {
    const channelKey = filters.channel || 'all';
    try {
      // First page with total count for pagination
      const paginatedFilters = {
        ...buildInteractionFilters(filters),
        page: 1,
        page_size: 50,
        include_total: true,
      };
      const response = await interactionsApi.getInteractions(paginatedFilters);

      // Update cache: replace first page (newest items)
      const prevItems = interactionCacheRef.current[channelKey];
      const isSame = prevItems
        && prevItems.length >= response.interactions.length
        && response.interactions.every((item, i) =>
          prevItems[i]
          && item.id === prevItems[i].id
          && item.updated_at === prevItems[i].updated_at
          && item.needs_response === prevItems[i].needs_response
        );
      if (!isSame) {
        // Merge: keep newer first-page items, keep already-loaded older pages
        const firstPageIds = new Set(response.interactions.map(i => i.id));
        const olderItems = (prevItems || []).filter(i => !firstPageIds.has(i.id));
        setInteractionCache(prev => ({
          ...prev,
          [channelKey]: [...response.interactions, ...olderItems],
        }));
        // Also split into per-channel caches for instant folder switching
        if (channelKey === 'all') {
          const byChannel: Record<string, Interaction[]> = {};
          for (const item of response.interactions) {
            if (!byChannel[item.channel]) byChannel[item.channel] = [];
            byChannel[item.channel].push(item);
          }
          setInteractionCache(prev => {
            const next: Record<string, Interaction[]> = { ...prev, [channelKey]: [...response.interactions, ...olderItems] };
            for (const [ch, items] of Object.entries(byChannel)) {
              if (!next[ch] || next[ch].length <= items.length) {
                next[ch] = items;
              }
            }
            return next;
          });
        }
      }

      // Track pagination metadata — use functional updater to read latest state (avoids stale closure)
      const total = response.total || response.interactions.length;
      const allLoaded = response.interactions.length < 50;
      let resolvedAllLoaded = allLoaded;
      setPaginationMeta(prev => {
        const currentMeta = prev[channelKey];
        resolvedAllLoaded = allLoaded || ((currentMeta?.allLoaded ?? false) && (prevItems?.length ?? 0) >= total);
        return {
          ...prev,
          [channelKey]: {
            total,
            loadedPages: 1,
            isLoadingMore: false,
            allLoaded: resolvedAllLoaded,
          },
        };
      });

      // Save first page to sessionStorage for instant restore on next visit
      saveInteractionsToCache(channelKey, response.interactions, resolvedAllLoaded);

      if (selectedInteractionId && !response.interactions.some((item) => item.id === selectedInteractionId)) {
        // Selected item might be on a later page — don't deselect
        const allCached = interactionCacheRef.current[channelKey] || [];
        if (!allCached.some(item => item.id === selectedInteractionId)) {
          setSelectedInteractionId(null);
          setMessages([]);
          setTimeline(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch interactions:', error);
    } finally {
      setIsLoadingChats(false);
    }
  }, [filters, selectedInteractionId, paginationMeta]);

  // Background pagination: auto-load next pages
  const fetchNextPage = useCallback(async (channelKey: string) => {
    const meta = paginationMeta[channelKey];
    if (!meta || meta.allLoaded || meta.isLoadingMore) return;

    const nextPage = meta.loadedPages + 1;
    setPaginationMeta(prev => ({
      ...prev,
      [channelKey]: { ...meta, isLoadingMore: true },
    }));

    try {
      const pageFilters: InteractionFilters = { page: nextPage, page_size: 50 };
      if (channelKey !== 'all') pageFilters.channel = channelKey;
      const response = await interactionsApi.getInteractions(pageFilters);

      setInteractionCache(prev => {
        const existing = prev[channelKey] || [];
        const existingIds = new Set(existing.map(i => i.id));
        const newItems = response.interactions.filter(i => !existingIds.has(i.id));
        return { ...prev, [channelKey]: [...existing, ...newItems] };
      });

      const allLoaded = response.interactions.length < 50;
      setPaginationMeta(prev => ({
        ...prev,
        [channelKey]: {
          total: meta.total,
          loadedPages: nextPage,
          isLoadingMore: false,
          allLoaded,
        },
      }));

      // When all pages loaded, save full list to sessionStorage cache
      if (allLoaded) {
        // Read from latest state via ref to get the complete merged list
        setTimeout(() => {
          const fullList = interactionCacheRef.current[channelKey];
          if (fullList) {
            saveInteractionsToCache(channelKey, fullList, true);
          }
        }, 0);
      }
    } catch {
      setPaginationMeta(prev => ({
        ...prev,
        [channelKey]: { ...meta, isLoadingMore: false },
      }));
    }
  }, [paginationMeta]);

  // Auto-trigger background loading of remaining pages
  useEffect(() => {
    const channelKey = filters.channel || 'all';
    const meta = paginationMeta[channelKey];
    if (!meta || meta.allLoaded || meta.isLoadingMore) return;
    const timer = setTimeout(() => fetchNextPage(channelKey), 300);
    return () => clearTimeout(timer);
  }, [paginationMeta, filters.channel, fetchNextPage]);

  const fetchQualityMetrics = useCallback(async () => {
    try {
      setIsLoadingQuality(true);
      const response = await interactionsApi.getQualityMetrics({ days: 30 });
      setQualityMetrics(response);
    } catch (error) {
      console.error('Failed to fetch quality metrics:', error);
    } finally {
      setIsLoadingQuality(false);
    }
  }, []);

  const fetchQualityHistory = useCallback(async () => {
    try {
      setIsLoadingQualityHistory(true);
      const response = await interactionsApi.getQualityHistory({ days: 30 });
      setQualityHistory(response);
    } catch (error) {
      console.error('Failed to fetch quality history:', error);
    } finally {
      setIsLoadingQualityHistory(false);
    }
  }, []);

  const fetchOpsAlerts = useCallback(async () => {
    try {
      setIsLoadingOpsAlerts(true);
      const response = await interactionsApi.getOpsAlerts();
      setOpsAlerts(response);
    } catch (error) {
      console.error('Failed to fetch ops alerts:', error);
    } finally {
      setIsLoadingOpsAlerts(false);
    }
  }, []);

  const fetchPilotReadiness = useCallback(async (
    override?: { minReplyActivity: number; replyActivityWindowDays: number }
  ) => {
    try {
      setIsLoadingPilotReadiness(true);
      const params = override || pilotReadinessParams;
      const response = await interactionsApi.getPilotReadiness({
        min_reply_activity: params.minReplyActivity,
        reply_activity_window_days: params.replyActivityWindowDays,
      });
      setPilotReadiness(response);
    } catch (error) {
      console.error('Failed to fetch pilot readiness:', error);
    } finally {
      setIsLoadingPilotReadiness(false);
    }
  }, [pilotReadinessParams]);

  const handleApplyPilotReadinessParams = useCallback(() => {
    const minReplyActivity = normalizeIntegerInput(pilotMinReplyActivityInput, 1, 0, 10000);
    const replyActivityWindowDays = normalizeIntegerInput(pilotReplyWindowDaysInput, 30, 1, 365);

    setPilotMinReplyActivityInput(String(minReplyActivity));
    setPilotReplyWindowDaysInput(String(replyActivityWindowDays));
    const next = { minReplyActivity, replyActivityWindowDays };
    setPilotReadinessParams(next);
    fetchPilotReadiness(next);
  }, [pilotMinReplyActivityInput, pilotReplyWindowDaysInput, fetchPilotReadiness]);

  const fetchMessages = useCallback(async (interactionId: number) => {
    try {
      setIsLoadingMessages(true);

      // Try to show messages from cache immediately while fetching fresh data
      const cachedInteraction = Object.values(interactionCacheRef.current)
        .flat()
        .find((item) => item.id === interactionId);

      if (cachedInteraction) {
        // Show cached messages immediately to reduce perceived latency
        if (cachedInteraction.channel !== 'chat') {
          setMessages(buildMessagesFromInteraction(cachedInteraction));
          setIsLoadingMessages(false);
        }
      }

      // Fetch fresh interaction data in parallel with messages
      const interaction = await interactionsApi.getInteraction(interactionId);
      upsertInteraction(interaction);

      if (interaction.channel === 'chat') {
        const extra = asRecord(interaction.extra_data);
        const rawChatId = extra.chat_id;
        const chatId = typeof rawChatId === 'number'
          ? rawChatId
          : (typeof rawChatId === 'string' && /^\d+$/.test(rawChatId.trim()))
          ? Number.parseInt(rawChatId.trim(), 10)
          : null;
        if (typeof chatId === 'number' && Number.isFinite(chatId)) {
          const response = await chatApi.getMessages(chatId);
          setMessages(response.messages);
        } else {
          setMessages(buildMessagesFromInteraction(interaction));
        }
      } else {
        setMessages(buildMessagesFromInteraction(interaction));
      }
    } catch (error) {
      console.error('Failed to fetch interaction details:', error);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [upsertInteraction]);

  const fetchTimeline = useCallback(async (interactionId: number) => {
    try {
      setIsLoadingTimeline(true);
      const response = await interactionsApi.getTimeline(interactionId, {
        maxItems: 100,
        productWindowDays: 45,
      });
      setTimeline(response);
    } catch (error) {
      console.error('Failed to fetch interaction timeline:', error);
      setTimeline(null);
    } finally {
      setIsLoadingTimeline(false);
    }
  }, []);

  // Poll for sync status updates when syncing — also fetch interactions progressively
  useEffect(() => {
    if (!user || user.sync_status !== 'syncing') return;

    const pollInterval = setInterval(async () => {
      try {
        // 1. Poll user status
        const updatedUser = await authApi.getMe();
        setUser(updatedUser);

        // 2. Poll interactions (first page + total) to show progress during sync
        try {
          const response = await interactionsApi.getInteractions({
            page_size: 50,
            include_total: true,
          });
          setSyncLoadedCount(response.total || response.interactions.length);
          if (response.interactions.length > 0) {
            setInteractionCache(prev => {
              const existing = prev['all'] || [];
              if (existing.length < response.interactions.length) {
                return { ...prev, all: response.interactions };
              }
              return prev;
            });
          }
          // Auto-transition to chat center at 50+ items
          if ((response.total || response.interactions.length) >= 50 && !syncAutoTransitioned) {
            setSyncAutoTransitioned(true);
            setDismissedSyncOnboarding(true);
            setActiveWorkspace('messages');
            setIsLoadingChats(false);
          }
        } catch {
          // Interactions not ready yet — that's ok during sync
        }

        // 3. When sync completes, do full refresh
        if (updatedUser.sync_status !== 'syncing') {
          clearInterval(pollInterval);
          fetchInteractions();
          fetchQualityMetrics();
          fetchQualityHistory();
          fetchOpsAlerts();
          fetchPilotReadiness();
        }
      } catch (error) {
        console.error('Failed to poll sync status:', error);
      }
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [user?.sync_status, syncAutoTransitioned, fetchInteractions, fetchQualityMetrics, fetchQualityHistory, fetchOpsAlerts, fetchPilotReadiness]);

  const handleSelectChat = useCallback(async (chat: Chat) => {
    setSelectedInteractionId(chat.id);
    setMobileView('chat');
    await Promise.all([fetchMessages(chat.id), fetchTimeline(chat.id)]);

    if (!chat.ai_suggestion_text && chat.unread_count > 0) {
      try {
        const draft = await interactionsApi.generateDraft(chat.id);
        upsertInteraction(draft.interaction);
      } catch (e) {
        console.warn('Auto-draft generation failed:', e);
      }
    }
  }, [fetchMessages, fetchTimeline, upsertInteraction]);

  const handleAnalyzeChat = useCallback(async () => {
    if (!selectedInteractionId || isAnalyzing) return;
    setIsAnalyzing(true);
    try {
      const draft = await interactionsApi.generateDraft(
        selectedInteractionId,
        { forceRegenerate: true }
      );
      upsertInteraction(draft.interaction);
      if (draft.interaction.channel !== 'chat') {
        setMessages(buildMessagesFromInteraction(draft.interaction));
      } else {
        await fetchMessages(draft.interaction.id);
      }
      fetchTimeline(selectedInteractionId);
      fetchQualityMetrics();
      fetchQualityHistory();
      fetchOpsAlerts();
      fetchPilotReadiness();
    } catch (error) {
      console.error('Failed to generate AI draft:', error);
      alert('Ошибка генерации AI черновика');
    } finally {
      setIsAnalyzing(false);
    }
  }, [selectedInteractionId, isAnalyzing, upsertInteraction, fetchTimeline, fetchQualityMetrics, fetchQualityHistory, fetchOpsAlerts, fetchPilotReadiness]);

  const handleSendMessage = useCallback(async (text: string) => {
    if (!selectedInteractionId) return;

    try {
      const reply = await interactionsApi.reply(selectedInteractionId, text);
      upsertInteraction(reply.interaction);
      if (reply.interaction.channel !== 'chat') {
        setMessages(buildMessagesFromInteraction(reply.interaction));
      } else {
        await fetchMessages(reply.interaction.id);
      }
      fetchTimeline(selectedInteractionId);
      fetchQualityMetrics();
      fetchQualityHistory();
      fetchOpsAlerts();
      fetchPilotReadiness();
    } catch (error) {
      console.error('Failed to send reply:', error);
      throw error;
    }
  }, [selectedInteractionId, upsertInteraction, fetchTimeline, fetchQualityMetrics, fetchQualityHistory, fetchOpsAlerts, fetchPilotReadiness, fetchMessages]);

  const handleBackToList = useCallback(() => {
    setMobileView('list');
  }, []);

  const handleOpenContext = useCallback(() => {
    setMobileView('context');
  }, []);

  const handleBackFromContext = useCallback(() => {
    setMobileView('chat');
  }, []);

  const handleRegenerateAI = useCallback(async (interactionId: number) => {
    setInteractionCache((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        next[key] = next[key].map((item) => {
          if (item.id !== interactionId) return item;
          const extra = asRecord(item.extra_data);
          return { ...item, extra_data: { ...extra, last_ai_draft: null } };
        });
      }
      return next;
    });

    const draft = await interactionsApi.generateDraft(
      interactionId,
      { forceRegenerate: true }
    );
    upsertInteraction(draft.interaction);
    fetchTimeline(interactionId);
    fetchQualityMetrics();
    fetchQualityHistory();
    fetchOpsAlerts();
    fetchPilotReadiness();
    if (selectedInteractionId === interactionId) {
      if (draft.interaction.channel !== 'chat') {
        setMessages(buildMessagesFromInteraction(draft.interaction));
      } else {
        fetchMessages(draft.interaction.id);
      }
    }
  }, [selectedInteractionId, upsertInteraction, fetchTimeline, fetchQualityMetrics, fetchQualityHistory, fetchOpsAlerts, fetchPilotReadiness, fetchMessages]);

  const handleOpenTimelineStep = useCallback(async (interactionId: number) => {
    setSelectedInteractionId(interactionId);
    setMobileView('chat');
    await Promise.all([fetchMessages(interactionId), fetchTimeline(interactionId)]);
  }, [fetchMessages, fetchTimeline]);

  const handleApplyTimelineTemplate = useCallback((templateText: string) => {
    const text = templateText.trim();
    if (!selectedInteractionId || !text) return;

    setInteractionCache((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        next[key] = next[key].map((item) => {
          if (item.id !== selectedInteractionId) return item;
          const extra = asRecord(item.extra_data);
          const existingDraft = asRecord(extra.last_ai_draft);
          return {
            ...item,
            extra_data: {
              ...extra,
              last_ai_draft: {
                ...existingDraft,
                text,
                source: "timeline_template",
                intent: (existingDraft.intent as string) || "thread_template",
                sentiment: (existingDraft.sentiment as string) || "neutral",
                sla_priority: (existingDraft.sla_priority as string) || item.priority,
                recommendation_reason: "Template from deterministic thread",
              },
            },
          };
        });
      }
      return next;
    });
  }, [selectedInteractionId]);

  // Restore from sessionStorage cache on mount, then fetch fresh data
  useEffect(() => {
    if (!user || cacheRestoredRef.current) return;
    cacheRestoredRef.current = true;

    const channelKey = filters.channel || 'all';
    const cached = loadInteractionsFromCache(channelKey);
    if (cached && cached.items.length > 0) {
      // Show cached data immediately -- NO spinner
      setInteractionCache(prev => ({ ...prev, [channelKey]: cached.items }));
      setIsLoadingChats(false);

      // Restore pagination meta so sync banner doesn't flash
      if (cached.allLoaded) {
        setPaginationMeta(prev => ({
          ...prev,
          [channelKey]: {
            total: cached.items.length,
            loadedPages: 1,
            isLoadingMore: false,
            allLoaded: true,
          },
        }));
      }

      // Also populate per-channel caches from 'all' for instant folder switching
      if (channelKey === 'all') {
        const byChannel: Record<string, Interaction[]> = {};
        for (const item of cached.items) {
          if (!byChannel[item.channel]) byChannel[item.channel] = [];
          byChannel[item.channel].push(item);
        }
        setInteractionCache(prev => {
          const next: Record<string, Interaction[]> = { ...prev, [channelKey]: cached.items };
          for (const [ch, items] of Object.entries(byChannel)) {
            if (!next[ch] || next[ch].length <= items.length) {
              next[ch] = items;
            }
          }
          return next;
        });
      }
    }
  }, [user, filters.channel]);

  // Fetch interactions and essential metrics when user changes
  useEffect(() => {
    if (user) {
      fetchInteractions();
      fetchQualityMetrics();
    }
  }, [user]);

  // Fetch analytics data only when analytics tab is active
  const isAnalyticsActive = activeWorkspace === 'analytics';
  useEffect(() => {
    if (user && isAnalyticsActive) {
      fetchQualityHistory();
      fetchOpsAlerts();
      fetchPilotReadiness();
    }
  }, [user, isAnalyticsActive]);

  // Poll unified interactions (essential — always active)
  usePolling(fetchInteractions, 10000, !!user);
  usePolling(fetchQualityMetrics, 30000, !!user);
  // Poll analytics data only when analytics tab is active
  usePolling(fetchQualityHistory, 60000, !!user && isAnalyticsActive);
  usePolling(fetchOpsAlerts, 60000, !!user && isAnalyticsActive);
  usePolling(fetchPilotReadiness, 60000, !!user && isAnalyticsActive);

  const formatLastMessage = (dateString: string | null) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return '—'; }
  };

  if (isCheckingAuth) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--color-bg-primary)'
      }}>
        <div style={{
          border: '3px solid var(--color-border-medium)',
          borderTop: '3px solid var(--color-accent)',
          borderRadius: '50%',
          width: '40px',
          height: '40px',
          animation: 'spin 1s linear infinite'
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  const needsConnectionOnboarding = !user.has_api_credentials && !connectionSkipped;
  if (needsConnectionOnboarding) {
    return (
      <MarketplaceOnboarding
        user={user}
        isConnecting={isConnecting}
        isRetryingSync={isRetryingSync}
        onConnectMarketplace={handleConnectMarketplace}
        onRetrySync={handleRetrySync}
        onSkip={handleSkipConnection}
        onContinue={() => setActiveWorkspace('messages')}
      />
    );
  }

  const shouldShowSyncOnboarding = Boolean(user.has_api_credentials)
    && user.sync_status === 'syncing'
    && !dismissedSyncOnboarding
    && !connectionSkipped;
  if (shouldShowSyncOnboarding) {
    return (
      <MarketplaceOnboarding
        user={user}
        isConnecting={isConnecting}
        isRetryingSync={isRetryingSync}
        loadedCount={syncLoadedCount}
        onConnectMarketplace={handleConnectMarketplace}
        onRetrySync={handleRetrySync}
        onSkip={() => {
          setDismissedSyncOnboarding(true);
          setActiveWorkspace('messages');
        }}
        onContinue={() => {
          setDismissedSyncOnboarding(true);
          setActiveWorkspace('messages');
        }}
      />
    );
  }

  const getUrgencyLabel = (urgency: string) => {
    const labels: Record<string, string> = {
      low: 'Низкая',
      normal: 'Обычная',
      high: 'Высокая',
      critical: 'Критическая',
    };
    return labels[urgency] || urgency;
  };

  const getSentimentLabel = (sentiment: string) => {
    const labels: Record<string, string> = {
      positive: 'Позитивная',
      neutral: 'Нейтральная',
      negative: 'Негативная',
    };
    return labels[sentiment] || sentiment;
  };

  const getQuestionIntentLabel = (intent: string | null) => {
    const labels: Record<string, string> = {
      sizing_fit: 'Размер и посадка',
      availability_delivery: 'Наличие и доставка',
      spec_compatibility: 'Характеристики и совместимость',
      compliance_safety: 'Безопасность и соответствие',
      post_purchase_issue: 'Проблема после покупки',
      general_question: 'Общий вопрос',
    };
    if (!intent) return '—';
    return labels[intent] || intent;
  };

  const formatDateTime = (value: string | null) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getSlaState = (dueAt: string | null, needsResponse: boolean) => {
    if (!dueAt) return { label: 'Не задан', tone: 'normal' as const };
    const due = new Date(dueAt);
    if (Number.isNaN(due.getTime())) return { label: 'Некорректная дата', tone: 'normal' as const };
    if (!needsResponse) return { label: 'Ответ дан', tone: 'normal' as const };
    const diffMs = due.getTime() - Date.now();
    if (diffMs < 0) return { label: 'SLA просрочен', tone: 'urgent' as const };
    if (diffMs <= 60 * 60 * 1000) return { label: 'SLA < 1 часа', tone: 'warning' as const };
    return { label: 'В SLA', tone: 'normal' as const };
  };

  const getTimelineScopeLabel = (scope: string | undefined) => {
    if (scope === 'customer_order') return 'Клиент + заказ + товар';
    if (scope === 'customer') return 'Клиент + товар';
    if (scope === 'product') return 'Товарный thread';
    if (scope === 'single') return 'Одиночное обращение';
    return scope || '—';
  };

  const getMatchReasonLabel = (reason: string) => {
    const labels: Record<string, string> = {
      current_interaction: 'Текущее обращение',
      order_id_exact: 'Совпадение order_id',
      customer_id_exact: 'Совпадение customer_id',
      nm_id_time_window: 'Товар nm_id + окно времени',
      article_time_window: 'Артикул + окно времени',
    };
    return labels[reason] || reason;
  };

  const wbChannelLink = selectedInteraction?.channel === 'review'
    ? 'https://seller.wildberries.ru/communication/reviews'
    : selectedInteraction?.channel === 'question'
    ? 'https://seller.wildberries.ru/communication/questions'
    : 'https://seller.wildberries.ru/communication/chats';

  const wbChannelLinkLabel = selectedInteraction?.channel === 'review'
    ? 'Открыть отзывы на WB'
    : selectedInteraction?.channel === 'question'
    ? 'Открыть вопросы на WB'
    : 'Открыть чаты на WB';

  const historySeries = qualityHistory?.series || [];
  const maxRepliesInHistory = historySeries.reduce((maxValue, point) => {
    return Math.max(maxValue, point.replies_total);
  }, 0);
  const pilotNonPassChecks = (pilotReadiness?.checks || []).filter((item) => item.status !== 'pass');
  const urgentForNav = chats.filter((chat) =>
    chat.sla_priority === 'urgent' ||
    (chat.sla_deadline_at && new Date(chat.sla_deadline_at) < new Date())
  ).length;
  const showDemoBanner = connectionSkipped && !user.has_api_credentials;

  const getReadinessBadgeClass = (status: string) => {
    if (status === 'fail') return 'insight-badge urgent';
    if (status === 'warn') return 'insight-badge warning';
    return 'insight-badge';
  };

  return (
    <div className="app-shell-page">
      {showDemoBanner && (
        <div className="demo-banner">
          <div className="demo-banner-text">
            <div className="demo-banner-dot"></div>
            Демо-данные. Подключите Wildberries, чтобы увидеть свои чаты
          </div>
          <button className="demo-banner-btn" type="button" onClick={handleResumeConnection}>
            Подключить
          </button>
        </div>
      )}
      <div className="app-shell">
        <nav className={`sidebar${isSidebarCollapsed ? ' collapsed' : ''}`}>
          <div className="sidebar-logo">AGENT<span>IQ</span></div>
          <button
            className="sidebar-collapse-btn"
            type="button"
            title="Свернуть меню"
            onClick={() => setIsSidebarCollapsed((prev) => !prev)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="11 17 6 12 11 7" />
              <polyline points="18 17 13 12 18 7" />
            </svg>
          </button>
          <div className="sidebar-nav">
            <button
              type="button"
              className={`sidebar-item ${activeWorkspace === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveWorkspace('dashboard')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
              <span className="sidebar-label">Главная</span>
            </button>
            <button
              type="button"
              className={`sidebar-item ${activeWorkspace === 'messages' ? 'active' : ''}`}
              onClick={() => setActiveWorkspace('messages')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <span className="sidebar-label">Сообщения</span>
              {activeWorkspace !== 'messages' && urgentForNav > 0 && (
                <div className="sidebar-badge">{urgentForNav}</div>
              )}
            </button>
            <button
              type="button"
              className={`sidebar-item ${activeWorkspace === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveWorkspace('analytics')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              <span className="sidebar-label">Аналитика</span>
            </button>
          </div>
          <div className="sidebar-bottom">
            <button
              type="button"
              className={`sidebar-item ${activeWorkspace === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveWorkspace('settings')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              <span className="sidebar-label">Настройки</span>
            </button>
            <button type="button" className="sidebar-item" onClick={handleLogout}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              <span className="sidebar-label">Выйти</span>
            </button>
          </div>
        </nav>

        <div className="app-content">
          {activeWorkspace === 'settings' ? (
            <SettingsPage
              user={user}
              onOpenConnectOnboarding={handleResumeConnection}
              onLogout={handleLogout}
            />
          ) : activeWorkspace === 'dashboard' ? (
            <div className="workspace-placeholder">
              <svg className="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width="48" height="48">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
              <h2>Главная</h2>
              <p>Дашборд будет доступен в следующем обновлении</p>
            </div>
          ) : activeWorkspace === 'analytics' ? (
            <div className="analytics-page mode-ops" id="analyticsPage">
              <div className="analytics-header">
                <div className="analytics-title">Аналитика</div>
                <div className="analytics-controls">
                  <div className="analytics-period">
                    <button className="period-btn" type="button" disabled>7 дней</button>
                    <button className="period-btn active" type="button">30 дней</button>
                    <button className="period-btn" type="button" disabled>90 дней</button>
                  </div>
                  <div className="analytics-mode">
                    <button className="period-btn active" type="button">Операционный</button>
                    <button className="period-btn" type="button" disabled>Полный</button>
                  </div>
                </div>
              </div>

              <div className="kpi-strip">
                <div className="kpi-card">
                  <div className="kpi-label">Отвечено</div>
                  <div className="kpi-value-row">
                    <div className="kpi-value">
                      {qualityMetrics && qualityMetrics.pipeline.interactions_total > 0
                        ? `${Math.round((qualityMetrics.pipeline.responded_total / qualityMetrics.pipeline.interactions_total) * 100)}%`
                        : '—'}
                    </div>
                  </div>
                  <div className="kpi-trend neutral">
                    {qualityMetrics
                      ? `${qualityMetrics.pipeline.responded_total} из ${qualityMetrics.pipeline.interactions_total}`
                      : 'Нет данных'}
                  </div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">Без ответа</div>
                  <div className="kpi-value-row">
                    <div className="kpi-value">
                      {qualityMetrics ? qualityMetrics.pipeline.needs_response_total : '—'}
                    </div>
                  </div>
                  <div className="kpi-trend neutral">Текущий backlog</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">SLA overdue</div>
                  <div className="kpi-value-row">
                    <div className="kpi-value">{opsAlerts ? Number(opsAlerts.question_sla.overdue_total || 0) : '—'}</div>
                  </div>
                  <div className="kpi-trend neutral">
                    {opsAlerts
                      ? `Due soon: ${Number(opsAlerts.question_sla.due_soon_total || 0)}`
                      : 'Нет данных'}
                  </div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">Pilot readiness</div>
                  <div className="kpi-value-row">
                    <div className={`kpi-value ${pilotReadiness ? (pilotReadiness.go_no_go ? 'ok' : 'risk') : ''}`}>
                      {pilotReadiness ? (pilotReadiness.go_no_go ? 'GO' : 'NO-GO') : '—'}
                    </div>
                  </div>
                  <div className="kpi-trend neutral">
                    {pilotReadiness ? `Checks: ${pilotReadiness.summary.total_checks}` : 'Нет данных'}
                  </div>
                </div>
              </div>

              <div className="analytics-grid">
                <div className="chart-card analytics-card">
                  <div className="chart-title">Качество ответов (30 дней)</div>
                  {isLoadingQuality && !qualityMetrics ? (
                    <div className="info-value">Загрузка метрик...</div>
                  ) : qualityMetrics ? (
                    <>
                      <div className="quality-grid">
                        <div className="quality-card">
                          <div className="quality-card-label">Принят AI</div>
                          <div className="quality-card-value">{formatRate(qualityMetrics.totals.accept_rate)}</div>
                          <div className="quality-card-meta">{qualityMetrics.totals.draft_accepted} ответов</div>
                        </div>
                        <div className="quality-card">
                          <div className="quality-card-label">AI отредактирован</div>
                          <div className="quality-card-value">{formatRate(qualityMetrics.totals.edit_rate)}</div>
                          <div className="quality-card-meta">{qualityMetrics.totals.draft_edited} ответов</div>
                        </div>
                        <div className="quality-card">
                          <div className="quality-card-label">Ручной ответ</div>
                          <div className="quality-card-value">{formatRate(qualityMetrics.totals.manual_rate)}</div>
                          <div className="quality-card-meta">{qualityMetrics.totals.reply_manual} ответов</div>
                        </div>
                      </div>
                      <div className="quality-backlog">
                        В обработке: {qualityMetrics.pipeline.needs_response_total} из {qualityMetrics.pipeline.interactions_total}
                      </div>
                      <div className="quality-channels">
                        {qualityMetrics.by_channel.map((item) => (
                          <span key={item.channel} className="insight-badge">
                            {item.channel}: {formatRate(item.accept_rate)}
                          </span>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="info-value">Метрики пока недоступны</div>
                  )}
                </div>

                <div className="chart-card analytics-card">
                  <div className="chart-title">Ops alerts</div>
                  {isLoadingOpsAlerts && !opsAlerts ? (
                    <div className="info-label">Загрузка алертов...</div>
                  ) : opsAlerts ? (
                    <>
                      <div className="quality-channels">
                        <span className="insight-badge">
                          SLA overdue: {Number(opsAlerts.question_sla.overdue_total || 0)}
                        </span>
                        <span className="insight-badge">
                          SLA due soon: {Number(opsAlerts.question_sla.due_soon_total || 0)}
                        </span>
                        <span className={`insight-badge${Boolean(opsAlerts.quality_regression.regression_detected) ? ' urgent' : ''}`}>
                          Manual delta: {Math.round(Number(opsAlerts.quality_regression.manual_rate_delta || 0) * 100)}%
                        </span>
                      </div>
                      <div className="analytics-alert-list">
                        {opsAlerts.alerts.length === 0 ? (
                          <div className="info-label">Активных алертов нет</div>
                        ) : opsAlerts.alerts.map((alert) => (
                          <div key={alert.code} className="pilot-check-line">
                            <span className={`insight-badge${alert.severity === 'high' ? ' urgent' : ''}`}>{alert.severity}</span>
                            <span className="pilot-check-text">{alert.title}: {alert.message}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="info-label">Алерты пока недоступны</div>
                  )}
                </div>
              </div>

              <div className="analytics-grid">
                <div className="chart-card analytics-card">
                  <div className="chart-title">Pilot Go/No-Go readiness</div>
                  {isLoadingPilotReadiness && !pilotReadiness ? (
                    <div className="info-label">Загрузка readiness...</div>
                  ) : pilotReadiness ? (
                    <>
                      <div className="pilot-readiness-controls">
                        <label className="pilot-readiness-field">
                          min replies
                          <input
                            className="pilot-readiness-input"
                            type="number"
                            min={0}
                            max={10000}
                            value={pilotMinReplyActivityInput}
                            onChange={(event) => setPilotMinReplyActivityInput(event.target.value)}
                          />
                        </label>
                        <label className="pilot-readiness-field">
                          window days
                          <input
                            className="pilot-readiness-input"
                            type="number"
                            min={1}
                            max={365}
                            value={pilotReplyWindowDaysInput}
                            onChange={(event) => setPilotReplyWindowDaysInput(event.target.value)}
                          />
                        </label>
                        <button
                          className="pilot-readiness-apply"
                          type="button"
                          onClick={handleApplyPilotReadinessParams}
                          disabled={isLoadingPilotReadiness}
                        >
                          Применить
                        </button>
                      </div>
                      <div className="pilot-readiness-thresholds">
                        thresholds: min_reply_activity=
                        {String((pilotReadiness.thresholds as Record<string, unknown>)?.min_reply_activity ?? '—')}
                        , reply_activity_window_days=
                        {String((pilotReadiness.thresholds as Record<string, unknown>)?.reply_activity_window_days ?? '—')}
                      </div>
                      <div className="quality-channels">
                        <span className={`insight-badge${pilotReadiness.go_no_go ? '' : ' urgent'}`}>
                          {pilotReadiness.go_no_go ? 'GO' : 'NO-GO'}
                        </span>
                        <span className="insight-badge">checks: {pilotReadiness.summary.total_checks}</span>
                        <span className="insight-badge">pass: {pilotReadiness.summary.passed}</span>
                        <span className="insight-badge">warn: {pilotReadiness.summary.warnings}</span>
                        <span className={`insight-badge${pilotReadiness.summary.failed > 0 ? ' urgent' : ''}`}>
                          fail: {pilotReadiness.summary.failed}
                        </span>
                      </div>
                      {pilotNonPassChecks.slice(0, 6).map((check) => (
                        <div key={check.code} className="pilot-check-line">
                          <span className={getReadinessBadgeClass(check.status)}>{check.status}</span>
                          <span className="pilot-check-text">{check.title}: {check.details}</span>
                        </div>
                      ))}
                    </>
                  ) : (
                    <div className="info-label">Readiness пока недоступен</div>
                  )}
                </div>

                <div className="chart-card analytics-card">
                  <div className="chart-title">Динамика ответов (по дням)</div>
                  {isLoadingQualityHistory && !qualityHistory ? (
                    <div className="info-label">Загрузка истории...</div>
                  ) : historySeries.length === 0 ? (
                    <div className="info-label">История пока пустая</div>
                  ) : (
                    <div className="quality-history-chart">
                      {historySeries.map((point, index) => {
                        const heightRatio = maxRepliesInHistory > 0 ? point.replies_total / maxRepliesInHistory : 0;
                        const barHeight = Math.max(4, Math.round(heightRatio * 56));
                        const dayLabel = point.date.slice(5);
                        return (
                          <div
                            key={point.date}
                            className="quality-history-col"
                            title={`${point.date}: replies=${point.replies_total}, accept=${formatRate(point.accept_rate)}`}
                          >
                            <div className="quality-history-bar-wrap">
                              <div className="quality-history-bar" style={{ height: `${barHeight}px` }} />
                            </div>
                            {index % 5 === 0 || index === historySeries.length - 1 ? (
                              <div className="quality-history-label">{dayLabel}</div>
                            ) : (
                              <div className="quality-history-label placeholder">·</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="chat-center" data-mobile-view={mobileView}>
              <FolderStrip
                variant="desktop"
                activeChannel={activeChannel}
                onChannelChange={handleChannelChange}
                pipeline={qualityMetrics?.pipeline}
                totalChats={chats.length}
              />
              <ChatList
                chats={chats}
                selectedChatId={selectedChat?.id || null}
                onSelectChat={handleSelectChat}
                onFiltersChange={setFilters}
                pipeline={qualityMetrics?.pipeline}
                activeChannel={activeChannel}
                onChannelChange={handleChannelChange}
                onConnectMarketplace={handleConnectMarketplace}
                isConnecting={isConnecting}
                isLoadingChats={isLoadingChats}
                hasApiCredentials={user.has_api_credentials}
                syncStatus={user.sync_status}
                syncError={user.sync_error}
                lastSyncAt={user.last_sync_at}
                onRetrySync={handleRetrySync}
                isRetryingSync={isRetryingSync}
                isConnectionSkipped={connectionSkipped}
                onOpenConnectOnboarding={handleResumeConnection}
                loadingProgress={(() => {
                  const meta = paginationMeta[activeChannel];
                  if (!meta || meta.allLoaded) return null;
                  const loaded = (interactionCache[activeChannel] || []).length;
                  return { loaded, total: meta.total };
                })()}
              />

              <ChatWindow
                chat={selectedChat}
                messages={messages}
                onSendMessage={handleSendMessage}
                isLoadingMessages={isLoadingMessages}
                onBack={handleBackToList}
                onOpenContext={handleOpenContext}
                onRegenerateAI={handleRegenerateAI}
                showLifecycleActions={false}
              />

              <aside className="product-context">
                <div className="context-header">
                  <button className="context-back-btn" onClick={handleBackFromContext}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    Назад к чату
                  </button>
                  <div className="context-title">Контекст менеджера</div>
                  {selectedChat ? (
                    <>
                      <div className="product-name">{selectedChat.product_name || 'Обращение покупателя'}</div>
                      <div className="product-rating">{selectedChat.product_article ? `Арт. ${selectedChat.product_article}` : ''}</div>
                      <div className="product-price"></div>
                    </>
                  ) : (
                    <div className="product-name">Выберите обращение</div>
                  )}
                </div>

                {selectedChat && (
                  <>
            <div className="info-section">
              <div className="info-section-title">Детали обращения</div>
              <div className="info-item">
                <div className="info-label">Канал</div>
                <div className="info-value">
                  {selectedChat.channel_type === 'review'
                    ? 'Отзыв'
                    : selectedChat.channel_type === 'question'
                    ? 'Вопрос'
                    : 'Чат'}
                </div>
              </div>
              <div className="info-item">
                <div className="info-label">Статус</div>
                <div className="info-value">
                  {selectedChat.chat_status === 'waiting' ? 'Ожидает ответа' :
                   selectedChat.chat_status === 'responded' ? 'Отвечено' :
                   selectedChat.chat_status === 'client-replied' ? 'Клиент ответил' :
                   selectedChat.chat_status === 'closed' ? 'Закрыт' :
                   selectedChat.chat_status || 'Открыт'}
                </div>
              </div>
              <div className="info-item">
                <div className="info-label">Последнее сообщение</div>
                <div className="info-value">{formatLastMessage(selectedChat.last_message_at)}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Ждет ответа</div>
                <div className="info-value">{selectedChat.unread_count > 0 ? 'Да' : 'Нет'}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Клиент</div>
                <div className="info-value">{selectedChat.customer_name || '—'}</div>
              </div>
              {selectedChat.channel_type === 'question' && (
                <>
                  <div className="info-item">
                    <div className="info-label">Интент вопроса</div>
                    <div className="info-value">
                      <span className="insight-badge">{getQuestionIntentLabel(questionIntent)}</span>
                    </div>
                  </div>
                  <div className="info-item">
                    <div className="info-label">SLA дедлайн</div>
                    <div className="info-value">
                      {formatDateTime(questionSlaDueAt)}
                      <span className={`insight-badge${getSlaState(questionSlaDueAt, selectedInteraction?.needs_response ?? false).tone !== 'normal' ? ' urgent' : ''}`}>
                        {getSlaState(questionSlaDueAt, selectedInteraction?.needs_response ?? false).label}
                      </span>
                    </div>
                  </div>
                  <div className="info-item">
                    <div className="info-label">SLA цель</div>
                    <div className="info-value">{questionSlaTargetMinutes ? `${questionSlaTargetMinutes} мин` : '—'}</div>
                  </div>
                  <div className="info-item">
                    <div className="info-label">Причина приоритета</div>
                    <div className="info-value">{questionPriorityReason || '—'}</div>
                  </div>
                </>
              )}
            </div>

            <div className="info-section">
              <div className="info-section-title">Deterministic Thread Timeline</div>
              {isLoadingTimeline && !timeline ? (
                <div className="info-label">Загрузка timeline...</div>
              ) : !timeline || timeline.steps.length === 0 ? (
                <div className="info-label">Связанные шаги не найдены.</div>
              ) : (
                <>
                  <div className="info-item">
                    <div className="info-label">Scope</div>
                    <div className="info-value">{getTimelineScopeLabel(timeline.thread_scope)}</div>
                  </div>
                  <div className="info-item">
                    <div className="info-label">Каналы</div>
                    <div className="info-value">{timeline.channels_present.join(' -> ') || '—'}</div>
                  </div>
                  {timeline.steps.map((step) => (
                    <div key={`timeline-${step.interaction_id}`} className="link-candidate-card">
                      <div className="link-candidate-top">
                        <span className="link-candidate-channel">
                          {step.channel}
                          {step.is_current ? ' · текущее' : ''}
                        </span>
                        <span className={`link-candidate-confidence ${confidenceTier(step.confidence)}`}>
                          {Math.round(step.confidence * 100)}%
                        </span>
                      </div>
                      <div className="link-candidate-id">{getMatchReasonLabel(step.match_reason)}</div>
                      <div className="link-candidate-expl">
                        {formatDateTime(step.occurred_at)} · {step.action_mode === 'auto_allowed' ? 'auto-allowed' : 'assist-only'}
                      </div>
                      <div className="timeline-step-actions">
                        {!step.is_current && (
                          <button
                            className="timeline-action-btn"
                            onClick={() => handleOpenTimelineStep(step.interaction_id)}
                          >
                            Перейти
                          </button>
                        )}
                        {step.wb_url && (
                          <a
                            href={step.wb_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="timeline-action-btn link"
                          >
                            WB
                          </a>
                        )}
                        {(step.last_reply_text || step.last_ai_draft_text) && !step.is_current && (
                          <button
                            className="timeline-action-btn"
                            onClick={() => handleApplyTimelineTemplate(step.last_reply_text || step.last_ai_draft_text || '')}
                          >
                            Шаблон
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="info-label">
                    Guardrail: авто-действия разрешены только для deterministic links при confidence {'>='} 85%.
                  </div>
                </>
              )}
            </div>

            <div className="info-section">
              <div className="info-section-title">Вероятностные связи (confidence)</div>
              {linkCandidates.length === 0 ? (
                <>
                  <div className="info-value">Нет вероятностных связей</div>
                  <div className="info-label">
                    Появятся после включения probabilistic-linking в pipeline.
                  </div>
                </>
              ) : (
                <>
                  {linkCandidates.map((candidate, index) => (
                    <div key={`${candidate.channel}-${candidate.externalId ?? index}`} className="link-candidate-card">
                      <div className="link-candidate-top">
                        <span className="link-candidate-channel">{candidate.channel}</span>
                        <span className={`link-candidate-confidence ${confidenceTier(candidate.confidence)}`}>
                          {Math.round(candidate.confidence * 100)}%
                        </span>
                      </div>
                      {candidate.externalId && (
                        <div className="link-candidate-id">ID: {candidate.externalId}</div>
                      )}
                      {candidate.explanation && (
                        <div className="link-candidate-expl">{candidate.explanation}</div>
                      )}
                      {candidate.reasoningSignals.length > 0 && (
                        <div className="link-candidate-signals">
                          {candidate.reasoningSignals.map((signal) => (
                            <span key={signal} className="insight-badge">{signal}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  <div className="info-label">Авто-действия отключены при confidence ниже 85%.</div>
                </>
              )}
            </div>

            <div className="info-section">
              <div className="info-section-title">
                AI Анализ
                <button
                  className="analyze-btn"
                  onClick={handleAnalyzeChat}
                  disabled={isAnalyzing}
                  title="Запустить AI анализ"
                >
                  {isAnalyzing ? '...' : '↻'}
                </button>
              </div>
              <div className="info-item">
                <div className="info-label">Интент</div>
                <div className="info-value">
                  <span className="insight-badge">
                    {aiAnalysis?.intent || '—'}
                  </span>
                </div>
              </div>
              <div className="info-item">
                <div className="info-label">Тональность</div>
                <div className="info-value">
                  {aiAnalysis ? (
                    <span className={`insight-badge${aiAnalysis.sentiment === 'negative' ? ' negative' : ''}`}>
                      {aiAnalysis.sentimentLabel || getSentimentLabel(aiAnalysis.sentiment)}
                    </span>
                  ) : <span className="insight-badge">—</span>}
                </div>
              </div>
              <div className="info-item">
                <div className="info-label">Срочность</div>
                <div className="info-value">
                  {aiAnalysis ? (
                    <span className={`insight-badge${aiAnalysis.urgency === 'critical' || aiAnalysis.urgency === 'high' ? ' urgent' : ''}`}>
                      {aiAnalysis.urgencyLabel || getUrgencyLabel(aiAnalysis.urgency)}
                    </span>
                  ) : '—'}
                </div>
              </div>
              {aiAnalysis?.needs_escalation && (
                <div className="info-item">
                  <div className="info-label">Эскалация</div>
                  <div className="info-value">
                    <span className="insight-badge urgent">
                      {aiAnalysis.escalation_reason || 'Требуется'}
                    </span>
                  </div>
                </div>
              )}
              <div className="info-item">
                <div className="info-label">Категории</div>
                <div className="info-value">
                  {aiAnalysis?.categories?.length ? aiAnalysis.categories.map((cat, i) => (
                    <span key={i} className="insight-badge">{cat}</span>
                  )) : '—'}
                </div>
              </div>
            </div>

            <div className="info-section">
              <div className="info-section-title">Действия</div>
              <div className="info-item">
                <a
                  href={wbChannelLink}
                  className="info-link"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {wbChannelLinkLabel}
                </a>
              </div>
              {selectedInteraction?.nm_id && (
                <div className="info-item">
                  <a
                    href={`https://www.wildberries.ru/catalog/${selectedInteraction.nm_id}/detail.aspx`}
                    className="info-link"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Карточка товара на WB
                  </a>
                </div>
              )}
            </div>
                  </>
                )}
              </aside>

              <style>{`
                .analyze-btn {
                  background: transparent;
                  border: 1px solid var(--color-border-light);
                  border-radius: 4px;
                  padding: 2px 8px;
                  font-size: 12px;
                  cursor: pointer;
                  margin-left: 8px;
                  color: var(--color-text-secondary);
                  transition: all 0.2s;
                }
                .analyze-btn:hover:not(:disabled) {
                  background: var(--color-bg-tertiary);
                  color: var(--color-accent);
                }
                .analyze-btn:disabled {
                  opacity: 0.5;
                  cursor: not-allowed;
                }
                .info-section-title {
                  display: flex;
                  align-items: center;
                }
              `}</style>
            </div>
          )}
        </div>

        <nav className="bottom-nav">
          <button
            type="button"
            className={`bottom-nav-item ${activeWorkspace === 'messages' ? 'active' : ''}`}
            onClick={() => setActiveWorkspace('messages')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <span>Сообщения</span>
            {activeWorkspace !== 'messages' && urgentForNav > 0 && (
              <div className="bottom-nav-badge">{urgentForNav}</div>
            )}
          </button>
          <button
            type="button"
            className={`bottom-nav-item ${activeWorkspace === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveWorkspace('analytics')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            <span>Аналитика</span>
          </button>
          <button
            type="button"
            className={`bottom-nav-item ${activeWorkspace === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveWorkspace('settings')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span>Настройки</span>
          </button>
        </nav>
      </div>
    </div>
  );
}

export default App;
