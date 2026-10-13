import React from 'react';
import type { Hotspot } from '../../types/hotspot';
import { getThermalCategory } from '../../types/hotspot';

interface DetectionListProps {
  hotspots: Hotspot[];
  onSelectHotspot: (hotspot: Hotspot) => void;
  selectedId?: string;
}

export const DetectionList: React.FC<DetectionListProps> = ({
  hotspots,
  onSelectHotspot,
  selectedId,
}) => {
  return (
    <div className="hotspot-cards-list">
      {hotspots.slice(0, 100).map((h) => {
        const isSelected = selectedId === h.id;
        const cat = getThermalCategory(h.frp);

        return (
          <button
            key={h.id}
            type="button"
            onClick={() => onSelectHotspot(h)}
            className={`hotspot-item-card ${isSelected ? 'selected' : ''}`}
          >
            {/* Avatar Sirkular Berwarna Tingkat Suhu (Kuning/Oranye/Merah) */}
            <div
              className="tier-avatar"
              style={{
                backgroundColor: cat.color,
                boxShadow: `0 0 0 3px ${cat.halo}`,
              }}
              title={cat.label}
            >
              <span className="tier-avatar-dot" />
            </div>

            {/* Informasi Kartu Dua Baris */}
            <div className="card-info-col">
              {/* Baris 1: Wilayah / Koordinat & Nilai FRP */}
              <div className="card-row-top">
                <span className="card-title font-mono tabular-nums">
                  {h.province ? `Prov. ${h.province}` : `${h.latitude.toFixed(4)}, ${h.longitude.toFixed(4)}`}
                </span>
                {h.frp !== undefined && h.frp !== null && (
                  <span className="card-frp-badge tabular-nums">
                    🔥 {h.frp} MW
                  </span>
                )}
              </div>

              {/* Baris 2: Waktu Observasi UTC & Tingkat Keyakinan */}
              <div className="card-row-bottom">
                <span className="card-meta tabular-nums">
                  {h.acq_date} · {h.acq_time} UTC
                </span>
                <span className="card-conf-tag">
                  {h.confidence}
                </span>
              </div>
            </div>

            {/* Sisi Kanan: Tag Status Ringkas */}
            <div className="card-right-status">
              <span className={`status-badge-chip tier-${cat.tier}`}>
                {cat.shortLabel}
              </span>
            </div>
          </button>
        );
      })}

      {hotspots.length > 100 && (
        <div className="cards-list-footer">
          Menampilkan 100 dari {hotspots.length.toLocaleString('id-ID')} titik untuk performa optimal.
        </div>
      )}
    </div>
  );
};
