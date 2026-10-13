import React from 'react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  onAction?: () => void;
  actionLabel?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'Tidak ada deteksi pada periode ini',
  message = 'Coba perluas rentang tanggal atau wilayah. Tidak adanya deteksi bukan bukti tidak ada kebakaran.',
  onAction,
  actionLabel = 'Perluas Periode',
}) => {
  return (
    <div className="state-card state-empty">
      <div className="state-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-desc">{message}</p>
      {onAction && (
        <button
          type="button"
          onClick={onAction}
          className="state-action-btn"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
