// Chat Types
export interface Chat {
  id: number;
  seller_id: number;
  marketplace: string;
  marketplace_chat_id: string;
  order_id: string | null;
  product_id: string | null;
  customer_name: string | null;
  customer_id: string | null;
  status: string;
  unread_count: number;
  last_message_at: string | null;
  first_message_at: string | null;
  sla_deadline_at: string | null;
  sla_priority: 'urgent' | 'high' | 'normal' | 'low';
  ai_suggestion_text: string | null;
  ai_analysis_json: string | null;
  last_message_preview: string | null;
  product_name: string | null;
  product_article: string | null;
  chat_status: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

// Parsed AI analysis (from ai_analysis_json) - matches backend AIAnalyzer format
export interface AIAnalysis {
  intent: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  sentimentLabel?: string | null;  // Russian label like "Негативная"
  urgency: 'low' | 'normal' | 'high' | 'critical';
  urgencyLabel?: string | null;    // Russian label like "Высокая"
  categories: string[];
  recommendation: string | null;
  recommendation_reason?: string;
  needs_escalation: boolean;
  escalation_reason?: string;
  sla_priority: string;
  analyzed_at: string;
}

// Auth types
export interface User {
  id: number;
  email: string;
  name: string;
  marketplace: string;
  is_active: boolean;
  is_verified: boolean;
  has_api_credentials?: boolean;
  last_sync_at?: string | null;
  sync_status?: 'idle' | 'syncing' | 'success' | 'error' | null;
  sync_error?: string | null;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  seller: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  marketplace?: string;
}

// Message Types (matching backend MessageResponse)
export interface Message {
  id: number;
  chat_id: number;
  external_message_id: string;
  direction: 'incoming' | 'outgoing';
  text: string | null;
  attachments: any[] | null;
  author_type: string | null;
  author_id: string | null;
  status: string;
  is_read: boolean;
  read_at: string | null;
  sent_at: string;
  created_at: string;
}

// API Response Types
export interface ChatsResponse {
  chats: Chat[];
  total: number;
  page: number;
  page_size: number;
}

export interface MessagesResponse {
  messages: Message[];
  total: number;
}

// AI Suggestion type (used by AIPanel)
export interface AISuggestion {
  text: string;
  intent: string;
  confidence: number;
  warnings: string[];
}

// Filter Types
export interface ChatFilters {
  status?: string;
  has_unread?: boolean;
  sla_priority?: string;
  search?: string;
  page?: number;
  page_size?: number;
}
