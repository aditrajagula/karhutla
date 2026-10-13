import React from 'react';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  onSwitchToSnapshot?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  onRetry,
  onSwitchToSnapshot,
}) => {
  return (
    <div
      role="alert"
      className="p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-md text-xs text-red-800 dark:text-red-300"
    >
      <div className="font-semibold mb-1">Terjadi Kendala Koneksi API</div>
      <div className="mb-2">{message}</div>
      <div className="flex gap-2">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-2.5 py-1 rounded bg-red-100 dark:bg-red-900/50 hover:bg-red-200 dark:hover:bg-red-800 text-red-900 dark:text-red-200 min-h-[44px]"
          >
            Coba Lagi
          </button>
        )}
        {onSwitchToSnapshot && (
          <button
            type="button"
            onClick={onSwitchToSnapshot}
            className="px-2.5 py-1 rounded bg-slate-800 text-white hover:bg-slate-700 min-h-[44px]"
          >
            Beralih ke Snapshot Benchmark
          </button>
        )}
      </div>
    </div>
  );
};
