import { useState } from 'react';
import { authApi } from '../services/api';
import type { User } from '../types';

interface LoginProps {
  onLogin: (user: User) => void;
}

export function Login({ onLogin }: LoginProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isRegister) {
        const response = await authApi.register({ email, password, name });
        onLogin(response.seller);
      } else {
        const response = await authApi.login({ email, password });
        onLogin(response.seller);
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Ошибка авторизации';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoMode = () => {
    onLogin({
      id: 0,
      email: 'demo@example.com',
      name: 'Demo Mode',
      marketplace: 'wildberries',
      is_active: true,
      is_verified: false,
      created_at: new Date().toISOString(),
    });
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>AGENT<span style={{ color: 'var(--color-accent)' }}>IQ</span></h1>
          <p>Chat Center для маркетплейсов</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {isRegister && (
            <div className="form-group">
              <label htmlFor="name">Название компании</label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Моя компания"
                required={isRegister}
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Пароль</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Минимум 8 символов"
              minLength={8}
              required
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? 'Загрузка...' : isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </form>

        <div className="login-footer">
          <button
            type="button"
            className="btn-link"
            onClick={() => setIsRegister(!isRegister)}
          >
            {isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
          </button>

          <div className="divider">
            <span>или</span>
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={handleDemoMode}
          >
            Демо-режим (без регистрации)
          </button>
        </div>
      </div>

      <style>{`
        .login-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background: var(--color-bg-primary);
          padding: 20px;
        }

        .login-card {
          background: var(--color-bg-secondary);
          border-radius: 12px;
          padding: 40px;
          width: 100%;
          max-width: 400px;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
        }

        .login-header {
          text-align: center;
          margin-bottom: 32px;
        }

        .login-header h1 {
          font-size: 28px;
          font-weight: 700;
          margin: 0 0 8px 0;
          color: var(--color-text-primary);
        }

        .login-header p {
          color: var(--color-text-secondary);
          margin: 0;
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-group label {
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-secondary);
        }

        .form-group input {
          padding: 12px 14px;
          border: 1px solid var(--color-border-light);
          border-radius: 8px;
          font-size: 14px;
          background: var(--color-bg-primary);
          color: var(--color-text-primary);
          transition: border-color 0.2s;
        }

        .form-group input:focus {
          outline: none;
          border-color: var(--color-accent);
        }

        .error-message {
          color: var(--color-danger);
          font-size: 14px;
          padding: 10px;
          background: rgba(231, 76, 60, 0.1);
          border-radius: 6px;
        }

        .btn-primary {
          padding: 12px 20px;
          background: var(--color-accent);
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        .btn-primary:hover:not(:disabled) {
          opacity: 0.9;
        }

        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .login-footer {
          margin-top: 24px;
          text-align: center;
        }

        .btn-link {
          background: none;
          border: none;
          color: var(--color-accent);
          font-size: 14px;
          cursor: pointer;
          padding: 0;
        }

        .btn-link:hover {
          text-decoration: underline;
        }

        .divider {
          display: flex;
          align-items: center;
          margin: 20px 0;
        }

        .divider::before,
        .divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: var(--color-border-light);
        }

        .divider span {
          padding: 0 12px;
          color: var(--color-text-tertiary);
          font-size: 13px;
        }

        .btn-secondary {
          width: 100%;
          padding: 12px 20px;
          background: transparent;
          color: var(--color-text-secondary);
          border: 1px solid var(--color-border-light);
          border-radius: 8px;
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-secondary:hover {
          background: var(--color-bg-tertiary);
          color: var(--color-text-primary);
        }
      `}</style>
    </div>
  );
}
