import React from 'react';

interface EmptyStateProps {
  message?: string;
  onAction?: () => void;
  actionLabel?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  message = 'Tidak ada anomali termal terdeteksi pada wilayah dan rentang waktu yang dipilih.',
  onAction,
  actionLabel = 'Perluas Rentang Waktu',
}) => {
  return (
    <div className="p-6 text-center border border-dashed border-slate-200 dark:border-slate-700 rounded-md">
      <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
        {message}
      </p>
      {onAction && (
        <button
          type="button"
          onClick={onAction}
          className="text-xs px-3 py-1.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-600 min-h-[44px]"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
