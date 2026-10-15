import React from 'react';
import type { DataSourceMode } from '../../types/status';

interface StatusBarProps {
  mode: DataSourceMode;
  lastSyncUtc: string | null;
  onToggleMode: () => void;
  isDark: boolean;
  onToggleTheme: () => void;
  totalCount?: number;
  reportsCount?: number;
  onOpenReportModal?: () => void;
  onOpenForestModal?: () => void;
  onCheckNearbyRisk?: () => void;
  isLocatingNearby?: boolean;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  mode,
  lastSyncUtc,
  onToggleMode,
  isDark,
  onToggleTheme,
  totalCount,
  reportsCount,
  onOpenReportModal,
  onOpenForestModal,
  onCheckNearbyRisk,
  isLocatingNearby = false,
}) => {
  return (
    <header className="status-header">
      <div className="header-brand">
        <h1 className="header-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🛡️ FireGuard</span>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#10B981', border: '1px solid #10B981', padding: '1px 6px', borderRadius: '4px' }}>
            Cakupan Kalimantan
          </span>
        </h1>
        <span
          className={`badge-mode ${
            mode === 'live' ? 'badge-live' : 'badge-snapshot'
          }`}
        >
          {mode === 'live' ? 'Mode: Live NASA FIRMS' : 'Mode: Snapshot Mandiri Tim'}
        </span>
        {totalCount !== undefined && (
          <span className="badge-count" title="Jumlah titik anomali satelit">
            {totalCount} Satelit
          </span>
        )}
        {reportsCount !== undefined && (
          <span
            className="badge-count"
            style={{ backgroundColor: '#0284C7', color: '#fff' }}
            title="Jumlah laporan partisipatif masyarakat"
          >
            {reportsCount} Laporan Warga
          </span>
        )}
      </div>

      <div className="header-actions">
        {onOpenForestModal && (
          <button
            type="button"
            onClick={onOpenForestModal}
            className="btn-action"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: isDark ? '#34D399' : '#047857',
              fontWeight: 600,
              border: '1px solid #10B981',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Buka data analisis tutupan pohon Hansen Global Forest Change v1.13"
          >
            <span>🌲</span>
            <span>Tutupan Pohon Hansen GFC</span>
          </button>
        )}
        {onCheckNearbyRisk && (
          <button
            type="button"
            onClick={onCheckNearbyRisk}
            className="btn-action"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              color: isDark ? '#FCA5A5' : '#B91C1C',
              fontWeight: 600,
              border: '1px solid #EF4444',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Deteksi posisi GPS perangkat dan cek estimasi risiko kebakaran di sekitar Anda"
          >
            <span>{isLocatingNearby ? '📡' : '🎯'}</span>
            <span>{isLocatingNearby ? 'Mencari GPS...' : 'Prediksi Sekitar Saya'}</span>
          </button>
        )}
        {onOpenReportModal && (
          <button
            type="button"
            onClick={onOpenReportModal}
            className="btn-action"
            style={{
              backgroundColor: 'var(--color-forest-dark, #0F766E)',
              color: '#FFFFFF',
              fontWeight: 600,
              border: '1px solid #14B8A6',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Buka form pelaporan kejadian oleh warga"
          >
            <span>📢</span>
            <span>Lapor Kejadian</span>
          </button>
        )}
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
