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
  lastSyncUtc,
  onToggleMode,
  isDark,
  onToggleTheme,
  totalCount,
}) => {
  return (
    <header className="status-header">
      <div className="header-brand">
        <h1 className="header-title">
          Pemantauan Hotspot & Konteks Gambut
        </h1>
        <span
          className={`badge-mode ${
            mode === 'live' ? 'badge-live' : 'badge-snapshot'
          }`}
        >
          {mode === 'live' ? 'Mode: Live NASA FIRMS' : 'Mode: Snapshot Statis (JOINTS 2026)'}
        </span>
        {totalCount !== undefined && (
          <span className="badge-count">
            {totalCount} Titik
          </span>
        )}
      </div>

      <div className="header-actions">
        {lastSyncUtc && (
          <span className="sync-time">
            Pembaruan: {lastSyncUtc}
          </span>
        )}
        <button
          type="button"
          onClick={onToggleMode}
          className="btn-action"
          title="Alihkan sumber data antara Live API dan Snapshot Fallback"
        >
          Ganti ke {mode === 'live' ? 'Snapshot Fallback' : 'Live API'}
        </button>
        <button
          type="button"
          onClick={onToggleTheme}
          className="btn-action"
          title="Ganti Tema Tampilan"
        >
          {isDark ? 'Tema Terang' : 'Tema Gelap'}
        </button>
      </div>
    </header>
  );
};
