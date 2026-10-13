import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';
import { getThermalCategory } from '../../types/hotspot';
import { FloatingDetailCard } from '../detection/FloatingDetailCard';
import { CustomDropdown } from '../common/CustomDropdown';

interface MapContainerProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot | null) => void;
  isDark?: boolean;
}

const INDONESIA_CENTER: [number, number] = [-0.7893, 113.9213];
const INDONESIA_BOUNDS: [[number, number], [number, number]] = [
  [-11.0, 95.0],
  [6.0, 141.0],
];

type BasemapType = 'dark' | 'light' | 'osm';

export const MapContainer: React.FC<MapContainerProps> = ({
  hotspots,
  selectedHotspot,
  onSelectHotspot,
  isDark = true,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const halosLayerRef = useRef<L.LayerGroup | null>(null);
  const selectionLayerRef = useRef<L.LayerGroup | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const basemap: BasemapType = userBasemap ?? (isDark ? 'dark' : 'light');
  const [isLegendOpen, setIsLegendOpen] = useState<boolean>(true);

  // Inisialisasi Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: INDONESIA_CENTER,
      zoom: 5,
      minZoom: 4,
      maxZoom: 18,
      zoomControl: false,
      preferCanvas: true, // Akselerasi HTML5 Canvas
    });

    // Kontrol zoom modern di pojok kiri atas
    L.control.zoom({ position: 'topleft' }).addTo(map);

    const halosGroup = L.layerGroup().addTo(map);
    const markersGroup = L.layerGroup().addTo(map);
    const selectionGroup = L.layerGroup().addTo(map);

    halosLayerRef.current = halosGroup;
    markersLayerRef.current = markersGroup;
    selectionLayerRef.current = selectionGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Perbarui TileLayer saat basemap berganti
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    let tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    let attribution = '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ';

    if (basemap === 'light') {
      tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    } else if (basemap === 'osm') {
      tileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      attribution = '&copy; OpenStreetMap contributors';
    }

    const tileLayer = L.tileLayer(tileUrl, {
      attribution,
      maxZoom: 16,
    }).addTo(map);

    tileLayerRef.current = tileLayer;
  }, [basemap]);

  // Efek 1: Render Markers & Halos saat list hotspots berubah
  useEffect(() => {
    const markersGroup = markersLayerRef.current;
    const halosGroup = halosLayerRef.current;
    if (!markersGroup || !halosGroup) return;

    markersGroup.clearLayers();
    halosGroup.clearLayers();

    hotspots.forEach((h) => {
      const cat = getThermalCategory(h.frp);
      const pointRadius = cat.tier === 'low' ? 5 : cat.tier === 'mid' ? 7 : 9;
      const haloRadius = cat.tier === 'low' ? 10 : cat.tier === 'mid' ? 14 : 18;

      // 1. Halo aura bercahaya lembut
      const halo = L.circleMarker([h.latitude, h.longitude], {
        radius: haloRadius,
        fillColor: cat.color,
        fillOpacity: cat.tier === 'high' ? 0.35 : cat.tier === 'mid' ? 0.28 : 0.22,
        stroke: false,
        interactive: false,
      });
      halosGroup.addLayer(halo);

      // 2. Inti titik termal dengan rim bersih bercahaya (tanpa garis hitam kusam)
      const marker = L.circleMarker([h.latitude, h.longitude], {
        radius: pointRadius,
        fillColor: cat.color,
        color: 'rgba(255, 255, 255, 0.75)',
        weight: 1,
        opacity: 0.95,
        fillOpacity: 1,
      });

      // Konten Popup Faktual Leaflet
      const popupHtml = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.45; min-width: 190px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 700; color: ${cat.color}; font-size: 13px;">
              ● ${cat.shortLabel}
            </span>
            <span style="font-size: 10px; padding: 1px 6px; border-radius: 999px; background: rgba(255,255,255,0.1); color: #FAFAFA;">
              ${h.satellite}
            </span>
          </div>
          <div style="font-size: 11px; color: #A1A1AA; margin-bottom: 6px;">
            ${h.acq_date} · ${h.acq_time} UTC
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
            <span>FRP: <strong>${h.frp !== undefined && h.frp !== null ? `${h.frp} MW` : '-'}</strong></span>
            <span>Mutu: <strong>${h.confidence}</strong></span>
          </div>
          <div style="font-family: monospace; font-size: 11px; color: #71717A; margin-bottom: 6px;">
            ${h.latitude.toFixed(4)}, ${h.longitude.toFixed(4)}
          </div>
          <div style="font-size: 10.5px; color: #10B981; border-top: 1px solid #33353D; padding-top: 4px; font-weight: 500;">
            Lihat kartu detail & salin koordinat →
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, {
        className: 'dark-map-popup',
        offset: [0, -4],
      });

      marker.on('click', () => {
        onSelectHotspot(h);
      });

      markersGroup.addLayer(marker);
    });
  }, [hotspots, onSelectHotspot]);

  // Efek 2: Render Selection Highlight Ring & Pulse
  useEffect(() => {
    const selGroup = selectionLayerRef.current;
    if (!selGroup) return;

    selGroup.clearLayers();

    if (!selectedHotspot) return;

    const cat = getThermalCategory(selectedHotspot.frp);

    // Cincin luar bercahaya putih + aksen hijau mint saat titik dipilih
    const selHalo = L.circleMarker([selectedHotspot.latitude, selectedHotspot.longitude], {
      radius: 20,
      fillColor: '#10B981',
      fillOpacity: 0.25,
      stroke: false,
      interactive: false,
    });
    const selRing = L.circleMarker([selectedHotspot.latitude, selectedHotspot.longitude], {
      radius: 12,
      fillColor: cat.color,
      color: '#FFFFFF',
      weight: 2.5,
      opacity: 1,
      fillOpacity: 1,
      interactive: false,
    });
    selGroup.addLayer(selHalo);
    selGroup.addLayer(selRing);

    // Pan halus ke titik yang dipilih
    if (mapInstanceRef.current) {
      mapInstanceRef.current.panTo([selectedHotspot.latitude, selectedHotspot.longitude], {
        animate: true,
        duration: 0.25,
      });
    }
  }, [selectedHotspot]);

  const handleResetView = () => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.fitBounds(INDONESIA_BOUNDS, {
      padding: [20, 20],
      animate: true,
    });
  };

  return (
    <div className="map-wrapper">
      {/* Kanvas Leaflet */}
      <div ref={mapContainerRef} className="map-canvas" />

      {/* Floating Toolbar Modern di Kanan Atas */}
      <div className="map-toolbar glass-panel">
        <button
          type="button"
          onClick={handleResetView}
          title="Fokuskan ke seluruh batas kepulauan Indonesia"
          className="map-control-btn"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <polygon points="12 8 8 12 12 16 16 12 12 8" />
          </svg>
          <span>Fokus Indonesia</span>
        </button>

        <CustomDropdown
          label="Basemap"
          value={basemap}
          ariaLabel="Pilih Jenis Basemap"
          align="right"
          className="map-control-dropdown"
          options={[
            { value: 'dark', label: 'Dark Matter (Esri Dark)', shortLabel: 'Dark Matter', icon: '🌙' },
            { value: 'light', label: 'Canvas Terang (Esri Light)', shortLabel: 'Canvas Terang', icon: '☀️' },
            { value: 'osm', label: 'OpenStreetMap', shortLabel: 'OpenStreetMap', icon: '🗺️' },
          ]}
          onChange={(val) => setUserBasemap(val as BasemapType)}
        />
      </div>

      {/* Floating Detail Card Mengambang di Atas Peta */}
      {selectedHotspot && (
        <FloatingDetailCard
          hotspot={selectedHotspot}
          onClose={() => onSelectHotspot(null)}
        />
      )}

      {/* Legenda Modern di Sudut Bawah Peta */}
      <div className={`map-legend-dock glass-panel ${isLegendOpen ? 'open' : 'collapsed'}`}>
        <div className="legend-header">
          <div className="legend-title-group">
            <span className="legend-badge-dot" />
            <span className="legend-title">Skala Suhu & FRP Satelit</span>
          </div>
          <button
            type="button"
            onClick={() => setIsLegendOpen((prev) => !prev)}
            aria-label={isLegendOpen ? 'Tutup Legenda' : 'Buka Legenda'}
            className="legend-toggle-btn"
          >
            {isLegendOpen ? '−' : '+'}
          </button>
        </div>

        {isLegendOpen && (
          <div className="legend-content">
            {/* Tingkat Suhu Tinggi */}
            <div className="legend-tier-row">
              <span className="tier-indicator tier-high" />
              <div className="tier-desc">
                <strong>Suhu Tinggi (Merah)</strong>
                <span>FRP &gt; 50 MW · Intensitas Maksimal</span>
              </div>
            </div>

            {/* Tingkat Suhu Sedang */}
            <div className="legend-tier-row">
              <span className="tier-indicator tier-mid" />
              <div className="tier-desc">
                <strong>Suhu Sedang (Oranye)</strong>
                <span>FRP 15 – 50 MW · Anomali Moderat</span>
              </div>
            </div>

            {/* Tingkat Suhu Rendah */}
            <div className="legend-tier-row">
              <span className="tier-indicator tier-low" />
              <div className="tier-desc">
                <strong>Suhu Rendah (Kuning)</strong>
                <span>FRP &lt; 15 MW · Anomali Awal</span>
              </div>
            </div>

            {/* Catatan Legenda Wajib */}
            <div className="legend-warning-box">
              Warna mengindikasikan intensitas daya pancar termal sensor satelit (FRP), bukan konfirmasi luas kobaran api riil di lapangan.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
