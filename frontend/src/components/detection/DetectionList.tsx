import React from 'react';
import type { ConfidenceLevel, Hotspot } from '../../types/hotspot';
import locationIcon from '../../assets/map/location.svg';
import pinIcon from '../../assets/map/pin.svg';
import timeIcon from '../../assets/map/time.svg';
import { Icon } from '../common/Icon';

interface DetectionListProps {
  hotspots: Hotspot[];
  isLoading?: boolean;
  onExpandRange?: () => void;
  onSelectHotspot: (hotspot: Hotspot) => void;
  selectedId?: string;
}

const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  high: 'Tinggi',
  nominal: 'Normal',
  low: 'Rendah',
};

const MAX_ROWS = 100;

export const DetectionList: React.FC<DetectionListProps> = ({
  hotspots,
  isLoading = false,
  onExpandRange,
  onSelectHotspot,
  selectedId,
}) => {
  return (
    <section className="mp-list" aria-label="Daftar rekaman hotspot">
      <div className="mp-list__header">
        <h2 className="mp-list__title">Daftar Rekaman Hotspot</h2>
        <span className="mp-list__count">{hotspots.length} rekaman</span>
      </div>

      {/* Kerangka tetap: tinggi & lebar sama saat loading, kosong, maupun berisi */}
      <div className="mp-list__frame">
        <div className="mp-list__scroll">
          {isLoading ? (
            <div className="mp-list__state" role="status">
              <span className="mp-spinner" aria-hidden="true" />
              <span>Mengambil deteksi satelit...</span>
            </div>
          ) : hotspots.length === 0 ? (
            <div className="mp-list__state">
              <span>Tidak ada anomali termal terdeteksi pada rentang waktu terpilih.</span>
              {onExpandRange && (
                <button type="button" className="mp-btn mp-btn--solid mp-list__expand" onClick={onExpandRange}>
                  Perluas Rentang ke 4 Hari
                </button>
              )}
            </div>
          ) : (
            hotspots.slice(0, MAX_ROWS).map((h) => (
              <button
                key={h.id}
                type="button"
                onClick={() => onSelectHotspot(h)}
                className={`mp-card ${selectedId === h.id ? 'is-selected' : ''}`}
              >
                <span className="mp-card__info">
                  <span className="mp-card__row">
                    <Icon src={locationIcon} size={10} />
                    {h.province || 'Kalimantan'}
                  </span>
                  <span className="mp-card__row">
                    <Icon src={pinIcon} size={10} />
                    {h.latitude.toFixed(5)}, {h.longitude.toFixed(5)}
                  </span>
                  <span className="mp-card__row">
                    <Icon src={timeIcon} size={10} />
                    {h.acq_date} {h.acq_time} UTC
                  </span>
                </span>
                <span className="mp-card__chips">
                  {h.in_peat && (
                    <span className="mp-chip" style={{ color: '#9333ea', borderColor: 'rgba(147, 51, 234, 0.4)' }}>
                      Gambut
                    </span>
                  )}
                  {h.in_forest && (
                    <span className="mp-chip" style={{ color: '#16a34a', borderColor: 'rgba(22, 163, 74, 0.4)' }}>
                      Hutan
                    </span>
                  )}
                  {h.frp !== undefined && h.frp !== null && (
                    <span className="mp-chip">{h.frp} MW</span>
                  )}
                  <span className="mp-chip">{CONFIDENCE_LABEL[h.confidence] ?? h.confidence}</span>
                </span>
              </button>
            ))
          )}
        </div>
      </div>
      {!isLoading && hotspots.length > MAX_ROWS && (
        <p className="mp-list__more">
          Menampilkan {MAX_ROWS} dari {hotspots.length} titik pada daftar ringkas.
        </p>
      )}
    </section>
  );
};
