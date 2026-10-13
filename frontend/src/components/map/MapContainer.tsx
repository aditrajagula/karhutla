import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';

interface MapContainerProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
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
  isDark = false,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const basemap: BasemapType = userBasemap ?? (isDark ? 'dark' : 'light');

  // Inisialisasi Leaflet Map sekali
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: INDONESIA_CENTER,
      zoom: 5,
      minZoom: 4,
      maxZoom: 18,
      zoomControl: false,
      preferCanvas: true, // Render semua titik via HTML5 Canvas (10-50x lebih cepat daripada SVG DOM)
    });

    // Kontrol zoom di pojok kiri atas
    L.control.zoom({ position: 'topleft' }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
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

    // Basemap publik berkecepatan tinggi tanpa watermark / tanpa batasan API key
    let tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    let attribution = '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ';

    if (basemap === 'dark') {
      tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
      attribution = '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ';
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

  // Perbarui Markers saat list hotspots berubah
  useEffect(() => {
    const layerGroup = markersLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();

    hotspots.forEach((h) => {
      const isSelected = selectedHotspot?.id === h.id;
      
      // Radius dinamis berdasarkan FRP jika ada, default 5px
      const radius = isSelected ? 8 : (h.frp ? Math.min(Math.max(h.frp / 8, 4.5), 10) : 5);

      const marker = L.circleMarker([h.latitude, h.longitude], {
        radius,
        fillColor: isSelected ? '#EF4444' : '#F59E0B', // Thermal Flame Amber
        color: isSelected ? '#991B1B' : '#78350F',
        weight: isSelected ? 2 : 1,
        opacity: 0.9,
        fillOpacity: 0.85,
      });

      // Konten popup informatif faktual tanpa AI buzzwords
      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 170px;">
          <div style="font-weight: 600; color: #1E3A2F; margin-bottom: 4px;">
            Anomali Termal Satelit
          </div>
          <div><b>Koordinat:</b> ${h.latitude.toFixed(4)}, ${h.longitude.toFixed(4)}</div>
          <div><b>Waktu:</b> ${h.acq_date} ${h.acq_time} UTC</div>
          <div><b>Satelit:</b> ${h.satellite} (${h.instrument})</div>
          <div><b>Keyakinan:</b> ${h.confidence}</div>
          <div><b>FRP:</b> ${h.frp !== undefined && h.frp !== null ? `${h.frp} MW` : '-'}</div>
          <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid #E2E8F0; font-size: 11px; color: #64748B;">
            Sumber: ${h.source_provenance === 'NASA_FIRMS_API' ? 'NASA FIRMS VIIRS' : 'Snapshot JOINTS'}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);

      marker.on('click', () => {
        onSelectHotspot(h);
      });

      layerGroup.addLayer(marker);
    });
  }, [hotspots, selectedHotspot, onSelectHotspot]);

  // Efek fokus saat titik dipilih
  useEffect(() => {
    if (!selectedHotspot || !mapInstanceRef.current) return;
    mapInstanceRef.current.panTo([selectedHotspot.latitude, selectedHotspot.longitude], {
      animate: true,
      duration: 0.5,
    });
  }, [selectedHotspot]);

  const handleResetView = () => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.fitBounds(INDONESIA_BOUNDS, {
      padding: [20, 20],
      animate: true,
    });
  };

  return (
    <div className="map-wrapper" style={{ position: 'relative', width: '100%', height: '100%', minHeight: '400px' }}>
      {/* Kanvas Peta Leaflet */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Floating Toolbar: Kontrol Navigasi & Basemap */}
      <div
        className="map-floating-controls"
        style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 1000,
          display: 'flex',
          gap: '6px',
          background: isDark ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.92)',
          padding: '6px',
          borderRadius: '6px',
          border: `1px solid ${isDark ? '#334155' : '#CBD5E1'}`,
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          backdropFilter: 'blur(4px)',
        }}
      >
        <button
          type="button"
          onClick={handleResetView}
          title="Fokus Seluruh Indonesia"
          className="control-btn"
          style={{
            fontSize: '12px',
            padding: '4px 8px',
            borderRadius: '4px',
            border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
            background: isDark ? '#1E293B' : '#F1F5F9',
            color: isDark ? '#F8FAFC' : '#0F172A',
            cursor: 'pointer',
            minHeight: '36px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span>Fokus Indonesia</span>
        </button>

        <select
          aria-label="Pilih Jenis Basemap"
          value={basemap}
          onChange={(e) => setUserBasemap(e.target.value as BasemapType)}
          style={{
            fontSize: '12px',
            padding: '4px 8px',
            borderRadius: '4px',
            border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
            background: isDark ? '#1E293B' : '#F1F5F9',
            color: isDark ? '#F8FAFC' : '#0F172A',
            cursor: 'pointer',
            minHeight: '36px',
          }}
        >
          <option value="light">Basemap Terang (Esri Canvas)</option>
          <option value="dark">Basemap Gelap (Esri Canvas)</option>
          <option value="osm">Basemap Standar (OSM)</option>
        </select>
      </div>

      {/* Legenda Faktual di Sudut Kanan Bawah */}
      <div
        className="map-legend"
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '12px',
          zIndex: 1000,
          background: isDark ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.92)',
          padding: '8px 12px',
          borderRadius: '6px',
          border: `1px solid ${isDark ? '#334155' : '#CBD5E1'}`,
          fontSize: '11px',
          color: isDark ? '#CBD5E1' : '#334155',
          maxWidth: '240px',
          lineHeight: 1.4,
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: '4px', color: isDark ? '#F8FAFC' : '#0F172A' }}>
          Legenda Peta
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: '#F59E0B',
              border: '1px solid #78350F',
              display: 'inline-block',
            }}
          />
          <span>Anomali Termal Satelit VIIRS</span>
        </div>
        <div style={{ fontSize: '10px', color: isDark ? '#94A3B8' : '#64748B', marginTop: '4px' }}>
          Indikasi sensor satelit, bukan konfirmasi kebakaran lapangan.
        </div>
      </div>
    </div>
  );
};
