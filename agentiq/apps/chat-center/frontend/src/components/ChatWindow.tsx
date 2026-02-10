import { useState, useEffect, useRef } from 'react';
import type { Chat, Message } from '../types';

interface ChatWindowProps {
  chat: Chat | null;
  messages: Message[];
  onSendMessage: (text: string) => Promise<void>;
  isLoadingMessages: boolean;
  onBack?: () => void;
  onCloseChat?: (chatId: number) => Promise<void>;
  onReopenChat?: (chatId: number) => Promise<void>;
}

export function ChatWindow({
  chat,
  messages,
  onSendMessage,
  isLoadingMessages,
  onBack,
  onCloseChat,
  onReopenChat,
}: ChatWindowProps) {
  const [messageText, setMessageText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [showCopied, setShowCopied] = useState(false);
  const [isClosingChat, setIsClosingChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Check if chat is closed
  const isChatClosed = chat?.chat_status === 'closed';

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
  const handleSend = async () => {
    if (!messageText.trim() || isSending) return;

    setIsSending(true);
    try {
      await onSendMessage(messageText.trim());
      setMessageText('');
    } catch (error) {
      console.error('Failed to send message:', error);
      alert('Ошибка отправки сообщения');
    } finally {
      setIsSending(false);
    }
  };

  // Use AI suggestion text as message
  const handleUseAISuggestion = () => {
    if (chat?.ai_suggestion_text) {
      setMessageText(chat.ai_suggestion_text);
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

  // Auto-resize textarea on input
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessageText(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

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

  return (
    <main className="chat-window">
      <div className="chat-header">
        <button className="chat-header-back" onClick={onBack}>&#8592;</button>
        <div className="chat-header-info">
          <h2>{chat.customer_name || 'Клиент'}</h2>
          <div className="chat-header-meta">{headerMeta}</div>
        </div>
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

      {/* AI Suggestion - show status based on analysis state */}
      {chat.ai_suggestion_text ? (
        <div className="ai-suggestion" onClick={handleUseAISuggestion} style={{ cursor: 'pointer', position: 'relative' }}>
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
          <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
        </div>
      ) : chat.unread_count > 0 ? (
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
            Анализируется...
          </div>
        </div>
      ) : null}

      {/* Input */}
      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            id="chatInput"
            value={messageText}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Напишите ответ..."
            rows={1}
            disabled={isSending}
            style={{ overflow: 'hidden', resize: 'none' }}
          />
          <button
            className="btn-send"
            onClick={handleSend}
            disabled={!messageText.trim() || isSending}
          >
            {isSending ? '...' : '\u2192'}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </main>
  );
}
