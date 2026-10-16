import React, { useEffect } from 'react';
import type { Hotspot } from '../../types/hotspot';
import { FlameIcon, CloseIcon } from '../common/SvgIcons';

interface HotspotDetailModalProps {
  hotspot: Hotspot | null;
  onClose: () => void;
}

export const HotspotDetailModal: React.FC<HotspotDetailModalProps> = ({
  hotspot,
  onClose,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!hotspot) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card">
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FlameIcon size={18} color="#CC6F00" />
            <h3 id="detail-title" className="modal-title">
              Detail Deteksi Anomali Termal
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup detail modal"
            className="modal-close-btn"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="modal-body">
          <div className="detail-row">
            <span className="detail-label">Koordinat:</span>
            <span className="detail-val font-mono">
              {hotspot.latitude.toFixed(5)}, {hotspot.longitude.toFixed(5)}
            </span>
          </div>
          {hotspot.province && (
            <div className="detail-row">
              <span className="detail-label">Provinsi Daratan:</span>
              <span className="detail-val">
                {hotspot.province}
              </span>
            </div>
          )}
          {hotspot.in_peat && (
            <div className="detail-row">
              <span className="detail-label">Lahan Gambut:</span>
              <span className="detail-val" style={{ color: '#9333ea', fontWeight: 600 }}>
                {hotspot.peat_landform || 'Wilayah Gambut Kalimantan'}
              </span>
            </div>
          )}
          {hotspot.in_forest && (
            <div className="detail-row">
              <span className="detail-label">Kawasan Hutan:</span>
              <span className="detail-val" style={{ color: '#16a34a', fontWeight: 600 }}>
                {hotspot.forest_name ? `${hotspot.forest_name} (${hotspot.forest_fungsi || 'Kawasan Hutan'})` : (hotspot.forest_fungsi || 'Kawasan Hutan Kalimantan')}
              </span>
            </div>
          )}
          <div className="detail-row">
            <span className="detail-label">Waktu Observasi:</span>
            <span className="detail-val">
              {hotspot.acq_date} {hotspot.acq_time} UTC
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Platform Satelit & Sensor:</span>
            <span className="detail-val">
              {hotspot.satellite} ({hotspot.instrument})
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Tingkat Keyakinan:</span>
            <span className={`detail-val capitalize conf-text-${hotspot.confidence}`}>
              {hotspot.confidence === 'high' ? 'Tinggi' : hotspot.confidence === 'nominal' ? 'Sedang' : 'Rendah'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">FRP (Fire Radiative Power):</span>
            <span className="detail-val">
              {hotspot.frp !== undefined && hotspot.frp !== null ? `${hotspot.frp} MW` : 'Tidak tersedia'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Orbit / Waktu:</span>
            <span className="detail-val">
              {hotspot.daynight === 'D' ? 'Siang Hari' : 'Malam Hari'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Sumber Provenance:</span>
            <span className="detail-val">
              {hotspot.source_provenance === 'NASA_FIRMS_API'
                ? 'Deteksi Satelit VIIRS NASA FIRMS (Live API)'
                : 'Snapshot Hasil Pengambilan Mandiri Tim (Bukan Benchmark Panitia)'}
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <p className="disclaimer-text">
            Catatan: Anomali termal adalah indikasi sensor satelit untuk ditinjau lapangan, bukan bukti pasti kebakaran lahan.
          </p>
        </div>
      </div>
    </div>
  );
};
