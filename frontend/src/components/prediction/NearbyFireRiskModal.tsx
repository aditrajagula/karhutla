import React from 'react';
import type { FireRiskPrediction } from '../../types/prediction';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import { CloseIcon, MapPinIcon, RefreshIcon } from '../common/SvgIcons';
import { TelegramAlertCard } from './TelegramAlertCard';

interface NearbyFireRiskModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  error: string | null;
  prediction: FireRiskPrediction | null;
  userCoords: { lat: number; lon: number; accuracy?: number } | null;
  hotspots?: Hotspot[];
  reports?: CitizenReport[];
  onRefreshGps: () => void;
  onSelectSampleLocation?: (lat: number, lon: number, name: string) => void;
  onFocusMap?: () => void;
  isDark?: boolean;
}

const SAMPLE_LOCATIONS = [
  { name: 'Pontianak', province: 'Kalimantan Barat', lat: -0.0263, lon: 109.3425 },
  { name: 'Palangka Raya', province: 'Kalimantan Tengah', lat: -2.2161, lon: 113.914 },
  { name: 'Banjarmasin', province: 'Kalimantan Selatan', lat: -3.3167, lon: 114.5901 },
  { name: 'Samarinda', province: 'Kalimantan Timur', lat: -0.5016, lon: 117.1537 },
  { name: 'Tanjung Selor', province: 'Kalimantan Utara', lat: 2.8375, lon: 117.3653 },
];

