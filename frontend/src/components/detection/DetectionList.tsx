import React from 'react';
import type { Hotspot } from '../../types/hotspot';

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
    <div className="detection-list-wrapper">
      <div className="detection-list-header">
        <span className="detection-list-title">Daftar Deteksi Terpilih</span>
        <span className="detection-list-meta">{hotspots.length} rekaman</span>
      </div>

      <div className="detection-items-scroll">
        {hotspots.slice(0, 100).map((h) => {
          const isSelected = selectedId === h.id;
          return (
            <button
              key={h.id}
              type="button"
              onClick={() => onSelectHotspot(h)}
              className={`detection-item-btn ${isSelected ? 'selected' : ''}`}
            >
              <div className="detection-item-info">
                <span className="detection-coord font-mono">
                  {h.latitude.toFixed(4)}, {h.longitude.toFixed(4)}
                  {h.province && <span style={{ marginLeft: '6px', fontWeight: 'normal', opacity: 0.85 }}>• {h.province}</span>}
                </span>
                <span className="detection-time">
                  {h.acq_date} | {h.acq_time} UTC
                </span>
              </div>
              <div className="detection-item-badges">
                {h.frp !== undefined && h.frp !== null && (
                  <span className="badge-frp">
                    {h.frp} MW
                  </span>
                )}
                <span className={`badge-conf conf-${h.confidence}`}>
                  {h.confidence}
                </span>
              </div>
            </button>
          );
        })}
      </div>
      {hotspots.length > 100 && (
        <div className="detection-list-footer">
          Menampilkan 100 dari {hotspots.length} titik pada daftar ringkas.
        </div>
      )}
    </div>
  );
};
