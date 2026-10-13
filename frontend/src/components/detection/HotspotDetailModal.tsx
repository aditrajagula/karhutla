import React, { useEffect } from 'react';
import type { Hotspot } from '../../types/hotspot';

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
      aria-labelledby="pointdetail-title"
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="point-detail-card">
        <div className="point-detail-header">
          <div>
            <div className="evidence-class-tag">
              <span className="dot-sat" />
              <span>Kelas A: Deteksi Satelit (FIRMS)</span>
            </div>
            {/* Headline wajib sesuai DSG §5 */}
            <h3 id="pointdetail-title" className="point-detail-headline">
              Deteksi aktivitas termal — bukan konfirmasi kebakaran
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup detail modal"
            className="modal-close-btn"
          >
            ✕
          </button>
        </div>

        <div className="point-detail-body">
          <div className="detail-row">
            <span className="detail-label">Koordinat Geospasial</span>
            <span className="detail-val font-mono tabular-nums">
              {hotspot.latitude.toFixed(5)}, {hotspot.longitude.toFixed(5)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Waktu Akuisisi Satelit</span>
            <span className="detail-val tabular-nums">
              {hotspot.acq_date} {hotspot.acq_time} UTC
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Satelit & Instrumen</span>
            <span className="detail-val">
              {hotspot.satellite} ({hotspot.instrument})
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Mutu Deteksi (Confidence)</span>
            <div className="detail-val-col">
              <span className={`conf-badge conf-${hotspot.confidence}`}>
                {hotspot.confidence}
              </span>
              <span className="conf-clarification">
                Confidence adalah mutu sinyal sensor, bukan kepastian kebakaran.
              </span>
            </div>
          </div>
          <div className="detail-row">
            <span className="detail-label">Fire Radiative Power (FRP)</span>
            <span className="detail-val tabular-nums">
              {hotspot.frp !== undefined && hotspot.frp !== null ? `${hotspot.frp} MW` : 'Tidak tersedia'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Waktu Lintasan Satelit</span>
            <span className="detail-val">
              {hotspot.daynight === 'D' ? 'Siang Hari (Day Pass)' : 'Malam Hari (Night Pass)'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Sumber & Provenance</span>
            <span className="detail-val">
              {hotspot.source_provenance === 'NASA_FIRMS_API'
                ? 'NASA FIRMS VIIRS (Live API Pipeline)'
                : 'Snapshot Statis Tim (Benchmark JOINTS 2026)'}
            </span>
          </div>
        </div>

        <div className="point-detail-footer">
          <p className="provenance-disclaimer">
            Data ini menunjukkan anomali radiasi panas yang diindikasikan sensor satelit pada saat melintas. Verifikasi lapangan oleh relawan atau instansi berwenang tetap diperlukan sebelum menarik kesimpulan kondisi di darat.
          </p>
        </div>
      </div>
    </div>
  );
};
