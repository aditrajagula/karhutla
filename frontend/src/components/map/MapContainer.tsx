import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, STATUS_LABELS } from '../../types/report';
import { fetchContextLayers, fetchKalimantanBoundaries } from '../../services/api';

interface MapContainerProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
  reports?: CitizenReport[];
  selectedReport?: CitizenReport | null;
  onSelectReport?: (report: CitizenReport) => void;
  isPickingLocation?: boolean;
  onLocationPicked?: (coords: { lat: number; lng: number }) => void;
  onCancelPickLocation?: () => void;
  isDark?: boolean;
}

const KALIMANTAN_BOUNDS: [[number, number], [number, number]] = [
  [-4.5, 108.5],
  [4.5, 119.5],
];

type BasemapType = 'dark' | 'light' | 'osm' | 'satellite';

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character] || character);
}

export const MapContainer: React.FC<MapContainerProps> = ({
  hotspots,
  selectedHotspot,
  onSelectHotspot,
  reports = [],
  selectedReport = null,
  onSelectReport,
  isPickingLocation = false,
  onLocationPicked,
  onCancelPickLocation,
  isDark = false,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const hotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const reportsLayerRef = useRef<L.LayerGroup | null>(null);
  const kalimantanLayerRef = useRef<L.GeoJSON | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showReports, setShowReports] = useState<boolean>(true);
  const [showKalimantanBoundaries, setShowKalimantanBoundaries] = useState<boolean>(true);
  const [contextStatus, setContextStatus] = useState<string | null>(null);
  const [layerError, setLayerError] = useState<string | null>(null);

  const basemap: BasemapType = userBasemap ?? (isDark ? 'dark' : 'light');

  // Inisialisasi Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [-0.5, 114.0], // Fokus awal Kalimantan
      zoom: 6,
      minZoom: 4,
      maxZoom: 18,
      maxBounds: KALIMANTAN_BOUNDS,
      maxBoundsViscosity: 1,
      zoomControl: false,
      preferCanvas: true,
    });

    L.control.zoom({ position: 'topleft' }).addTo(map);

    const hotspotsGroup = L.layerGroup().addTo(map);
    hotspotsLayerRef.current = hotspotsGroup;

    const reportsGroup = L.layerGroup().addTo(map);
    reportsLayerRef.current = reportsGroup;

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Handler mode pilih koordinat di peta
  useEffect(() => {
    const map = mapInstanceRef.current;
    const container = mapContainerRef.current;
    if (!map) return;

    if (isPickingLocation && onLocationPicked) {
      const overlayPane = container?.querySelector('.leaflet-overlay-pane') as HTMLElement | null;
      const markerPane = container?.querySelector('.leaflet-marker-pane') as HTMLElement | null;

      if (container) {
        container.style.cursor = 'crosshair';
      }
      if (overlayPane) {
        overlayPane.style.pointerEvents = 'none';
      }
      if (markerPane) {
        markerPane.style.pointerEvents = 'none';
      }

      const handleClick = (e: L.LeafletMouseEvent) => {
        map.closePopup();
        onLocationPicked({
          lat: e.latlng.lat,
          lng: e.latlng.lng,
        });
      };

      map.on('click', handleClick);
      return () => {
        map.off('click', handleClick);
        if (container) {
          container.style.cursor = '';
        }
        if (overlayPane) {
          overlayPane.style.pointerEvents = '';
        }
        if (markerPane) {
          markerPane.style.pointerEvents = '';
        }
      };
    }
  }, [isPickingLocation, onLocationPicked]);


  // Basemaps use standard Web Mercator XYZ tile grids.
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    let url = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    let attribution = '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ';

    if (basemap === 'dark') {
      url = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    } else if (basemap === 'osm') {
      url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
      attribution = '&copy; OpenStreetMap contributors';
    } else if (basemap === 'satellite') {
      url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      attribution = 'Tiles &copy; Esri';
    }

    const tileLayer = L.tileLayer(url, {
      attribution,
      maxZoom: 18,
    }).addTo(map);

    tileLayerRef.current = tileLayer;
  }, [basemap]);

  useEffect(() => {
    let isSubscribed = true;
    fetchContextLayers()
      .then((layers) => {
        if (!isSubscribed) return;
        setContextStatus(
          `${layers.forest_layer.status_message} ${layers.peatland_layer.status_message}`,
        );
      })
      .catch((error: unknown) => {
        if (!isSubscribed) return;
        setLayerError(error instanceof Error ? error.message : 'Status layer konteks gagal dimuat.');
      });
    return () => {
      isSubscribed = false;
    };
  }, []);

  // Layer Poligon Batas 5 Provinsi Kalimantan
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (kalimantanLayerRef.current) {
      map.removeLayer(kalimantanLayerRef.current);
      kalimantanLayerRef.current = null;
    }

    if (!showKalimantanBoundaries) return;

    let isSubscribed = true;
    fetchKalimantanBoundaries()
      .then((geojson) => {
        if (!isSubscribed || !mapInstanceRef.current) return;
        const layer = L.geoJSON(geojson, {
          style: {
            color: '#10B981',
            weight: 2,
            dashArray: '4, 4',
            fillColor: '#10B981',
            fillOpacity: 0.05,
          },
          onEachFeature: (feature, l) => {
            const props = feature.properties || {};
            const provName = escapeHtml(props.province || props.name || 'Kalimantan');
            const baseline = props.baseline_treecover_2000_ha
              ? (props.baseline_treecover_2000_ha / 1000000).toFixed(2)
              : '-';
            const loss = props.cumulative_loss_2001_2025_ha
              ? (props.cumulative_loss_2001_2025_ha / 1000000).toFixed(2)
              : '-';

            l.bindPopup(`
              <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
                <div style="font-weight: 700; color: #047857; margin-bottom: 4px;">🌳 ${provName}</div>
                <div><b>Cakupan:</b> Wilayah Daratan Kalimantan Indonesia</div>
                <div><b>Tutupan 2000:</b> ~${baseline} Juta Hektare</div>
                <div><b>Akumulasi Kehilangan (2001-2025):</b> ~${loss} Juta Ha</div>
                <div style="margin-top: 4px; font-size: 10px; color: #D97706; background: rgba(245, 158, 11, 0.1); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.3);">
                  ⚠️ <b>Status Data:</b> Data Demonstrasi (Belum Terverifikasi Raster)
                </div>
                <div style="margin-top: 4px; font-size: 10px; color: #64748B;">
                  Sumber: Hansen Global Forest Change v1.13
                </div>
              </div>
            `);
          },
        });
        layer.addTo(map);
        kalimantanLayerRef.current = layer;
      })
      .catch(() => {
        if (isSubscribed) {
          setLayerError('Batas administratif Kalimantan gagal dimuat.');
        }
      });

    return () => {
      isSubscribed = false;
      if (kalimantanLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(kalimantanLayerRef.current);
        kalimantanLayerRef.current = null;
      }
    };
  }, [showKalimantanBoundaries]);

  // Render Penanda Hotspot Satelit (VIIRS)
  useEffect(() => {
    const layerGroup = hotspotsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showHotspots) return;

    hotspots.forEach((h) => {
      const isSelected = selectedHotspot?.id === h.id;
      const confidenceColor =
        h.confidence === 'high' ? '#EF4444' : h.confidence === 'nominal' ? '#F59E0B' : '#64748B';

      const strokeColor = isSelected ? '#FFFFFF' : '#78350F';
      const radius = isSelected ? 8 : 5;

      const marker = L.circleMarker([h.latitude, h.longitude], {
        radius,
        fillColor: confidenceColor,
        color: strokeColor,
        weight: isSelected ? 3 : 1,
        opacity: 0.9,
        fillOpacity: 0.8,
      });

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 180px;">
          <div style="font-weight: 700; color: #B45309; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
            <span>🔥</span> Anomali Termal Satelit
          </div>
          <div><b>Satelit/Sensor:</b> ${escapeHtml(h.satellite)} (${escapeHtml(h.instrument)})</div>
          <div><b>Waktu:</b> ${escapeHtml(h.acq_date)} pk. ${escapeHtml(h.acq_time)} UTC</div>
          <div><b>Koordinat:</b> ${h.latitude.toFixed(3)}°, ${h.longitude.toFixed(3)}°</div>
          ${h.province ? `<div><b>Wilayah:</b> ${escapeHtml(h.province)}</div>` : ''}
          <div><b>Tingkat Keyakinan:</b> <span style="text-transform: capitalize; font-weight: 600; color: ${confidenceColor};">${h.confidence}</span></div>
          ${h.frp !== undefined ? `<div><b>Daya Termal (FRP):</b> ${h.frp.toFixed(1)} MW</div>` : ''}
          <div style="margin-top: 6px; font-size: 10px; color: #64748B; border-top: 1px solid #E2E8F0; paddingTop: 3px;">
            Indikasi panas permukaan bumi, bukan bukti otomatis kebakaran hutan terbuka.
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.on('click', () => {
        onSelectHotspot(h);
      });

      layerGroup.addLayer(marker);
    });
  }, [hotspots, selectedHotspot, onSelectHotspot, showHotspots]);

  // Render Penanda Laporan Masyarakat
  useEffect(() => {
    const layerGroup = reportsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showReports) return;

    reports.forEach((r) => {
      const isSelected = selectedReport?.id === r.id;
      if (r.status === 'ditolak') return;
      const pending = r.status === 'menunggu_validasi';
      const statusIcon = pending ? null : r.status === 'perlu_tinjauan_lapangan'
        ? '⚠️'
        : r.status === 'terverifikasi_petugas'
          ? '🔥✓'
          : '🔥';
      const statusColor = r.status === 'riwayat_kebakaran_validasi_warga'
        ? '#EA580C'
        : r.status === 'perlu_tinjauan_lapangan'
          ? '#D97706'
          : '#DC2626';
      const marker = pending
        ? L.circleMarker([r.latitude, r.longitude], {
          radius: isSelected ? 9 : 7,
          fillColor: '#2563EB',
          color: isSelected ? '#FFFFFF' : '#1D4ED8',
          weight: isSelected ? 3 : 1.5,
          opacity: 0.95,
          fillOpacity: 0.9,
        })
        : L.marker([r.latitude, r.longitude], {
          icon: L.divIcon({
            className: 'fireguard-report-status-marker',
            html: `<span aria-label="${escapeHtml(STATUS_LABELS[r.status])}" style="color:${statusColor}">${statusIcon}</span>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
          }),
        });

      const catLabel = CATEGORY_LABELS[r.category] || r.category;
      const shortDesc = r.description.length > 80 ? `${r.description.slice(0, 80)}...` : r.description;

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 200px;">
          <div style="font-weight: 600; color: #0284C7; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
            <span>${pending ? '🔵' : statusIcon} ${escapeHtml(STATUS_LABELS[r.status])}</span>
            <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(37, 99, 235, 0.1); color: ${statusColor}; border: 1px solid ${statusColor};">
              ${r.citizen_validation_count || 0} validasi warga
            </span>
          </div>
          <div><b>ID:</b> <code>${escapeHtml(r.id)}</code></div>
          <div><b>Kategori:</b> ${escapeHtml(catLabel)}</div>
          <div><b>Koordinat:</b> ${r.latitude.toFixed(3)}°, ${r.longitude.toFixed(3)}° <span style="font-size: 9px; color: #64748B;">(disamarkan)</span></div>
          ${r.province ? `<div><b>Wilayah:</b> ${escapeHtml(r.province)}</div>` : ''}
          <div><b>Waktu Pengamatan:</b> ${escapeHtml(r.observed_at_utc.slice(0, 16).replace('T', ' '))} UTC</div>
          <div style="margin-top: 4px; font-style: italic; color: #475569; background: #F8FAFC; padding: 4px; border-radius: 4px; border: 1px solid #E2E8F0;">
            "${escapeHtml(shortDesc)}"
          </div>
          ${r.photo_url ? '<div style="margin-top: 4px; color: #0284C7; font-size: 11px;">📷 Ada foto pendukung</div>' : ''}
          ${r.is_duplicate_suspect ? '<div style="margin-top: 2px; color: #D97706; font-size: 10px; font-weight: 600;">⚠️ Indikasi Duplikasi Area</div>' : ''}
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.on('click', () => {
        if (onSelectReport) {
          onSelectReport(r);
        }
      });

      layerGroup.addLayer(marker);
    });
  }, [reports, selectedReport, onSelectReport, showReports]);

  // Efek fokus saat titik satelit dipilih
  useEffect(() => {
    if (!selectedHotspot || !mapInstanceRef.current) return;
    mapInstanceRef.current.panTo([selectedHotspot.latitude, selectedHotspot.longitude], {
      animate: true,
      duration: 0.5,
    });
  }, [selectedHotspot]);

  // Efek fokus saat laporan warga dipilih
  useEffect(() => {
    if (!selectedReport || !mapInstanceRef.current) return;
    mapInstanceRef.current.panTo([selectedReport.latitude, selectedReport.longitude], {
      animate: true,
      duration: 0.5,
    });
  }, [selectedReport]);

  const handleFocusKalimantan = () => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.fitBounds(KALIMANTAN_BOUNDS, {
      padding: [20, 20],
      animate: true,
    });
  };

  return (
    <div className="map-wrapper" style={{ position: 'relative', width: '100%', height: '100%', minHeight: '400px' }}>
      {/* Banner Mode Pilih Koordinat */}
      {isPickingLocation && (
        <div className="map-picking-banner">
          <span>🎯 <b>Mode Pemilihan Titik:</b> Klik pada peta untuk memilih lokasi kejadian di Kalimantan.</span>
          {onCancelPickLocation && (
            <button
              type="button"
              onClick={onCancelPickLocation}
              style={{
                background: '#EF4444',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                padding: '3px 8px',
                fontSize: '11px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Batal
            </button>
          )}
        </div>
      )}

      {/* Kanvas Peta Leaflet */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Floating Toolbar: Kontrol Navigasi, Layer & Basemap */}
      <div
        className="map-floating-controls"
        style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 1000,
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          background: isDark ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.92)',
          padding: '6px',
          borderRadius: '6px',
          border: `1px solid ${isDark ? '#334155' : '#CBD5E1'}`,
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          backdropFilter: 'blur(4px)',
          alignItems: 'center',
        }}
      >
        <button
          type="button"
          onClick={handleFocusKalimantan}
          title="Fokus 5 Provinsi Kalimantan Indonesia"
          className="control-btn"
          style={{
            fontSize: '12px',
            padding: '4px 8px',
            borderRadius: '4px',
            border: '1px solid #059669',
            background: isDark ? 'rgba(5, 150, 105, 0.25)' : '#DCFCE7',
            color: isDark ? '#34D399' : '#047857',
            cursor: 'pointer',
            minHeight: '34px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span>🌴 Fokus Kalimantan</span>
        </button>


        {/* Toggle Layer Batas Kalimantan */}
        <label
          style={{
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            cursor: 'pointer',
            padding: '4px 6px',
            borderRadius: '4px',
            background: isDark ? '#1E293B' : '#F1F5F9',
            border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
            color: isDark ? '#F8FAFC' : '#0F172A',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={showKalimantanBoundaries}
            onChange={(e) => setShowKalimantanBoundaries(e.target.checked)}
          />
          <span style={{ width: '8px', height: '8px', borderRadius: '2px', border: '1px dashed #10B981', display: 'inline-block' }} />
          <span>Batas Kalimantan (5 Prov)</span>
        </label>

        {/* Toggle Layer Hotspots */}
        <label
          style={{
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            cursor: 'pointer',
            padding: '4px 6px',
            borderRadius: '4px',
            background: isDark ? '#1E293B' : '#F1F5F9',
            border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
            color: isDark ? '#F8FAFC' : '#0F172A',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={showHotspots}
            onChange={(e) => setShowHotspots(e.target.checked)}
          />
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#F59E0B', display: 'inline-block' }} />
          <span>Satelit ({hotspots.length})</span>
        </label>

        {/* Toggle Layer Laporan Warga */}
        <label
          style={{
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            cursor: 'pointer',
            padding: '4px 6px',
            borderRadius: '4px',
            background: isDark ? '#1E293B' : '#F1F5F9',
            border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
            color: isDark ? '#F8FAFC' : '#0F172A',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={showReports}
            onChange={(e) => setShowReports(e.target.checked)}
          />
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#0284C7', display: 'inline-block' }} />
          <span>Laporan Warga ({reports.length})</span>
        </label>

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
            minHeight: '34px',
          }}
        >
          <option value="light">Basemap Terang (Esri Canvas)</option>
          <option value="dark">Basemap Gelap (Esri Canvas)</option>
          <option value="osm">Basemap Standar (OSM)</option>
          <option value="satellite">Citra Satelit (Esri)</option>
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
          maxWidth: '280px',
          lineHeight: 1.4,
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: '6px', color: isDark ? '#F8FAFC' : '#0F172A' }}>
          Legenda Lapisan Peta Kalimantan
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: '#F59E0B',
              border: '1px solid #78350F',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span><b>Anomali Termal Satelit</b> (Sensor VIIRS)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: '#0284C7',
              border: '1.5px solid #0F172A',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span><b>Laporan baru</b> (titik biru); divalidasi warga (ikon api)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
          <span
            style={{
              width: '14px',
              height: '8px',
              border: '1.5px dashed #10B981',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span><b>Batas 5 Provinsi Kalimantan</b> (Indonesia)</span>
        </div>
        <div style={{ fontSize: '10px', color: isDark ? '#94A3B8' : '#64748B', borderTop: '1px solid var(--color-border)', paddingTop: '4px' }}>
          Hotspot near-real-time dapat tertunda beberapa jam; bukan konfirmasi kebakaran atau alert darurat.
        </div>
        {(contextStatus || layerError) && (
          <div role={layerError ? 'alert' : 'note'} style={{ marginTop: '5px', fontSize: '10px', color: layerError ? '#B91C1C' : isDark ? '#FBBF24' : '#92400E' }}>
            {layerError || contextStatus}
          </div>
        )}
      </div>
    </div>
  );
};
