import { useState, useEffect, useRef, useCallback } from 'react';
import type { Chat, Message } from '../types';

type ReplyStatus = 'idle' | 'sending' | 'sent' | 'error' | 'rejected';

interface GuardrailViolation {
  type: string;
  severity: string;
  message: string;
  phrase?: string;
  category?: string;
}

interface ReplyErrorInfo {
  message: string;
  violations?: GuardrailViolation[];
  httpStatus?: number;
}

interface ChatWindowProps {
  chat: Chat | null;
  messages: Message[];
  onSendMessage: (text: string) => Promise<void>;
  isLoadingMessages: boolean;
  onBack?: () => void;
  onCloseChat?: (chatId: number) => Promise<void>;
  onReopenChat?: (chatId: number) => Promise<void>;
  onRegenerateAI?: (chatId: number) => Promise<void>;
  showLifecycleActions?: boolean;
}

/** Character limits by channel type */
function getCharLimits(channelType: string | undefined): { min: number; max: number } {
  if (channelType === 'chat') return { min: 1, max: 1000 };
  // review and question: WB API accepts 2-5000
  return { min: 2, max: 5000 };
}

/** Parse axios error into a user-friendly structure */
function parseReplyError(error: unknown): ReplyErrorInfo {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { status?: number; data?: unknown } };
    const status = axiosError.response?.status;
    const data = axiosError.response?.data as Record<string, unknown> | undefined;

    if (status === 422 && data?.detail) {
      const detail = data.detail as Record<string, unknown>;
      return {
        message: (typeof detail.summary === 'string' && detail.summary)
          || (typeof detail.message === 'string' && detail.message)
          || 'Текст заблокирован guardrails',
        violations: Array.isArray(detail.violations) ? detail.violations as GuardrailViolation[] : undefined,
        httpStatus: 422,
      };
    }

    if (status === 502) {
      const detail = data?.detail;
      const msg = typeof detail === 'string' ? detail : 'Ошибка отправки через WB API';
      return { message: msg, httpStatus: 502 };
    }

    if (status === 400) {
      const detail = data?.detail;
      const msg = typeof detail === 'string' ? detail : 'Некорректный запрос';
      return { message: msg, httpStatus: 400 };
    }

    return {
      message: `Ошибка сервера (${status || 'unknown'})`,
      httpStatus: status,
    };
  }

  return { message: 'Не удалось отправить ответ. Проверьте подключение.' };
}

