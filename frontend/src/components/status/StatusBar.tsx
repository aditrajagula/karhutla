import React from 'react';
import type { DataSourceMode } from '../../types/status';

interface StatusBarProps {
  mode: DataSourceMode;
  lastSyncUtc: string | null;
  onToggleMode: () => void;
  isDark: boolean;
  onToggleTheme: () => void;
  totalCount?: number;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  mode,
  onToggleMode,
  isDark,
  onToggleTheme,
}) => {
  return (
    <div className="sidebar-brand-header">
      <div className="brand-title-group">
        <div className="brand-icon-box">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <div className="brand-text-col">
          <h1 className="brand-title-text">FireGuard</h1>
          <span className="brand-sub-text">Sistem Pemantauan Hotspot</span>
        </div>
      </div>

      <div className="brand-actions-group">
        {/* Badge Live Status Warna Hijau Mint (● Live API) sesuai DSG §5.1 */}
        <button
          type="button"
          onClick={onToggleMode}
          className={`live-status-pill ${mode === 'live' ? 'status-mint-active' : 'status-snapshot-active'}`}
          title="Klik untuk beralih antara Live FIRMS API dan Snapshot"
          aria-live="polite"
        >
          <span className="live-status-dot" />
          <span>{mode === 'live' ? 'Live API' : 'Snapshot'}</span>
        </button>

        <button
          type="button"
          onClick={onToggleTheme}
          className="theme-toggle-btn"
          title={isDark ? 'Beralih ke Tema Terang' : 'Beralih ke Tema Gelap'}
          aria-label="Toggle tema gelap dan terang"
        >
          {isDark ? '☀️' : '🌙'}
        </button>
      </div>
    </div>
  );
};
