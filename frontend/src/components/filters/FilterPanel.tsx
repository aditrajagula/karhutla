import React from 'react';
import type { ConfidenceLevel, HotspotFilterParams, ThermalTier } from '../../types/hotspot';
import { CustomDropdown } from '../common/CustomDropdown';

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
    <div className="filter-panel-v2">
      {/* Search Input Bar (DSG §5.1) */}
      <div className="search-bar-wrapper">
        <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          placeholder="Cari provinsi / kabupaten..."
          value={filters.searchQuery || ''}
          onChange={(e) => onFilterChange({ ...filters, searchQuery: e.target.value })}
          className="search-input"
        />
        {filters.searchQuery && (
          <button
            type="button"
            onClick={() => onFilterChange({ ...filters, searchQuery: '' })}
            className="search-clear-btn"
          >
            ✕
          </button>
        )}
      </div>

      {/* Horizontal Filter Bar (Pill Group Sesuai DSG §5.1) */}
      <div className="filter-pills-row">
        {/* Pill 1: Status Suhu */}
        <CustomDropdown
          label="Status Suhu"
          value={filters.thermalTier || ''}
          ariaLabel="Filter Status Suhu"
          options={[
            { value: '', label: 'Semua Status Suhu', shortLabel: 'Status Suhu' },
            { value: 'high', label: 'Suhu Tinggi (>50 MW)', shortLabel: 'Tinggi', color: 'var(--ev-hotspot-high)' },
            { value: 'mid', label: 'Suhu Sedang (15–50 MW)', shortLabel: 'Sedang', color: 'var(--ev-hotspot-mid)' },
            { value: 'low', label: 'Suhu Rendah (<15 MW)', shortLabel: 'Rendah', color: 'var(--ev-hotspot-low)' },
          ]}
          onChange={(val) =>
            onFilterChange({
              ...filters,
              thermalTier: (val as ThermalTier) || undefined,
            })
          }
        />

        {/* Pill 2: Sensor VIIRS */}
        <CustomDropdown
          label="Sensor"
          value={filters.satellite || ''}
          ariaLabel="Filter Sensor VIIRS"
          options={[
            { value: '', label: 'Semua Sensor VIIRS', shortLabel: 'Sensor' },
            { value: 'NOAA-20', label: 'NOAA-20 (VIIRS)', shortLabel: 'NOAA-20', icon: '🛰️' },
            { value: 'Suomi NPP', label: 'Suomi NPP (VIIRS)', shortLabel: 'Suomi NPP', icon: '🛰️' },
            { value: 'NOAA-21', label: 'NOAA-21 (VIIRS)', shortLabel: 'NOAA-21', icon: '🛰️' },
          ]}
          onChange={(val) =>
            onFilterChange({
              ...filters,
              satellite: val || undefined,
            })
          }
        />

        {/* Pill 3: Mutu / Confidence */}
        <CustomDropdown
          label="Mutu"
          value={filters.minConfidence || ''}
          ariaLabel="Filter Mutu Keyakinan"
          options={[
            { value: '', label: 'Semua Mutu', shortLabel: 'Mutu' },
            { value: 'high', label: 'Tinggi (High Confidence)', shortLabel: 'Tinggi' },
            { value: 'nominal', label: 'Nominal', shortLabel: 'Nominal' },
            { value: 'low', label: 'Rendah (Low Confidence)', shortLabel: 'Rendah' },
          ]}
          onChange={(val) =>
            onFilterChange({
              ...filters,
              minConfidence: (val as ConfidenceLevel) || undefined,
            })
          }
        />
      </div>

      {/* Rentang Waktu (Pill Tombol) */}
      <div className="time-range-row">
        <span className="time-range-label">Rentang:</span>
        <div className="time-pill-buttons">
          {[1, 2, 3, 7].map((days) => (
            <button
              key={days}
              type="button"
              className={`time-pill-btn ${filters.dayRange === days || (!filters.dayRange && days === 2) ? 'active' : ''}`}
              onClick={() => onFilterChange({ ...filters, dayRange: days })}
            >
              {days}H
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onReset}
          className="reset-pill-btn"
          title="Pulihkan filter awal"
        >
          Reset
        </button>
      </div>

      {/* Total Terdeteksi Bar */}
      <div className="summary-status-bar">
        <span className="summary-count tabular-nums">
          {totalFiltered.toLocaleString('id-ID')} titik anomali termal
        </span>
        <span className="summary-note">
          {filters.dayRange || 2} hari observasi
        </span>
      </div>
    </div>
  );
};
