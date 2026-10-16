import React, { useState } from 'react';
import type { PredictiveHotspotFeature } from '../../types/prediction';
import locationIcon from '../../assets/map/location.svg';
import pinIcon from '../../assets/map/pin.svg';
import timeIcon from '../../assets/map/time.svg';
import { Icon } from '../common/Icon';

interface PredictiveListProps {
  hotspots: PredictiveHotspotFeature[];
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onSelectHotspot: (hotspot: PredictiveHotspotFeature) => void;
  selectedId?: string;
}

export const PredictiveList: React.FC<PredictiveListProps> = ({
  hotspots,
  isLoading = false,
  errorMessage,
  onRetry,
  onSelectHotspot,
  selectedId,
}) => {
  const [levelFilter, setLevelFilter] = useState<'ALL' | 'TINGGI' | 'SEDANG'>('ALL');

  const filteredHotspots = hotspots.filter((feat) => {
    if (levelFilter === 'ALL') return true;
    return feat.properties.risk_level === levelFilter;
  });

  return (
    <>
      {/* Panel Filter Tingkat Risiko Prediksi Model (Selaras dengan FilterPanel) */}
      <div className="mp-filter">
        <h2 className="mp-filter__title">Hotspot Prediksi Model</h2>

        <div className="mp-filter__group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="mp-label">Tingkat Kerawanan</span>
            <span style={{ fontSize: '11px', color: '#64748B' }}>Siklus Harian</span>
          </div>
          <div className="mp-days" role="group" aria-label="Filter tingkat risiko">
            <button
              type="button"
              className={`mp-days__item ${levelFilter === 'ALL' ? 'is-active' : ''}`}
              onClick={() => setLevelFilter('ALL')}
            >
              Semua
            </button>
            <button
              type="button"
              className={`mp-days__item ${levelFilter === 'TINGGI' ? 'is-active' : ''}`}
              onClick={() => setLevelFilter('TINGGI')}
            >
              Siaga
            </button>
            <button
              type="button"
              className={`mp-days__item ${levelFilter === 'SEDANG' ? 'is-active' : ''}`}
              onClick={() => setLevelFilter('SEDANG')}
            >
              Waspada
            </button>
          </div>
        </div>

        <p style={{ margin: 0, fontSize: '11px', lineHeight: 1.4, color: 'var(--mp-orange)', opacity: 0.9 }}>
          Estimasi probabilitas kerawanan karhutla 24 jam berbasis cuaca mikro dan tutupan lahan. <b>Bukan</b> deteksi api fisik satelit NASA FIRMS.
        </p>
      </div>

      {/* Daftar Titik Pantau Waspada (Identik dengan format mp-list pada DetectionList) */}
      <section className="mp-list" aria-label="Daftar titik pantau waspada">
        <div className="mp-list__header">
          <h2 className="mp-list__title">Daftar Titik Pantau Waspada</h2>
          <span className="mp-list__count">
            {isLoading ? 'Memuat...' : `${filteredHotspots.length} wilayah`}
          </span>
        </div>

        <div className="mp-list__frame">
          <div className="mp-list__scroll">
            {isLoading ? (
              <div className="mp-list__state" role="status">
                <span className="mp-spinner" aria-hidden="true" />
                <span>Mengevaluasi risiko cuaca harian...</span>
              </div>
            ) : errorMessage ? (
              <div className="mp-list__state">
                <span>{errorMessage}</span>
                {onRetry && (
                  <button type="button" className="mp-btn mp-btn--solid mp-list__expand" onClick={onRetry}>
                    Muat Ulang Prediksi
                  </button>
                )}
              </div>
            ) : filteredHotspots.length === 0 ? (
              <div className="mp-list__state">
                <span>Tidak ada titik kerawanan Sedang-Tinggi terdeteksi.</span>
              </div>
            ) : (
              filteredHotspots.map((feat) => {
                const p = feat.properties;
                const isSelected = selectedId === p.id;

                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onSelectHotspot(feat)}
                    className={`mp-card ${isSelected ? 'is-selected' : ''}`}
                  >
                    <span className="mp-card__info">
                      <span className="mp-card__row">
                        <Icon src={locationIcon} size={10} />
                        {p.location_name}
                      </span>
                      <span className="mp-card__row">
                        <Icon src={pinIcon} size={10} />
                        {p.latitude.toFixed(5)}, {p.longitude.toFixed(5)}
                      </span>
                      <span className="mp-card__row">
                        <Icon src={timeIcon} size={10} />
                        {p.prediction_date} Harian
                      </span>
                    </span>
                    <span className="mp-card__chips">
                      <span className="mp-chip">{p.risk_percentage}%</span>
                      <span className="mp-chip">{p.caution_level}</span>
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
        {!isLoading && filteredHotspots.length > 0 && (
          <p className="mp-list__more">
            Menampilkan {filteredHotspots.length} titik waspada hasil evaluasi model prediktif harian.
          </p>
        )}
      </section>
    </>
  );
};

