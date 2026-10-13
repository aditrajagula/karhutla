import React from 'react';

interface ErrorBannerProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  onSwitchToSnapshot?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title = 'Data live tidak dapat diambil',
  message = 'Kami menampilkan snapshot statis yang diambil sebelumnya. Data live belum valid sampai koneksi pulih.',
  onRetry,
  onSwitchToSnapshot,
}) => {
  return (
    <div role="alert" className="state-card state-error">
      <div className="error-header-row">
        <span className="error-indicator" />
        <h3 className="error-title">{title}</h3>
      </div>
      <p className="error-desc">{message}</p>
      <div className="error-actions">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="error-btn-primary"
          >
            Coba lagi
          </button>
        )}
        {onSwitchToSnapshot && (
          <button
            type="button"
            onClick={onSwitchToSnapshot}
            className="error-btn-secondary"
          >
            Lihat snapshot
          </button>
        )}
      </div>
    </div>
  );
};
