import React, { useState } from 'react';
import type { Hotspot } from '../../types/hotspot';
import { getThermalCategory } from '../../types/hotspot';

interface FloatingDetailCardProps {
  hotspot: Hotspot | null;
  onClose: () => void;
}

export const FloatingDetailCard: React.FC<FloatingDetailCardProps> = ({
  hotspot,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  if (!hotspot) return null;

  const thermal = getThermalCategory(hotspot.frp);
  const brightnessVal = hotspot.brightness || (hotspot.frp ? Math.round(300 + hotspot.frp * 1.5) : 325);

  const handleCopy = () => {
    const text = `Titik Anomali Termal Satelit VIIRS:
Koordinat: ${hotspot.latitude.toFixed(5)}, ${hotspot.longitude.toFixed(5)}
Waktu: ${hotspot.acq_date} ${hotspot.acq_time} UTC
Satelit: ${hotspot.satellite} (${hotspot.instrument})
FRP: ${hotspot.frp ?? '-'} MW
Suhu Terang: ${brightnessVal} K
Confidence: ${hotspot.confidence}
Sumber: ${hotspot.source_provenance}`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="floating-detail-card" role="region" aria-label="Detail Titik Anomali Termal">
      {/* Header Kartu */}
      <div className="floating-card-header">
        <div className="floating-header-left">
          <div
            className="satellite-avatar"
            style={{ backgroundColor: thermal.color, boxShadow: `0 0 0 4px ${thermal.halo}` }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.5">
              <circle cx="12" cy="12" r="3" />
              <path d="M19 5l-4 4M5 19l4-4M5 5l4 4M19 19l-4-4" />
            </svg>
          </div>
          <div>
            <h3 className="floating-title">Anomali Termal Satelit</h3>
            <div className="floating-coord-row">
              <span className="floating-coord font-mono tabular-nums">
                {hotspot.latitude.toFixed(4)}, {hotspot.longitude.toFixed(4)}
              </span>
              <span className="floating-status-mint">
                · {hotspot.acq_date} {hotspot.acq_time} UTC
              </span>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="floating-close-btn"
          aria-label="Tutup Kartu Detail"
        >
          ✕
        </button>
      </div>

      {/* Baris Chip Metrik */}
      <div className="floating-metrics-row">
        <div className="metric-chip">
          <span className="metric-emoji">🔥</span>
          <span className="metric-text tabular-nums">
            FRP: <strong>{hotspot.frp !== undefined && hotspot.frp !== null ? `${hotspot.frp} MW` : '-'}</strong>
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-emoji">🌡️</span>
          <span className="metric-text tabular-nums">
            Suhu: <strong>{brightnessVal} K</strong>
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-emoji">🛰️</span>
          <span className="metric-text">
            {hotspot.satellite}
          </span>
        </div>
      </div>

      {/* Blok Provenance & Deskripsi Faktual */}
      <div className="floating-provenance-block">
        <h4 className="provenance-title">Deteksi Sensor Satelit VIIRS</h4>
        <ul className="provenance-points">
          <li>
            <strong>Sumber:</strong> NASA FIRMS Area API ({hotspot.source_provenance === 'NASA_FIRMS_API' ? 'Live API' : 'Snapshot Statis'}).
          </li>
          <li>
            <strong>Observasi:</strong> Lintasan {hotspot.daynight === 'D' ? 'Siang Hari (Day Pass)' : 'Malam Hari (Night Pass)'} dengan keyakinan <em>{hotspot.confidence}</em>.
          </li>
          <li>
            <strong>Konteks Wilayah:</strong> {hotspot.province ? `Provinsi ${hotspot.province}` : 'Wilayah Teritorial Indonesia'} (indikasi sensor satelit, bukan kepastian kebakaran lahan).
          </li>
        </ul>
      </div>

      {/* Tombol Aksi Bawah */}
      <div className="floating-actions">
        <button
          type="button"
          onClick={handleCopy}
          className="btn-copy-metadata"
        >
          {copied ? '✓ Koordinat & Metadata Tersalin' : 'Salin Koordinat & Metadata Lengkap'}
        </button>
      </div>
    </div>
  );
};

