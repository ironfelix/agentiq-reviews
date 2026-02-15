import type {
  InteractionQualityMetricsResponse,
  InteractionQualityHistoryResponse,
  InteractionOpsAlertsResponse,
  InteractionPilotReadinessResponse,
} from '../types';

const now = new Date().toISOString();
const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString();

export const DEMO_QUALITY_METRICS: InteractionQualityMetricsResponse = {
  period_days: 30,
  generated_from: thirtyDaysAgo,
  generated_to: now,
  totals: {
    replies_total: 98,
    draft_generated: 85,
    draft_cache_hits: 12,
    draft_accepted: 60,
    draft_edited: 15,
    reply_manual: 10,
    accept_rate: 0.71,
    edit_rate: 0.18,
    manual_rate: 0.12,
  },
  by_channel: [
    { channel: 'review', replies_total: 35, draft_generated: 30, draft_cache_hits: 5, draft_accepted: 22, draft_edited: 6, reply_manual: 3, accept_rate: 0.73, edit_rate: 0.2, manual_rate: 0.1 },
    { channel: 'question', replies_total: 40, draft_generated: 35, draft_cache_hits: 4, draft_accepted: 25, draft_edited: 7, reply_manual: 4, accept_rate: 0.71, edit_rate: 0.2, manual_rate: 0.11 },
    { channel: 'chat', replies_total: 23, draft_generated: 20, draft_cache_hits: 3, draft_accepted: 13, draft_edited: 2, reply_manual: 3, accept_rate: 0.65, edit_rate: 0.1, manual_rate: 0.15 },
  ],
  pipeline: {
    interactions_total: 120,
    needs_response_total: 22,
    responded_total: 98,
    by_channel: [
      { channel: 'review', interactions_total: 40, needs_response_total: 5, responded_total: 35 },
      { channel: 'question', interactions_total: 50, needs_response_total: 10, responded_total: 40 },
      { channel: 'chat', interactions_total: 30, needs_response_total: 7, responded_total: 23 },
    ],
  },
};

function generateHistorySeries(): InteractionQualityHistoryResponse['series'] {
  const series = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    const dayOfWeek = d.getDay();
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    const base = isWeekend ? 2 : 4;
    const replies = base + Math.floor(Math.random() * 3);
    const accepted = Math.round(replies * (0.65 + Math.random() * 0.15));
    const edited = Math.round((replies - accepted) * 0.6);
    const manual = replies - accepted - edited;
    series.push({
      date: d.toISOString().slice(0, 10),
      replies_total: replies,
      draft_accepted: accepted,
      draft_edited: edited,
      reply_manual: Math.max(0, manual),
      accept_rate: replies > 0 ? accepted / replies : 0,
      edit_rate: replies > 0 ? edited / replies : 0,
      manual_rate: replies > 0 ? Math.max(0, manual) / replies : 0,
    });
  }
  return series;
}

export const DEMO_QUALITY_HISTORY: InteractionQualityHistoryResponse = {
  period_days: 30,
  generated_from: thirtyDaysAgo,
  generated_to: now,
  series: generateHistorySeries(),
};

export const DEMO_OPS_ALERTS: InteractionOpsAlertsResponse = {
  generated_at: now,
  question_sla: {
    open_questions_total: 10,
    with_sla_total: 10,
    overdue_total: 2,
    due_soon_total: 3,
    oldest_overdue_minutes: 45,
  },
  quality_regression: {
    current_window_days: 7,
    previous_window_days: 7,
    current_manual_rate: 0.12,
    previous_manual_rate: 0.14,
    manual_rate_delta: -0.02,
    regression_detected: false,
    manual_rate_regression_threshold: 0.15,
  },
  alerts: [],
};

export const DEMO_PILOT_READINESS: InteractionPilotReadinessResponse = {
  generated_at: now,
  go_no_go: true,
  decision: 'go',
  summary: {
    total_checks: 8,
    passed: 7,
    warnings: 1,
    failed: 0,
    blockers: [],
  },
  thresholds: {
    required_channels: ['review', 'question'],
    recommended_channels: ['chat'],
    max_sync_age_minutes: 30,
    max_overdue_questions: 5,
    max_manual_rate: 0.6,
    max_open_backlog: 250,
    min_reply_activity: 1,
    reply_activity_window_days: 30,
  },
  checks: [
    { code: 'sync_status', title: 'Sync статус', status: 'pass', blocker: false, details: 'Demo mode — sync не требуется.' },
    { code: 'channel_coverage', title: 'Покрытие каналов', status: 'pass', blocker: false, details: 'Есть данные по обязательным каналам: review, question.' },
    { code: 'channel_coverage_recommended', title: 'Рекомендованные каналы', status: 'pass', blocker: false, details: 'Есть данные по каналу: chat.' },
    { code: 'question_sla_overdue', title: 'SLA вопросов', status: 'warn', blocker: false, details: 'Просрочено 2 вопросов (лимит 5).' },
    { code: 'quality_manual_rate', title: 'Manual rate', status: 'pass', blocker: false, details: 'Manual rate 12%.' },
    { code: 'quality_regression', title: 'Регрессия качества', status: 'pass', blocker: false, details: 'Регрессия не обнаружена.' },
    { code: 'open_backlog', title: 'Размер очереди', status: 'pass', blocker: false, details: 'Открытый backlog 22.' },
    { code: 'reply_activity', title: 'Активность ответов', status: 'pass', blocker: false, details: 'Ответов в окне: 98.' },
  ],
};
