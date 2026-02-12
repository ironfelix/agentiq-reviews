import { useState } from 'react';
import type { AISuggestion } from '../types';

interface AIPanelProps {
  suggestion: AISuggestion | null;
  isLoading: boolean;
  onEdit: (text: string) => void;
  onSend: () => void;
  onClose: () => void;
}

export function AIPanel({ suggestion, isLoading, onEdit, onSend, onClose }: AIPanelProps) {
  const [editedText, setEditedText] = useState('');

  // Update edited text when suggestion changes
  useState(() => {
    if (suggestion) {
      setEditedText(suggestion.text);
    }
  });

  const handleEdit = (text: string) => {
    setEditedText(text);
    onEdit(text);
  };

  if (!suggestion && !isLoading) {
    return null;
  }

  return (
    <div className="w-96 border-l border-gray-700/30 bg-[#141e2b] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-700/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-[#e8a838]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <h3 className="font-semibold">AI Рекомендация</h3>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#e8a838] mb-4"></div>
            <p className="text-sm text-gray-400">Генерация ответа...</p>
          </div>
        ) : suggestion ? (
          <div className="space-y-4">
            {/* Intent & Confidence */}
            <div className="flex items-center justify-between">
              <span className="chat-badge chat-badge-normal">
                {suggestion.intent}
              </span>
              <span className="text-xs text-gray-400">
                Уверенность: {Math.round(suggestion.confidence * 100)}%
              </span>
            </div>

            {/* Warnings */}
            {suggestion.warnings.length > 0 && (
              <div className="bg-[#e85454]/10 border border-[#e85454]/30 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-[#e85454] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#e85454] mb-1">Предупреждения:</p>
                    <ul className="text-xs text-gray-300 space-y-1">
                      {suggestion.warnings.map((warning, idx) => (
                        <li key={idx}>• {warning}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Editable Text */}
            <div>
              <label className="block text-sm font-medium mb-2">
                Текст ответа (можно редактировать):
              </label>
              <textarea
                value={editedText}
                onChange={(e) => handleEdit(e.target.value)}
                className="chat-input w-full resize-none"
                rows={6}
              />
              <p className="text-xs text-gray-500 mt-1">
                {editedText.length} символов
              </p>
            </div>

            {/* Info */}
            <div className="bg-[#7db8e8]/10 border border-[#7db8e8]/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-[#7db8e8] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="flex-1">
                  <p className="text-xs text-gray-300">
                    AI рекомендация создана на основе контекста чата и политик RESPONSE_GUARDRAILS.
                    Проверьте текст перед отправкой.
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Actions */}
      {suggestion && !isLoading && (
        <div className="p-4 border-t border-gray-700/30 space-y-2">
          <button
            onClick={onSend}
            className="chat-button-primary w-full"
          >
            Отправить
          </button>
          <button
            onClick={onClose}
            className="chat-button-secondary w-full"
          >
            Отмена
          </button>
        </div>
      )}
    </div>
  );
}
