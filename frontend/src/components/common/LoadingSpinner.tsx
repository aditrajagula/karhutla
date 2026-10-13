import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Memuat deteksi satelit...',
}) => {
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center p-6 space-y-2 text-slate-500 dark:text-slate-400"
    >
      <div className="w-5 h-5 border-2 border-slate-300 border-t-amber-600 rounded-full animate-spin" />
      <span className="text-xs">{label}</span>
    </div>
  );
};
