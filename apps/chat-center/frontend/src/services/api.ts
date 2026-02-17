import axios from 'axios';
import type {
  AuthResponse,
  AISettingsResponse,
  AISettingsUpdateRequest,
  Chat,
  ChatFilters,
  ChatsResponse,
  Interaction,
  InteractionDraftResponse,
  InteractionFilters,
  InteractionOpsAlertsResponse,
  InteractionPilotReadinessResponse,
  InteractionTimelineResponse,
  InteractionQualityHistoryResponse,
  InteractionListResponse,
  InteractionQualityMetricsResponse,
  InteractionReplyResponse,
  InteractionSyncResponse,
  LoginRequest,
  Message,
  MessagesResponse,
  PromoSettingsResponse,
  PromoSettingsUpdateRequest,
  RegisterRequest,
  SyncNowResponse,
  User,
} from '../types';

// API base URL - computed at runtime to support both dev and prod
// Uses indirect window access to prevent build-time optimization
const api = axios.create({
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // send httpOnly cookies with requests
});

// Set baseURL at runtime (not build time) using request interceptor
api.interceptors.request.use((config) => {
  if (!config.baseURL) {
    const loc = window['location']; // indirect access prevents minifier optimization
    const hostname = loc.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      config.baseURL = 'http://localhost:8001/api';
    } else {
      config.baseURL = '/api';
    }
  }
  return config;
});

// Auth token management
// In production: httpOnly cookie handles auth (set by backend, sent automatically).
// In development (localhost): localStorage fallback for cross-origin requests.
const TOKEN_KEY = 'auth_token';

function _isLocalDev(): boolean {
  const loc = window['location'];
  return loc.hostname === 'localhost' || loc.hostname === '127.0.0.1';
}

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string): void => {
  // Always store — needed for isAuthenticated() check and dev Authorization header
  localStorage.setItem(TOKEN_KEY, token);
};
export const removeToken = (): void => localStorage.removeItem(TOKEN_KEY);

api.interceptors.request.use((config) => {
  // In dev (cross-origin), send Authorization header since cookies won't work.
  // In prod (same-origin), httpOnly cookie is sent automatically.
  if (_isLocalDev()) {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 errors — show message before redirect to login
let _sessionExpiredHandled = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !_sessionExpiredHandled) {
      _sessionExpiredHandled = true;
      removeToken();
      // Show brief toast so user understands why they're being redirected
      const toast = document.createElement('div');
      toast.textContent = 'Сессия истекла. Перенаправляем на вход\u2026';
      toast.style.cssText =
        'position:fixed;top:20px;left:50%;transform:translateX(-50%);' +
        'background:#333;color:#fff;padding:12px 24px;border-radius:8px;' +
        'z-index:99999;font-family:Inter,sans-serif;font-size:14px;';
      document.body.appendChild(toast);
      setTimeout(() => window.location.reload(), 1500);
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/login', data);
    setToken(response.data.access_token);
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/register', data);
    setToken(response.data.access_token);
    return response.data;
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },

  logout: (): void => {
    removeToken();
  },

  isAuthenticated: (): boolean => {
    return !!getToken();
  },

  connectMarketplace: async (apiKey: string): Promise<User> => {
    const response = await api.post<User>('/auth/connect-marketplace', {
      api_key: apiKey,
    });
    return response.data;
  },

  triggerSync: async (options?: { includeInteractions?: boolean }): Promise<SyncNowResponse> => {
    const response = await api.post<SyncNowResponse>('/auth/sync-now', {
      include_interactions: options?.includeInteractions ?? true,
    });
    return response.data;
  },

  seedDemo: async (): Promise<{ created: number; message: string }> => {
    const response = await api.post<{ created: number; message: string }>('/auth/seed-demo');
    return response.data;
  },
};

// Chat API
export const chatApi = {
  getChats: async (filters?: ChatFilters): Promise<ChatsResponse> => {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.has_unread !== undefined) params.append('has_unread', String(filters.has_unread));
    if (filters?.sla_priority) params.append('sla_priority', filters.sla_priority);
    if (filters?.search) params.append('search', filters.search);
    if (filters?.page) params.append('page', String(filters.page));
    if (filters?.page_size) params.append('page_size', String(filters.page_size));

    const response = await api.get<ChatsResponse>(`/chats?${params.toString()}`);
    return response.data;
  },

  getChat: async (chatId: number): Promise<Chat> => {
    const response = await api.get<Chat>(`/chats/${chatId}`);
    return response.data;
  },

  getMessages: async (chatId: number): Promise<MessagesResponse> => {
    const response = await api.get<MessagesResponse>(`/messages/chat/${chatId}`);
    return response.data;
  },

  sendMessage: async (chatId: number, text: string): Promise<Message> => {
    const response = await api.post<Message>('/messages', {
      chat_id: chatId,
      text,
    });
    return response.data;
  },

  markAsRead: async (chatId: number): Promise<Chat> => {
    const response = await api.post<Chat>(`/chats/${chatId}/mark-read`);
    return response.data;
  },

  analyzeChat: async (chatId: number): Promise<Chat> => {
    const response = await api.post<Chat>(`/chats/${chatId}/analyze`);
    return response.data;
  },

  closeChat: async (chatId: number): Promise<Chat> => {
    const response = await api.post<Chat>(`/chats/${chatId}/close`);
    return response.data;
  },

  reopenChat: async (chatId: number): Promise<Chat> => {
    const response = await api.post<Chat>(`/chats/${chatId}/reopen`);
    return response.data;
  },
};

