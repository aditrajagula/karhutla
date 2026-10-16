import React from 'react';
import type { DataSourceMode } from '../../types/status';
import logoWhite from '../../assets/landing/logo-white.png';
import logoOrange from '../../assets/landing/logo-orange.png';
import { ThemeToggle } from '../common/ThemeToggle';
import { getCurrentUser, logout } from '../../services/dummyAuth';

interface StatusBarProps {
  mode: DataSourceMode;
  lastSyncUtc?: string | null;
  onToggleMode: () => void;
  isDark: boolean;
  onToggleTheme: () => void;
  totalCount?: number;
  reportsCount?: number;
  onOpenReportModal?: () => void;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  mode,
  onToggleMode,
  isDark,
  onToggleTheme,
  onOpenReportModal,
}) => {
  const user = getCurrentUser();

  const handleLogout = () => {
    logout();
    window.history.pushState(null, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const isOfficer = !user || user.role === 'petugas';

  return (
    <header className="mp-header">
      <div className="mp-header__brand">
        <img
          className="mp-header__logo"
          src={isDark ? logoOrange : logoWhite}
          alt="Logo JagaBorneo"
        />
        <h1 className="mp-header__title">JagaBorneo</h1>
      </div>

      <div className="mp-header__actions">
        {/* Tombol aksi pelaporan deforestasi: hanya untuk akun warga, disembunyikan di bagian admin / petugas */}
        {!isOfficer && onOpenReportModal && (
          <button
            type="button"
            className="mp-btn mp-btn--solid"
            onClick={onOpenReportModal}
            title="Buka form pelaporan deforestasi dan kerusakan hutan oleh warga"
          >
            Lapor Deforestasi
          </button>
        )}

        <div className="mp-segment" role="group" aria-label="Sumber data">
          <button
            type="button"
            className={`mp-segment__item ${mode === 'live' ? 'is-active' : ''}`}
            onClick={mode === 'live' ? undefined : onToggleMode}
            aria-pressed={mode === 'live'}
            title="Data langsung dari NASA FIRMS"
          >
            Live API
          </button>
          <button
            type="button"
            className={`mp-segment__item ${mode === 'snapshot' ? 'is-active' : ''}`}
            onClick={mode === 'snapshot' ? undefined : onToggleMode}
            aria-pressed={mode === 'snapshot'}
            title="Gunakan data arsip lokal cadangan jika API atau koneksi terbatas"
          >
            Data Cadangan
          </button>
        </div>

        {user && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 8px',
                borderRadius: '6px',
                backgroundColor:
                  user.role === 'petugas'
                    ? 'rgba(204, 111, 0, 0.2)'
                    : 'rgba(16, 185, 129, 0.2)',
                color: user.role === 'petugas' ? '#CC6F00' : '#10B981',
                border: `1px solid ${user.role === 'petugas' ? '#CC6F00' : '#10B981'}`,
              }}
              title={`${user.name} (${user.email})`}
            >
              {user.role === 'petugas' ? 'Petugas' : 'Warga'}
            </span>
            <button
              type="button"
              className="mp-btn mp-btn--ghost"
              onClick={handleLogout}
              style={{ fontSize: '12px', padding: '5px 10px' }}
              title="Keluar dari akun"
            >
              Keluar
            </button>
          </div>
        )}

        <ThemeToggle isDark={isDark} onToggle={onToggleTheme} />
      </div>
    </header>
  );
};