export const NearbyFireRiskModal: React.FC<NearbyFireRiskModalProps> = ({
  isOpen,
  onClose,
  isLoading,
  error,
  prediction,
  userCoords,
  onRefreshGps,
  onSelectSampleLocation,
  onFocusMap,
  isDark = false,
}) => {
  if (!isOpen) return null;

  const features = prediction?.input_features;
  const riskLevel = prediction?.risk_level || 'TIDAK_DAPAT_DINILAI';
  const riskLevelLabel =
    prediction?.risk_label ||
    (riskLevel === 'TINGGI' ? 'Tinggi' : riskLevel === 'SEDANG' ? 'Sedang' : riskLevel === 'RENDAH' ? 'Rendah' : 'Belum dapat dinilai');
  const riskPercent = prediction?.risk_percentage;
  const isSuccessful = prediction?.status === 'SUCCESS';
  const isUnavailable = prediction && ['OUT_OF_SCOPE', 'INSUFFICIENT_DATA', 'UNAVAILABLE'].includes(prediction.status);

  const measurements = [
    { label: 'Suhu udara', value: features?.t2m !== undefined ? `${features.t2m} °C` : null },
    { label: 'Kelembapan', value: features?.h2m !== undefined ? `${features.h2m} %` : null },
    { label: 'Curah hujan', value: features?.tp !== undefined ? `${features.tp} mm` : null },
    { label: 'Kecepatan angin', value: features?.w10 !== undefined ? `${features.w10} m/s` : null },
    { label: 'Tutupan pohon', value: features?.f_prim !== undefined ? `${Math.round(features.f_prim * 100)} %` : null },
    { label: 'Ketinggian', value: features?.dem !== undefined ? `${Math.round(features.dem)} mdpl` : null },
  ].filter((item): item is { label: string; value: string } => item.value !== null);

  return (
    <div
      className="modal-backdrop risk-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={`risk-modal${isDark ? ' risk-modal--dark' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="nearby-risk-title"
      >
        <header className="risk-modal__header">
          <div>
            <h2 id="nearby-risk-title">Prediksi Risiko Karhutla</h2>
            <p>Estimasi model untuk 24 jam ke depan</p>
          </div>
          <button type="button" className="risk-modal__close" onClick={onClose} aria-label="Tutup prediksi risiko">
            <CloseIcon size={16} />
          </button>
        </header>

        <div className="risk-modal__body">
          <section className="risk-modal__location" aria-label="Lokasi pemantauan">
            <div className="risk-modal__location-info">
              <span className="risk-modal__eyebrow">Lokasi pemantauan</span>
              <strong className="risk-modal__coordinates">
                {userCoords ? `${userCoords.lat.toFixed(4)}°, ${userCoords.lon.toFixed(4)}°` : 'Mencari lokasi perangkat…'}
              </strong>
              <span className="risk-modal__muted">
                {prediction?.province || 'Kalimantan'}
                {userCoords?.accuracy ? ` · Akurasi ±${Math.round(userCoords.accuracy)} m` : ''}
              </span>
            </div>
            <button type="button" className="mp-btn mp-btn--solid risk-modal__button" onClick={onRefreshGps} disabled={isLoading}>
              <RefreshIcon size={14} />
              {isLoading ? 'Memproses…' : 'Perbarui lokasi'}
            </button>
          </section>

          {error && (
            <div className="risk-modal__message risk-modal__message--error" role="alert">
              <p>{error}</p>
              {onSelectSampleLocation && (
                <div className="risk-modal__samples">
                  <span>Pilih lokasi contoh:</span>
                  <div>
                    {SAMPLE_LOCATIONS.map((location) => (
                      <button
                        type="button"
                        key={location.name}
                        onClick={() => onSelectSampleLocation(location.lat, location.lon, `${location.name} (${location.province})`)}
                      >
                        {location.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {isLoading && (
            <div className="risk-modal__message" role="status">
              Memuat data cuaca dan kondisi lingkungan…
            </div>
          )}

          {!isLoading && isUnavailable && (
            <div className="risk-modal__message">
              <strong>{prediction.risk_label || 'Risiko belum dapat dinilai'}</strong>
              <p>{prediction.message || 'Data yang tersedia belum cukup untuk menghitung risiko di lokasi ini.'}</p>
              <span className="risk-modal__muted">Belum dapat dinilai bukan berarti lokasi aman.</span>
            </div>
          )}

          {!isLoading && isSuccessful && prediction && (
            <>
              {prediction.data_quality?.status === 'PARTIAL' && (
                <div className="risk-modal__message risk-modal__message--notice">
                  Data yang tersedia masih parsial. Hasil ini hanya indikasi awal dan bukan konfirmasi kebakaran.
                </div>
              )}

              <section className={`risk-modal__result risk-modal__result--${riskLevel.toLowerCase()}`} aria-label="Hasil prediksi risiko">
                <div>
                  <span className="risk-modal__eyebrow">Tingkat risiko</span>
                  <strong className="risk-modal__level">{riskLevelLabel}</strong>
                </div>
                {typeof riskPercent === 'number' && (
                  <div className="risk-modal__score">
                    <strong>{riskPercent.toFixed(1)}%</strong>
                    <span>skor model</span>
                  </div>
                )}
              </section>

              <p className="risk-modal__disclaimer">
                Prediksi eksperimental berdasarkan cuaca dan tutupan pohon. Gunakan sebagai informasi tambahan, bukan satu-satunya dasar keputusan.
              </p>

              {measurements.length > 0 && (
                <section className="risk-modal__measurements" aria-label="Data pendukung prediksi">
                  <h3>Data pendukung</h3>
                  <dl>
                    {measurements.map((item) => (
                      <div key={item.label}>
                        <dt>{item.label}</dt>
                        <dd>{item.value}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </>
          )}

          {userCoords && (
            <TelegramAlertCard
              lat={userCoords.lat}
              lon={userCoords.lon}
              defaultLabel={prediction?.province ? `${prediction.province} (Lokasi pantau)` : 'Lokasi pantau'}
            />
          )}
        </div>

        <footer className="risk-modal__footer">
          {onFocusMap && userCoords ? (
            <button
              type="button"
              className="mp-btn mp-btn--solid risk-modal__button"
              onClick={() => {
                onFocusMap();
                onClose();
              }}
            >
              <MapPinIcon size={15} />
              Pusatkan di peta
            </button>
          ) : <span />}
          <button type="button" className="mp-btn mp-btn--solid risk-modal__button" onClick={onClose}>
            Tutup
          </button>
        </footer>
      </section>
    </div>
  );
};

export default NearbyFireRiskModal;