// Unified interactions API
export const interactionsApi = {
  getInteractions: async (filters?: InteractionFilters): Promise<InteractionListResponse> => {
    const params = new URLSearchParams();
    params.append('include_total', String(filters?.include_total ?? false));
    if (filters?.channel) params.append('channel', filters.channel);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.priority) params.append('priority', filters.priority);
    if (filters?.needs_response !== undefined) {
      params.append('needs_response', String(filters.needs_response));
    }
    if (filters?.marketplace) params.append('marketplace', filters.marketplace);
    if (filters?.source) params.append('source', filters.source);
    if (filters?.search) params.append('search', filters.search);
    if (filters?.page) params.append('page', String(filters.page));
    if (filters?.page_size) params.append('page_size', String(filters.page_size));

    const response = await api.get<InteractionListResponse>(`/interactions?${params.toString()}`);
    return response.data;
  },

  getInteraction: async (interactionId: number): Promise<Interaction> => {
    const response = await api.get<Interaction>(`/interactions/${interactionId}`);
    return response.data;
  },

  getTimeline: async (
    interactionId: number,
    options?: { maxItems?: number; productWindowDays?: number }
  ): Promise<InteractionTimelineResponse> => {
    const query = new URLSearchParams();
    if (options?.maxItems) query.append('max_items', String(options.maxItems));
    if (options?.productWindowDays) query.append('product_window_days', String(options.productWindowDays));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.get<InteractionTimelineResponse>(
      `/interactions/${interactionId}/timeline${suffix}`
    );
    return response.data;
  },

  syncReviews: async (params?: {
    nm_id?: number;
    only_unanswered?: boolean;
    max_items?: number;
    page_size?: number;
  }): Promise<InteractionSyncResponse> => {
    const query = new URLSearchParams();
    if (params?.nm_id) query.append('nm_id', String(params.nm_id));
    if (params?.only_unanswered !== undefined) {
      query.append('only_unanswered', String(params.only_unanswered));
    }
    if (params?.max_items) query.append('max_items', String(params.max_items));
    if (params?.page_size) query.append('page_size', String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.post<InteractionSyncResponse>(`/interactions/sync/reviews${suffix}`);
    return response.data;
  },

  syncQuestions: async (params?: {
    nm_id?: number;
    only_unanswered?: boolean;
    max_items?: number;
    page_size?: number;
  }): Promise<InteractionSyncResponse> => {
    const query = new URLSearchParams();
    if (params?.nm_id) query.append('nm_id', String(params.nm_id));
    if (params?.only_unanswered !== undefined) {
      query.append('only_unanswered', String(params.only_unanswered));
    }
    if (params?.max_items) query.append('max_items', String(params.max_items));
    if (params?.page_size) query.append('page_size', String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.post<InteractionSyncResponse>(`/interactions/sync/questions${suffix}`);
    return response.data;
  },

  syncChats: async (params?: { max_items?: number }): Promise<InteractionSyncResponse> => {
    const query = new URLSearchParams();
    if (params?.max_items) query.append('max_items', String(params.max_items));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.post<InteractionSyncResponse>(`/interactions/sync/chats${suffix}`);
    return response.data;
  },

  generateDraft: async (
    interactionId: number,
    options?: { forceRegenerate?: boolean }
  ): Promise<InteractionDraftResponse> => {
    const response = await api.post<InteractionDraftResponse>(
      `/interactions/${interactionId}/ai-draft`,
      { force_regenerate: Boolean(options?.forceRegenerate) }
    );
    return response.data;
  },

  reply: async (interactionId: number, text: string): Promise<InteractionReplyResponse> => {
    const response = await api.post<InteractionReplyResponse>(`/interactions/${interactionId}/reply`, { text });
    return response.data;
  },

  getQualityMetrics: async (options?: {
    days?: number;
    channel?: string;
  }): Promise<InteractionQualityMetricsResponse> => {
    const query = new URLSearchParams();
    if (options?.days) query.append('days', String(options.days));
    if (options?.channel) query.append('channel', options.channel);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.get<InteractionQualityMetricsResponse>(
      `/interactions/metrics/quality${suffix}`
    );
    return response.data;
  },

  getQualityHistory: async (options?: {
    days?: number;
    channel?: string;
  }): Promise<InteractionQualityHistoryResponse> => {
    const query = new URLSearchParams();
    if (options?.days) query.append('days', String(options.days));
    if (options?.channel) query.append('channel', options.channel);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.get<InteractionQualityHistoryResponse>(
      `/interactions/metrics/quality-history${suffix}`
    );
    return response.data;
  },

  getOpsAlerts: async (): Promise<InteractionOpsAlertsResponse> => {
    const response = await api.get<InteractionOpsAlertsResponse>(
      '/interactions/metrics/ops-alerts'
    );
    return response.data;
  },

  getPilotReadiness: async (options?: {
    min_reply_activity?: number;
    reply_activity_window_days?: number;
  }): Promise<InteractionPilotReadinessResponse> => {
    const query = new URLSearchParams();
    if (typeof options?.min_reply_activity === 'number') {
      query.append('min_reply_activity', String(options.min_reply_activity));
    }
    if (typeof options?.reply_activity_window_days === 'number') {
      query.append('reply_activity_window_days', String(options.reply_activity_window_days));
    }
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const response = await api.get<InteractionPilotReadinessResponse>(
      `/interactions/metrics/pilot-readiness${suffix}`
    );
    return response.data;
  },
};

// Settings API
export const settingsApi = {
  getPromoSettings: async (): Promise<PromoSettingsResponse> => {
    const response = await api.get<PromoSettingsResponse>('/settings/promo');
    return response.data;
  },

  updatePromoSettings: async (payload: PromoSettingsUpdateRequest): Promise<PromoSettingsResponse> => {
    const response = await api.put<PromoSettingsResponse>('/settings/promo', payload);
    return response.data;
  },

  getAISettings: async (): Promise<AISettingsResponse> => {
    const response = await api.get<AISettingsResponse>('/settings/ai');
    return response.data;
  },

  updateAISettings: async (payload: AISettingsUpdateRequest): Promise<AISettingsResponse> => {
    const response = await api.put<AISettingsResponse>('/settings/ai', payload);
    return response.data;
  },
};

export default api;
