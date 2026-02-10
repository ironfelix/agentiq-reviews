import { useState, useCallback, useEffect, useMemo } from 'react';
import { ChatList } from './components/ChatList';
import { ChatWindow } from './components/ChatWindow';
import { Login } from './components/Login';
import { chatApi, authApi, getToken } from './services/api';
import { usePolling } from './hooks/usePolling';
import type { Chat, Message, ChatFilters, AIAnalysis, User } from './types';

function parseAIAnalysis(jsonStr: string | null): AIAnalysis | null {
  if (!jsonStr) return null;
  try {
    const raw = JSON.parse(jsonStr);
    // Normalize format - backend returns objects for sentiment/urgency with label + boolean
    // Use first category as intent if no intent field
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
      categories: categories,
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

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [filters, setFilters] = useState<ChatFilters>({});
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'chat' | 'context'>('list');

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

  // Parse AI analysis from selected chat
  const aiAnalysis = useMemo(() => {
    return selectedChat ? parseAIAnalysis(selectedChat.ai_analysis_json) : null;
  }, [selectedChat]);

  // Handle login
  const handleLogin = useCallback((loggedInUser: User) => {
    setUser(loggedInUser);
  }, []);

  // Handle logout
  const handleLogout = useCallback(() => {
    authApi.logout();
    setUser(null);
    setChats([]);
    setSelectedChat(null);
    setMessages([]);
  }, []);

  // Handle marketplace connection
  const handleConnectMarketplace = useCallback(async (apiKey: string) => {
    setIsConnecting(true);
    try {
      const updatedUser = await authApi.connectMarketplace(apiKey);
      setUser(updatedUser);
      // Sync is triggered by backend, we'll poll for updates
    } finally {
      setIsConnecting(false);
    }
  }, []);

  // Fetch chats
  const fetchChats = useCallback(async () => {
    try {
      const response = await chatApi.getChats(filters);
      setChats(response.chats);
    } catch (error) {
      console.error('Failed to fetch chats:', error);
    } finally {
      setIsLoadingChats(false);
    }
  }, [filters]);

  // Poll for sync status updates when syncing
  useEffect(() => {
    if (!user || user.sync_status !== 'syncing') return;

    const pollInterval = setInterval(async () => {
      try {
        const updatedUser = await authApi.getMe();
        setUser(updatedUser);

        // Stop polling when sync completes
        if (updatedUser.sync_status !== 'syncing') {
          clearInterval(pollInterval);
          // Refresh chats after sync completes
          fetchChats();
        }
      } catch (error) {
        console.error('Failed to poll sync status:', error);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [user?.sync_status, fetchChats]);

  // Fetch messages for selected chat
  const fetchMessages = useCallback(async (chatId: number) => {
    try {
      setIsLoadingMessages(true);
      const response = await chatApi.getMessages(chatId);
      setMessages(response.messages);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  // Handle chat selection
  const handleSelectChat = useCallback(async (chat: Chat) => {
    setSelectedChat(chat);
    setMobileView('chat');
    fetchMessages(chat.id);

    // Mark as read if has unread messages
    if (chat.unread_count > 0) {
      try {
        const updatedChat = await chatApi.markAsRead(chat.id);
        setSelectedChat(updatedChat);
        setChats(prevChats =>
          prevChats.map(c => c.id === chat.id ? { ...c, unread_count: 0 } : c)
        );
      } catch (error) {
        console.error('Failed to mark as read:', error);
      }
    }
  }, [fetchMessages]);

  // Handle AI analysis
  const handleAnalyzeChat = useCallback(async () => {
    if (!selectedChat || isAnalyzing) return;

    setIsAnalyzing(true);
    try {
      const updatedChat = await chatApi.analyzeChat(selectedChat.id);
      setSelectedChat(updatedChat);
      setChats(prevChats =>
        prevChats.map(c => c.id === selectedChat.id ? updatedChat : c)
      );
    } catch (error) {
      console.error('Failed to analyze chat:', error);
      alert('Ошибка анализа чата');
    } finally {
      setIsAnalyzing(false);
    }
  }, [selectedChat, isAnalyzing]);

  // Handle send message
  const handleSendMessage = useCallback(async (text: string) => {
    if (!selectedChat) return;

    try {
      const newMessage = await chatApi.sendMessage(selectedChat.id, text);
      setMessages(prev => [...prev, newMessage]);
      setChats(prevChats =>
        prevChats.map(chat =>
          chat.id === selectedChat.id
            ? { ...chat, last_message_at: newMessage.sent_at }
            : chat
        )
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }, [selectedChat]);

  // Handle back to list (mobile)
  const handleBackToList = useCallback(() => {
    setMobileView('list');
  }, []);

  // Fetch chats when user changes (login/logout) or on initial load
  useEffect(() => {
    if (user) {
      fetchChats();
    }
  }, [user, fetchChats]);

  // Polling for new chats (every 10 seconds) - only when logged in
  usePolling(fetchChats, 10000, !!user);

  // Format date for display
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

  // Show loading while checking auth
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

  // Show login if not authenticated
  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Urgency/sentiment labels
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

  return (
    <div className="chat-center" data-mobile-view={mobileView}>
      <ChatList
        chats={chats}
        selectedChatId={selectedChat?.id || null}
        onSelectChat={handleSelectChat}
        onFiltersChange={setFilters}
        userName={user.name}
        onLogout={handleLogout}
        onConnectMarketplace={handleConnectMarketplace}
        isConnecting={isConnecting}
        isLoadingChats={isLoadingChats}
        hasApiCredentials={user.has_api_credentials}
        syncStatus={user.sync_status}
        syncError={user.sync_error}
        lastSyncAt={user.last_sync_at}
      />

      <ChatWindow
        chat={selectedChat}
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoadingMessages={isLoadingMessages}
        onBack={handleBackToList}
      />

      {/* RIGHT PANEL: Product Context */}
      <aside className="product-context">
        <div className="context-header">
          <div className="context-title">Товар</div>
          {selectedChat ? (
            <>
              <div className="product-name">{selectedChat.product_name || 'Чат покупателя'}</div>
              <div className="product-rating">{selectedChat.product_article ? `Арт. ${selectedChat.product_article}` : ''}</div>
              <div className="product-price"></div>
            </>
          ) : (
            <div className="product-name">Выберите чат</div>
          )}
        </div>

        {selectedChat && (
          <>
            <div className="info-section">
              <div className="info-section-title">Детали чата</div>
              <div className="info-item">
                <div className="info-label">Статус</div>
                <div className="info-value">
                  {selectedChat.chat_status === 'waiting' ? 'Ожидает ответа' :
                   selectedChat.chat_status === 'responded' ? 'Отвечено' :
                   selectedChat.chat_status === 'client-replied' ? 'Клиент ответил' :
                   selectedChat.chat_status || 'Открыт'}
                </div>
              </div>
              <div className="info-item">
                <div className="info-label">Последнее сообщение</div>
                <div className="info-value">{formatLastMessage(selectedChat.last_message_at)}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Непрочитанных</div>
                <div className="info-value">{selectedChat.unread_count}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Клиент</div>
                <div className="info-value">{selectedChat.customer_name || '—'}</div>
              </div>
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
                <a href="#" className="info-link" onClick={(e) => e.preventDefault()}>
                  Открыть чат на WB
                </a>
              </div>
              <div className="info-item">
                <a href="#" className="info-link" onClick={(e) => e.preventDefault()}>
                  Посмотреть все чаты клиента
                </a>
              </div>
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
  );
}

export default App;
