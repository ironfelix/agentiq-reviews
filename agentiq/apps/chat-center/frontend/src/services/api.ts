import axios from 'axios';
import type { Chat, Message, ChatsResponse, MessagesResponse, ChatFilters, AuthResponse, LoginRequest, RegisterRequest, User } from '../types';

// API base URL - computed at runtime to support both dev and prod
// Uses indirect window access to prevent build-time optimization
const api = axios.create({
  headers: { 'Content-Type': 'application/json' },
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
const TOKEN_KEY = 'auth_token';

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token);
export const removeToken = (): void => localStorage.removeItem(TOKEN_KEY);

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      window.location.reload();
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

export default api;
