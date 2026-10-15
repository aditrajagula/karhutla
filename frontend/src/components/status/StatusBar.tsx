import React from 'react';
import type { DataSourceMode } from '../../types/status';
import logoWhite from '../../assets/landing/logo-white.png';
import logoOrange from '../../assets/landing/logo-orange.png';
import { ThemeToggle } from '../common/ThemeToggle';

interface StatusBarProps {
  mode: DataSourceMode;
  onToggleMode: () => void;
  isDark: boolean;
  onToggleTheme: () => void;
  onOpenReportModal?: () => void;
  onOpenForestModal?: () => void;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  mode,
  onToggleMode,
  isDark,
  onToggleTheme,
  onOpenReportModal,
  onOpenForestModal,
}) => {
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
        {onOpenForestModal && (
          <button
            type="button"
            className="mp-btn mp-btn--ghost"
            onClick={onOpenForestModal}
            title="Buka data analisis tutupan pohon Hansen Global Forest Change v1.13"
          >
            Tutupan Pohon
          </button>
        )}

        {onOpenReportModal && (
          <button
            type="button"
            className="mp-btn mp-btn--solid"
            onClick={onOpenReportModal}
            title="Buka form pelaporan kejadian oleh warga"
          >
            Lapor Kejadian
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
            title="Snapshot lokal tim sebagai cadangan"
          >
            Snapshot Fallback
          </button>
        </div>

        <ThemeToggle isDark={isDark} onToggle={onToggleTheme} />
      </div>
    </header>
  );
};
