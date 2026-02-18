// Chat Types
export interface Chat {
  id: number;
  seller_id: number;
  marketplace: string;
  channel_type?: 'review' | 'question' | 'chat' | string;
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
  source: string | null;
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

export interface SyncNowResponse {
  seller_id: number;
  sync_status: string;
  queued_scopes: string[];
  message: string;
}

// Settings types
export type PromoChannels = {
  chat_positive: boolean;
  chat_negative: boolean;
  chat_questions: boolean;
  reviews_positive: boolean;
  reviews_negative: boolean;
};

export type PromoCode = {
  id: string;
  code: string;
  discount_label: string;
  expires_label: string;
  scope_label: string;
  nm_ids: number[];
  sent_count: number;
  active: boolean;
  channels: PromoChannels;
  created_at: string;
  updated_at: string;
};

export type PromoConfig = {
  ai_offer_enabled: boolean;
  warn_reviews_enabled: boolean;
};

export type PromoSettingsResponse = {
  promo_codes: PromoCode[];
  config: PromoConfig;
};

export type PromoSettingsUpdateRequest = Partial<PromoSettingsResponse>;

export type AITone = 'formal' | 'friendly' | 'neutral';

export type AutoResponseChannel = 'review' | 'question' | 'chat';

export type ScenarioAction = 'auto' | 'draft' | 'block';

export type ScenarioConfig = {
  action: ScenarioAction;
  channels: string[];
  enabled: boolean;
};

export type AISettings = {
  tone: AITone;
  auto_replies_positive: boolean;
  ai_suggestions: boolean;
  auto_response_channels: AutoResponseChannel[];
  auto_response_nm_ids: number[];
  auto_response_scenarios: Record<string, ScenarioConfig>;
  auto_response_promo_on_5star: boolean;
};

export type AISettingsResponse = {
  settings: AISettings;
};

export type AISettingsUpdateRequest = AISettingsResponse;

export type PresetInfo = {
  name: string;
  label: string;
  description: string;
  channels: string[];
};

export type PresetsResponse = {
  presets: PresetInfo[];
};

export type ApplyPresetRequest = {
  preset: string;
};

export type ApplyPresetResponse = {
  preset: string;
  channels: string[];
  scenarios: Record<string, ScenarioConfig>;
};

// Message Types (matching backend MessageResponse)
export interface Message {
  id: number;
  chat_id: number;
  external_message_id: string;
  direction: 'incoming' | 'outgoing';
  text: string | null;
  attachments: unknown[] | null;
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

// Unified Interaction Types
export interface Interaction {
  id: number;
  seller_id: number;
  marketplace: string;
  channel: 'review' | 'question' | 'chat' | string;
  external_id: string;
  customer_id: string | null;
  order_id: string | null;
  nm_id: string | null;
  product_article: string | null;
  subject: string | null;
  text: string | null;
  rating: number | null;
  status: string;
  priority: string;
  needs_response: boolean;
  source: string;
  occurred_at: string | null;
  created_at: string;
  updated_at: string;
  extra_data: Record<string, unknown> | null;
}

export interface InteractionListResponse {
  interactions: Interaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface InteractionSyncResponse {
  seller_id: number;
  channel: string;
  source: string;
  fetched: number;
  created: number;
  updated: number;
  skipped: number;
}

export interface InteractionDraftResponse {
  interaction: Interaction;
  draft_text: string;
  intent: string | null;
  sentiment: string | null;
  sla_priority: string | null;
  recommendation_reason: string | null;
  source: string;
}

export interface InteractionReplyResponse {
  interaction: Interaction;
  result: string;
}

export interface InteractionQualityTotals {
  replies_total: number;
  draft_generated: number;
  draft_cache_hits: number;
  draft_accepted: number;
  draft_edited: number;
  reply_manual: number;
  accept_rate: number;
  edit_rate: number;
  manual_rate: number;
}

export interface InteractionQualityChannel {
  channel: string;
  replies_total: number;
  draft_generated: number;
  draft_cache_hits: number;
  draft_accepted: number;
  draft_edited: number;
  reply_manual: number;
  accept_rate: number;
  edit_rate: number;
  manual_rate: number;
}

export interface InteractionPipelineChannel {
  channel: string;
  interactions_total: number;
  needs_response_total: number;
  responded_total: number;
}

export interface InteractionQualityMetricsResponse {
  period_days: number;
  generated_from: string;
  generated_to: string;
  totals: InteractionQualityTotals;
  by_channel: InteractionQualityChannel[];
  pipeline: {
    interactions_total: number;
    needs_response_total: number;
    responded_total: number;
    by_channel: InteractionPipelineChannel[];
  };
}

export interface InteractionQualityHistoryPoint {
  date: string;
  replies_total: number;
  draft_accepted: number;
  draft_edited: number;
  reply_manual: number;
  accept_rate: number;
  edit_rate: number;
  manual_rate: number;
}

export interface InteractionQualityHistoryResponse {
  period_days: number;
  generated_from: string;
  generated_to: string;
  series: InteractionQualityHistoryPoint[];
}

export interface InteractionOpsAlert {
  code: string;
  severity: string;
  title: string;
  message: string;
}

export interface InteractionOpsAlertsResponse {
  generated_at: string;
  question_sla: Record<string, number | null>;
  quality_regression: Record<string, number | boolean>;
  alerts: InteractionOpsAlert[];
}

export interface InteractionPilotReadinessCheck {
  code: string;
  title: string;
  status: 'pass' | 'warn' | 'fail' | string;
  blocker: boolean;
  details: string;
}

export interface InteractionPilotReadinessSummary {
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  blockers: string[];
}

export interface InteractionPilotReadinessResponse {
  generated_at: string;
  go_no_go: boolean;
  decision: 'go' | 'no-go' | string;
  summary: InteractionPilotReadinessSummary;
  thresholds: Record<string, unknown>;
  checks: InteractionPilotReadinessCheck[];
}

export interface InteractionTimelineStep {
  interaction_id: number;
  channel: string;
  external_id: string;
  occurred_at: string | null;
  status: string;
  priority: string;
  needs_response: boolean;
  subject: string | null;
  match_reason: string;
  confidence: number;
  auto_action_allowed: boolean;
  action_mode: 'auto_allowed' | 'assist_only' | string;
  policy_reason: string;
  is_current?: boolean;
  wb_url?: string | null;
  last_reply_text?: string | null;
  last_ai_draft_text?: string | null;
}

export interface InteractionTimelineResponse {
  interaction_id: number;
  thread_scope: string;
  thread_key: Record<string, string | null>;
  channels_present: string[];
  steps: InteractionTimelineStep[];
}

export interface InteractionFilters {
  channel?: string;
  status?: string;
  priority?: string;
  needs_response?: boolean;
  marketplace?: string;
  source?: string;
  search?: string;
  page?: number;
  page_size?: number;
  include_total?: boolean;
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
  channel?: string;
  status?: string;
  has_unread?: boolean;
  sla_priority?: string;
  search?: string;
  page?: number;
  page_size?: number;
}