export function ChatWindow({
  chat,
  messages,
  onSendMessage,
  isLoadingMessages,
  onBack,
  onCloseChat,
  onReopenChat,
  onRegenerateAI,
  showLifecycleActions = true,
}: ChatWindowProps) {
  const [messageText, setMessageText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [replyStatus, setReplyStatus] = useState<ReplyStatus>('idle');
  const [replyError, setReplyError] = useState<ReplyErrorInfo | null>(null);
  const [showCopied, setShowCopied] = useState(false);
  const [isClosingChat, setIsClosingChat] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Track whether the current text originated from AI draft
  const [usedAIDraft, setUsedAIDraft] = useState(false);

  // Derive channel-aware character limits
  const charLimits = getCharLimits(chat?.channel_type);
  const textLength = messageText.length;
  const isOverLimit = textLength > charLimits.max;
  const isUnderMin = textLength > 0 && textLength < charLimits.min;

  // Check if interaction was already responded
  const isResponded = chat?.chat_status === 'responded' || chat?.chat_status === 'auto-response';
  const isChatClosed = chat?.chat_status === 'closed';

  // Reset state when switching between chats
  useEffect(() => {
    setMessageText('');
    setReplyStatus('idle');
    setReplyError(null);
    setUsedAIDraft(false);
    setPendingFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [chat?.id]);

  // Handle close/reopen chat
  const handleCloseOrReopenChat = async () => {
    if (!chat || isClosingChat) return;
    setIsClosingChat(true);
    try {
      if (isChatClosed) {
        await onReopenChat?.(chat.id);
      } else {
        await onCloseChat?.(chat.id);
      }
    } catch (error) {
      console.error('Failed to close/reopen chat:', error);
      alert(isChatClosed ? 'Ошибка открытия чата' : 'Ошибка закрытия чата');
    } finally {
      setIsClosingChat(false);
    }
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle send message
  const handleSend = useCallback(async () => {
    if ((!messageText.trim() && pendingFiles.length === 0) || isSending) return;

    // Client-side validation
    const trimmedText = messageText.trim();
    if (trimmedText.length < charLimits.min) {
      setReplyError({
        message: `Минимальная длина ответа: ${charLimits.min} символов`,
      });
      setReplyStatus('error');
      return;
    }
    if (trimmedText.length > charLimits.max) {
      setReplyError({
        message: `Максимальная длина ответа: ${charLimits.max} символов`,
      });
      setReplyStatus('error');
      return;
    }

    setIsSending(true);
    setReplyStatus('sending');
    setReplyError(null);

    try {
      const textBody = trimmedText;
      const filesSuffix = pendingFiles.length > 0
        ? pendingFiles.map((file) => `[Файл: ${file.name}]`).join(' ')
        : '';
      const outboundText = [textBody, filesSuffix].filter(Boolean).join('\n');

      await onSendMessage(outboundText);
      setMessageText('');
      setPendingFiles([]);
      setReplyStatus('sent');
      setUsedAIDraft(false);

      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorInfo = parseReplyError(error);
      setReplyError(errorInfo);
      setReplyStatus(errorInfo.httpStatus === 422 ? 'rejected' : 'error');
      // Keep text in textarea for retry
    } finally {
      setIsSending(false);
    }
  }, [messageText, pendingFiles, isSending, charLimits, onSendMessage]);

  const handlePickFiles = () => {
    fileInputRef.current?.click();
  };

  const handleFilesSelected = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setPendingFiles((prev) => [...prev, ...files].slice(0, 3));
    event.target.value = '';
  };

  const handleRemovePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Use AI suggestion text as message
  const handleUseAISuggestion = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (chat?.ai_suggestion_text) {
      setMessageText(chat.ai_suggestion_text);
      setUsedAIDraft(true);
      setReplyStatus('idle');
      setReplyError(null);
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 2000);
      // Auto-resize textarea and scroll
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
          textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
          textareaRef.current.focus();
        }
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 50);
    }
  };

  // Regenerate AI suggestion
  const handleRegenerateAI = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!chat || isRegenerating) return;
    setIsRegenerating(true);
    try {
      await onRegenerateAI?.(chat.id);
    } catch (error) {
      console.error('Failed to regenerate AI:', error);
    } finally {
      setIsRegenerating(false);
    }
  };

  // Auto-resize textarea on input
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessageText(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';

    // Clear errors when user edits text
    if (replyStatus === 'error' || replyStatus === 'rejected') {
      setReplyStatus('idle');
      setReplyError(null);
    }
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  // Dismiss success status
  const handleDismissStatus = useCallback(() => {
    setReplyStatus('idle');
    setReplyError(null);
  }, []);

  // Get time string (HH:MM)
  const getTimeString = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  // Format date for date separator (e.g. "24 сентября 2025 г.")
  const getDateLabel = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('ru-RU', {
        day: 'numeric', month: 'long', year: 'numeric'
      });
    } catch {
      return '';
    }
  };

  // Get date key for grouping (YYYY-MM-DD)
  const getDateKey = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toISOString().slice(0, 10);
    } catch {
      return '';
    }
  };

  // Get author name for display
  const getAuthorName = (message: Message) => {
    if (message.direction === 'outgoing') return 'Продавец';
    if (message.author_type === 'customer') return chat?.customer_name || 'Клиент';
    return 'Клиент';
  };

  if (!chat) {
    return (
      <main className="chat-window">
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: 'var(--color-text-tertiary)'
        }}>
          <svg style={{ width: '64px', height: '64px', marginBottom: '16px', opacity: 0.3 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p>Выберите чат для просмотра</p>
        </div>
      </main>
    );
  }

  // Build header meta: "Wildberries · Арт. 335542810 · Кран шаровой ВР/ВР 1/2"
  const headerMeta = [
    chat.marketplace === 'wildberries' ? 'Wildberries' : chat.marketplace,
    chat.product_article ? `Арт. ${chat.product_article}` : null,
    chat.product_name || 'Чат покупателя'
  ].filter(Boolean).join(' · ');

  // Build messages with date separators
  const renderMessages = () => {
    const elements: React.ReactNode[] = [];
    let lastDateKey = '';

    messages.forEach((message) => {
      // Insert date separator if day changed
      const dateKey = getDateKey(message.sent_at);
      if (dateKey && dateKey !== lastDateKey) {
        lastDateKey = dateKey;
        elements.push(
          <div key={`date-${dateKey}`} className="date-separator">
            <span>{getDateLabel(message.sent_at)}</span>
          </div>
        );
      }

      const isIncoming = message.direction === 'incoming';
      const authorName = getAuthorName(message);
      // auto-tag only for authors containing "[авто]" (auto-responses)
      const hasAutoTag = authorName.includes('[авто]');

      elements.push(
        <div key={message.id} className={`message ${isIncoming ? 'customer' : 'seller'}`}>
          <div className="message-header">
            <span className={`message-author${hasAutoTag ? ' auto-tag' : ''}`}>
              {authorName}
            </span>
            <span className="message-time">{getTimeString(message.sent_at)}</span>
          </div>
          <div className="message-content">{message.text}</div>
        </div>
      );
    });

    return elements;
  };

  // Determine character counter color
  const getCharCounterClass = () => {
    if (isOverLimit) return 'reply-char-counter over-limit';
    if (textLength > charLimits.max * 0.9) return 'reply-char-counter near-limit';
    if (isUnderMin) return 'reply-char-counter under-min';
    return 'reply-char-counter';
  };

  // Determine if send button should be disabled
  const isSendDisabled =
    isSending ||
    (!messageText.trim() && pendingFiles.length === 0) ||
    isOverLimit ||
    isUnderMin;

  // Determine the send button label
  const getSendButtonContent = () => {
    if (isSending) {
      return (
        <span className="reply-send-spinner" />
      );
    }
    return '\u2192';
  };

  // Source label for AI draft tracking
  const getSourceLabel = () => {
    if (!usedAIDraft) return null;
    if (messageText === chat.ai_suggestion_text) return 'AI-черновик (без изменений)';
    return 'AI-черновик (отредактирован)';
  };

  const sourceLabel = getSourceLabel();

  return (
    <main className="chat-window">
      <div className="chat-header">
        <button className="chat-header-back" onClick={onBack}>&#8592;</button>
        <div className="chat-header-info">
          <h2>{chat.customer_name || 'Клиент'}</h2>
          <div className="chat-header-meta">{headerMeta}</div>
        </div>
        {showLifecycleActions && (
          <div className="chat-header-actions">
            <button
              className={`header-action-btn ${isChatClosed ? 'reopen' : 'close'}`}
              title={isChatClosed ? 'Открыть чат' : 'Закрыть чат'}
              onClick={handleCloseOrReopenChat}
              disabled={isClosingChat}
              style={{
                fontSize: '12px',
                padding: '6px 12px',
                background: isChatClosed ? 'var(--color-success, #4ecb71)' : 'var(--color-text-tertiary)',
                color: 'white',
                borderRadius: '4px',
                opacity: isClosingChat ? 0.6 : 1,
              }}
            >
              {isClosingChat ? '...' : (isChatClosed ? 'Открыть' : 'Закрыть')}
            </button>
          </div>
        )}
      </div>

      {/* Product badge */}
      <div className="product-chat-badge" id="productBadge" style={{ display: 'none' }}></div>

      <div className="chat-messages" id="chatMessages">
        {isLoadingMessages ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <div style={{
              border: '2px solid var(--color-border-medium)',
              borderTop: '2px solid var(--color-accent)',
              borderRadius: '50%', width: '32px', height: '32px',
              animation: 'spin 1s linear infinite'
            }}></div>
          </div>
        ) : messages.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--color-text-tertiary)'
          }}>
            Нет сообщений
          </div>
        ) : (
          renderMessages()
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* AI Suggestion - context-aware based on chat status */}
      {(isResponded && replyStatus !== 'sent') ? (
        /* Seller already responded -- show the sent reply and hide input */
        <div className="ai-suggestion" style={{ opacity: 0.6, cursor: 'default' }}>
          <div className="ai-suggestion-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-success, #4ecb71)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Вы ответили
          </div>
          <div className="ai-suggestion-text" style={{ color: 'var(--color-text-tertiary)' }}>
            Рекомендация появится, когда покупатель напишет снова
          </div>
        </div>
      ) : chat.ai_suggestion_text ? (
        <div className="ai-suggestion">
          <div className="ai-suggestion-header">
            <div className="ai-suggestion-label">
              AI Рекомендация
              {showCopied && (
                <span style={{
                  marginLeft: '8px',
                  padding: '2px 8px',
                  background: 'var(--color-accent)',
                  color: 'white',
                  borderRadius: '4px',
                  fontSize: '10px',
                  fontWeight: 500,
                }}>
                  Скопировано
                </span>
              )}
            </div>
            <button
              className="ai-regenerate-btn"
              onClick={handleRegenerateAI}
              disabled={isRegenerating}
              title="Сгенерировать другой ответ"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={isRegenerating ? { animation: 'spin 1s linear infinite' } : undefined}>
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
              </svg>
            </button>
          </div>
          <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
          <button className="ai-use-btn" onClick={handleUseAISuggestion}>
            Использовать AI-черновик
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </button>
        </div>
      ) : (chat.unread_count > 0 || isRegenerating) ? (
        <div className="ai-suggestion ai-suggestion--pending">
          <div className="ai-suggestion-label">AI Рекомендация</div>
          <div className="ai-suggestion-text" style={{ color: 'var(--color-text-tertiary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              display: 'inline-block',
              width: '12px',
              height: '12px',
              border: '2px solid var(--color-border-medium)',
              borderTop: '2px solid var(--color-accent)',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }} />
            {isRegenerating ? 'Генерация нового ответа...' : 'Анализируется...'}
          </div>
        </div>
      ) : null}

      {/* Reply status feedback */}
      {replyStatus === 'sent' && (
        <div className="reply-status-bar reply-status-success">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <span>Ответ отправлен</span>
          <button className="reply-status-dismiss" onClick={handleDismissStatus} type="button">
            Закрыть
          </button>
        </div>
      )}

      {(replyStatus === 'error' || replyStatus === 'rejected') && replyError && (
        <div className={`reply-status-bar ${replyStatus === 'rejected' ? 'reply-status-rejected' : 'reply-status-error'}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <div className="reply-error-content">
            <span className="reply-error-message">{replyError.message}</span>
            {replyError.violations && replyError.violations.length > 0 && (
              <ul className="reply-violations-list">
                {replyError.violations.map((v, i) => (
                  <li key={i} className="reply-violation-item">
                    {v.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button className="reply-status-dismiss" onClick={handleDismissStatus} type="button">
            Закрыть
          </button>
        </div>
      )}

      {/* Input area -- hidden when already responded and no active reply attempt */}
      {!(isResponded && replyStatus !== 'error' && replyStatus !== 'rejected') && (
        <div className="chat-input-container">
          {pendingFiles.length > 0 && (
            <div className="pending-files-row">
              {pendingFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="pending-file-chip">
                  <span>{file.name}</span>
                  <button type="button" onClick={() => handleRemovePendingFile(index)}>x</button>
                </div>
              ))}
            </div>
          )}

          {/* Source label when using AI draft */}
          {sourceLabel && (
            <div className="reply-source-label">
              {sourceLabel}
            </div>
          )}

          <div className="chat-input-wrapper">
            <button
              type="button"
              className="btn-attach"
              onClick={handlePickFiles}
              title="Загрузить файл"
              disabled={isSending}
            >
              +
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: 'none' }}
              onChange={handleFilesSelected}
            />
            <textarea
              ref={textareaRef}
              className={`chat-input${isOverLimit ? ' input-over-limit' : ''}`}
              id="chatInput"
              value={messageText}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Написать ответ..."
              rows={1}
              disabled={isSending}
              style={{ overflow: 'hidden', resize: 'none' }}
            />
            <button
              className="btn-send"
              onClick={handleSend}
              disabled={isSendDisabled}
              title="Отправить (Ctrl+Enter)"
            >
              {getSendButtonContent()}
            </button>
          </div>

          {/* Character counter row */}
          <div className="reply-input-footer">
            {textLength > 0 && (
              <span className={getCharCounterClass()}>
                {textLength}/{charLimits.max}
              </span>
            )}
            <span className="reply-shortcut-hint">Ctrl+Enter</span>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </main>
  );
}
