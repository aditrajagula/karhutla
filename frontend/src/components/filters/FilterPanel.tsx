import React from 'react';
import type { ConfidenceLevel, HotspotFilterParams } from '../../types/hotspot';
import arrowDropdown from '../../assets/map/arrow-dropdown.svg';
import { Icon } from '../common/Icon';

interface FilterPanelProps {
  filters: HotspotFilterParams;
  onFilterChange: (filters: HotspotFilterParams) => void;
  onReset: () => void;
  totalFiltered: number;
}

const DAY_OPTIONS = [1, 2, 3];

export const FilterPanel: React.FC<FilterPanelProps> = ({ filters, onFilterChange, onReset }) => {
  const activeDays = Math.min(filters.dayRange ?? 3, 3);

  return (
    <div className="mp-filter">
      <h2 className="mp-filter__title">Filter Observasi Satelit</h2>

      <div className="mp-filter__group">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="mp-label">Rentang Hari Deteksi</span>
          <span style={{ fontSize: '11px', color: '#64748B' }}>Maks. 3 Hari</span>
        </div>
        <div className="mp-days" role="group" aria-label="Rentang hari deteksi">
          {DAY_OPTIONS.map((days) => (
            <button
              key={days}
              type="button"
              className={`mp-days__item ${activeDays === days ? 'is-active' : ''}`}
              onClick={() => onFilterChange({ ...filters, dayRange: days })}
            >
              {days} Hari
            </button>
          ))}
        </div>
      </div>

      <div className="mp-filter__group">
        <span className="mp-label">Rentang Tanggal Kalender</span>
        <div className="mp-dates">
          <input
            type="date"
            aria-label="Tanggal mulai observasi"
            value={filters.startDate || ''}
            onChange={(e) => onFilterChange({ ...filters, startDate: e.target.value })}
            className="mp-field"
          />
          <span className="mp-dates__dash" aria-hidden="true" />
          <input
            type="date"
            aria-label="Tanggal selesai observasi"
            value={filters.endDate || ''}
            onChange={(e) => onFilterChange({ ...filters, endDate: e.target.value })}
            className="mp-field"
          />
        </div>
      </div>

      <div className="mp-filter__group">
        <span className="mp-label">Tingkat Keyakinan Sensor</span>
        <div className="mp-select">
          <select
            aria-label="Pilih tingkat keyakinan"
            value={filters.minConfidence || ''}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                minConfidence: (e.target.value as ConfidenceLevel) || undefined,
              })
            }
            className="mp-field"
          >
            <option value="">Semua Tingkat Keyakinan</option>
            <option value="high">Tinggi</option>
            <option value="nominal">Sedang</option>
            <option value="low">Rendah</option>
          </select>
          <Icon src={arrowDropdown} className="mp-select__arrow" />
        </div>
      </div>

      <button type="button" onClick={onReset} className="mp-btn mp-btn--solid mp-filter__reset">
        Pulihkan Pengaturan Awal
      </button>
    </div>
  );
};
