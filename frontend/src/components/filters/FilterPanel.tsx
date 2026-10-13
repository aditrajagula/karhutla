import React from 'react';
import type { ConfidenceLevel, HotspotFilterParams } from '../../types/hotspot';

interface FilterPanelProps {
  filters: HotspotFilterParams;
  onFilterChange: (filters: HotspotFilterParams) => void;
  onReset: () => void;
  totalFiltered: number;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  filters,
  onFilterChange,
  onReset,
  totalFiltered,
}) => {
  return (
    <div className="filter-card">
      <div className="filter-header">
        <h2 className="filter-title">
          Filter Observasi Satelit
        </h2>
        <span className="filter-count-badge">
          {totalFiltered} Anomali
        </span>
      </div>

      <div className="filter-body">
        {/* Rentang Waktu Observasi */}
        <div className="filter-group">
          <label className="filter-label">
            Rentang Hari Deteksi
          </label>
          <div className="filter-day-buttons">
            {[1, 2, 3, 7].map((days) => (
              <button
                key={days}
                type="button"
                className={`btn-day ${filters.dayRange === days || (!filters.dayRange && days === 2) ? 'active' : ''}`}
                onClick={() => onFilterChange({ ...filters, dayRange: days })}
              >
                {days} Hari
              </button>
            ))}
          </div>
        </div>

        {/* Tanggal Manual (Opsional) */}
        <div className="filter-group">
          <label className="filter-label">
            Rentang Tanggal Kalender
          </label>
          <div className="filter-date-grid">
            <input
              type="date"
              aria-label="Tanggal mulai observasi"
              value={filters.startDate || ''}
              onChange={(e) => onFilterChange({ ...filters, startDate: e.target.value })}
              className="filter-input"
            />
            <input
              type="date"
              aria-label="Tanggal selesai observasi"
              value={filters.endDate || ''}
              onChange={(e) => onFilterChange({ ...filters, endDate: e.target.value })}
              className="filter-input"
            />
          </div>
        </div>

        {/* Filter Tingkat Keyakinan (Confidence) */}
        <div className="filter-group">
          <label className="filter-label">
            Tingkat Keyakinan Sensor
          </label>
          <select
            aria-label="Pilih tingkat keyakinan"
            value={filters.minConfidence || ''}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                minConfidence: (e.target.value as ConfidenceLevel) || undefined,
              })
            }
            className="filter-select"
          >
            <option value="">Semua Tingkat Keyakinan</option>
            <option value="high">Tinggi (High)</option>
            <option value="nominal">Nominal</option>
            <option value="low">Rendah (Low)</option>
          </select>
        </div>

        <div className="filter-actions">
          <button
            type="button"
            onClick={onReset}
            className="btn-reset"
          >
            Pulihkan Pengaturan Awal
          </button>
        </div>
      </div>
    </div>
  );
};
