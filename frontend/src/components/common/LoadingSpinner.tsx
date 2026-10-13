import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Memuat deteksi…',
}) => {
  return (
    <div role="status" className="state-card state-loading">
      <div className="skeleton-line skeleton-short" />
      <div className="skeleton-line skeleton-long" />
      <div className="skeleton-line skeleton-medium" />
      <span className="loading-label">{label}</span>
    </div>
  );
};
