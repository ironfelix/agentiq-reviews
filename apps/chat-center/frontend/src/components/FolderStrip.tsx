import { useEffect, useRef, type ReactNode } from 'react';
import type { InteractionQualityMetricsResponse } from '../types';

type Channel = 'all' | 'review' | 'question' | 'chat';

interface FolderStripProps {
  activeChannel: Channel;
  onChannelChange: (channel: Channel) => void;
  pipeline?: InteractionQualityMetricsResponse['pipeline'] | null;
  totalChats?: number;
  variant?: 'desktop' | 'mobile';
}

const FOLDERS: { id: Channel; label: string; icon: ReactNode }[] = [
  {
    id: 'all',
    label: 'Все',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    id: 'review',
    label: 'Отзывы',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
  },
  {
    id: 'question',
    label: 'Вопросы',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
  },
  {
    id: 'chat',
    label: 'Чаты',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
      </svg>
    ),
  },
];

function getBadgeCount(
  channel: Channel,
  pipeline: InteractionQualityMetricsResponse['pipeline'] | null | undefined,
): number {
  if (!pipeline) return 0;
  if (channel === 'all') return pipeline.needs_response_total;
  const item = pipeline.by_channel.find((ch) => ch.channel === channel);
  return item ? item.needs_response_total : 0;
}

export function FolderStrip({ activeChannel, onChannelChange, pipeline, variant = 'desktop' }: FolderStripProps) {
  const spacerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (variant !== 'desktop') return;
    const sync = () => {
      const header = document.querySelector('.chat-list-header') as HTMLElement | null;
      if (header && spacerRef.current) {
        spacerRef.current.style.height = `${header.offsetHeight + 1}px`;
      }
    };
    sync();
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  }, [variant]);

  return (
    <nav className={`folder-strip ${variant}`}>
      {variant === 'desktop' && <div ref={spacerRef} className="folder-spacer" />}
      {FOLDERS.map((folder) => {
        const badge = getBadgeCount(folder.id, pipeline);
        const isActive = activeChannel === folder.id;
        return (
          <button
            key={folder.id}
            type="button"
            className={`folder-item${isActive ? ' active' : ''}`}
            onClick={() => onChannelChange(folder.id)}
            title={folder.label}
          >
            <div className="folder-icon">{folder.icon}</div>
            <span className="folder-label">{folder.label}</span>
            {badge > 0 && (
              <span className="folder-badge">{badge > 99 ? '99+' : badge}</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
