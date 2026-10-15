import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';
import { fetchKalimantanBoundaries } from '../../services/api';
import kalimantanGeoJsonFallback from '../../assets/map/kalimantan_provinces.json';
import { Icon } from '../common/Icon';
import zoomInIcon from '../../assets/map/zoom-in.svg';
import zoomOutIcon from '../../assets/map/zoom-out.svg';
import arrowDropdown from '../../assets/map/arrow-dropdown.svg';
import hotspotIcon from '../../assets/map/hotspot.svg';

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

type BasemapType = 'dark' | 'light' | 'osm';

const REPORT_COLOR = '#30AFFF';

const HOTSPOT_COLORS: Record<string, string> = {
  high: '#EF4444',
  nominal: '#CC6F00',
  low: '#EAB308',
};

const FLAME_PATH_STRING =
  'M12 24C16.971 24 21 21 21 15.75C21 13.5 20.25 9.75 17.25 6.75C17.625 9 15.375 9.75 15.375 9.75C16.5 6 13.5 0.75 9 0C9.5355 3 9.75 6 6 9C4.125 10.5 3 13.0935 3 15.75C3 21 7.029 24 12 24ZM12 22.5C9.5145 22.5 7.5 21 7.5 18.375C7.5 17.25 7.875 15.375 9.375 13.875C9.1875 15 10.5 15.75 10.5 15.75C9.9375 13.875 11.25 10.875 13.5 10.5C13.2315 12 13.125 13.5 15 15C15.9375 15.75 16.5 17.046 16.5 18.375C16.5 21 14.4855 22.5 12 22.5Z';

interface CanvasMarkerOptions extends L.CircleMarkerOptions {
  canvasImage?: HTMLCanvasElement;
  iconDisplaySize?: number;
}

// Patch L.Canvas sekali saja agar saat merender circleMarker dengan canvasImage,
// gambar langsung di-blit dengan ctx.drawImage di GPU canvas tanpa ribuan DOM node
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const canvasProto = L.Canvas.prototype as any;
if (!canvasProto._flameCanvasPatched) {
  const originalUpdateCircle = canvasProto._updateCircle;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  canvasProto._updateCircle = function (layer: any) {
    if (!this._drawing || layer._empty()) return;
    if (layer.options.canvasImage) {
      const p = layer._point;
      const ctx = this._ctx;
      const img: HTMLCanvasElement = layer.options.canvasImage;
      const size: number = layer.options.iconDisplaySize || 20;
      ctx.drawImage(img, p.x - size / 2, p.y - size / 2, size, size);
      return;
    }
    originalUpdateCircle.call(this, layer);
  };
  canvasProto._flameCanvasPatched = true;
}

/** Cache offscreen canvas untuk setiap warna dan status terpilih */
const flameCanvasCache = new Map<string, HTMLCanvasElement>();
function getFlameCanvas(color: string, isSelected: boolean): HTMLCanvasElement {
  const cacheKey = `${color}_${isSelected}`;
  const cached = flameCanvasCache.get(cacheKey);
  if (cached) return cached;

  const canvas = document.createElement('canvas');
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const baseSize = isSelected ? 30 : 20;
  canvas.width = baseSize * dpr;
  canvas.height = baseSize * dpr;

  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.scale(dpr, dpr);
    const flameSize = isSelected ? 24 : 16;
    const offset = (baseSize - flameSize) / 2;

    ctx.save();
    ctx.translate(offset, offset);
    ctx.scale(flameSize / 24, flameSize / 24);

    if (typeof Path2D !== 'undefined') {
      const p = new Path2D(FLAME_PATH_STRING);
      if (isSelected) {
        ctx.shadowColor = '#FFFFFF';
        ctx.shadowBlur = 6;
      } else {
        ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';
        ctx.shadowBlur = 2;
      }
      ctx.fillStyle = color;
      ctx.fill(p);
    }
    ctx.restore();
  }

  flameCanvasCache.set(cacheKey, canvas);
  return canvas;
}

const BASEMAP_OPTIONS: { value: BasemapType; label: string }[] = [
  { value: 'light', label: 'Map Terang' },
  { value: 'dark', label: 'Map Gelap' },
  { value: 'osm', label: 'Map Standar' },
];

const LEGEND_ITEMS = [
  { color: HOTSPOT_COLORS.high, label: 'Hotspot Suhu Tinggi', flame: true },
  { color: HOTSPOT_COLORS.nominal, label: 'Hotspot Suhu Sedang', flame: true },
  { color: HOTSPOT_COLORS.low, label: 'Hotspot Suhu Rendah', flame: true },
  { color: REPORT_COLOR, label: 'Laporan Warga', flame: false },
];

/**
 * Menghasilkan poligon inverted mask: area luar Kalimantan tertutup mask,
 * sementara pulau Kalimantan (5 provinsi) tetap terlihat jelas sebagai 'lubang' (holes).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createKalimantanInvertedMask(geoJson: any): any {
  const worldRing: [number, number][] = [
    [-180, 90],
    [180, 90],
    [180, -90],
    [-180, -90],
    [-180, 90],
  ];

  const holes: [number, number][][] = [];

  if (geoJson && Array.isArray(geoJson.features)) {
    for (const feature of geoJson.features) {
      const geom = feature.geometry;
      if (!geom) continue;
      if (geom.type === 'Polygon' && Array.isArray(geom.coordinates)) {
        if (geom.coordinates[0]) {
          holes.push(geom.coordinates[0]);
        }
      } else if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
        for (const poly of geom.coordinates) {
          if (poly && poly[0]) {
            holes.push(poly[0]);
          }
        }
      }
    }
  }

  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [worldRing, ...holes],
    },
    properties: {},
  };
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
  const maskLayerRef = useRef<L.GeoJSON | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kalimantanGeoJson, setKalimantanGeoJson] = useState<any>(kalimantanGeoJsonFallback);
  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showReports, setShowReports] = useState<boolean>(true);
  const [showKalimantanBoundaries] = useState<boolean>(true);
  const [isMapMenuOpen, setIsMapMenuOpen] = useState<boolean>(false);

  const basemap: BasemapType = userBasemap ?? (isDark ? 'dark' : 'light');

  // Inisialisasi Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [-0.5, 114.0], // Fokus awal Kalimantan
      zoom: 6,
      minZoom: 5,
      maxZoom: 18,
      maxBounds: [
        [-8.0, 105.0],
        [8.0, 122.5],
      ],
      maxBoundsViscosity: 0.8,
      zoomControl: false,
      preferCanvas: true,
    });

    // Custom pane untuk mask penutup di luar Kalimantan (di atas basemap tiles, di bawah markers & boundaries)
    if (!map.getPane('maskPane')) {
      const maskPane = map.createPane('maskPane');
      maskPane.style.zIndex = '350';
      maskPane.style.pointerEvents = 'none';
    }

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
      if (container) {
        container.style.cursor = 'crosshair';
      }

      const handleClick = (e: L.LeafletMouseEvent) => {
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
      };
    }
  }, [isPickingLocation, onLocationPicked]);


  // Efek ganti basemap (Esri Gray / Dark / OSM)
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
    }

    const tileLayer = L.tileLayer(url, {
      attribution,
      maxZoom: 18,
    }).addTo(map);

    tileLayerRef.current = tileLayer;
  }, [basemap]);

  // Ambil data batas 5 provinsi dari backend bila tersedia, fallback ke GeoJSON lokal yang sudah dibundle
  useEffect(() => {
    let isSubscribed = true;
    fetchKalimantanBoundaries()
      .then((geojson) => {
        if (!isSubscribed) return;
        if (geojson && Array.isArray(geojson.features) && geojson.features.length > 0) {
          setKalimantanGeoJson(geojson);
        }
      })
      .catch(() => {
        // Fallback sudah aktif dari kalimantanGeoJsonFallback
      });

    return () => {
      isSubscribed = false;
    };
  }, []);

  // Layer Inverted Mask: Menutup area di luar pulau Kalimantan dengan warna latar tema
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (maskLayerRef.current) {
      map.removeLayer(maskLayerRef.current);
      maskLayerRef.current = null;
    }

    if (!kalimantanGeoJson) return;

    const maskGeoJson = createKalimantanInvertedMask(kalimantanGeoJson);
    const maskBgColor = isDark ? '#11100D' : '#FFFDFA';

    const maskLayer = L.geoJSON(maskGeoJson, {
      pane: 'maskPane',
      interactive: false,
      style: {
        fillColor: maskBgColor,
        fillOpacity: 0.92,
        stroke: false,
        weight: 0,
      },
    });

    maskLayer.addTo(map);
    maskLayerRef.current = maskLayer;

    return () => {
      if (maskLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(maskLayerRef.current);
        maskLayerRef.current = null;
      }
    };
  }, [kalimantanGeoJson, isDark]);

  // Layer Poligon Batas 5 Provinsi Kalimantan
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (kalimantanLayerRef.current) {
      map.removeLayer(kalimantanLayerRef.current);
      kalimantanLayerRef.current = null;
    }

    if (!showKalimantanBoundaries || !kalimantanGeoJson) return;

    const layer = L.geoJSON(kalimantanGeoJson, {
      style: {
        color: '#10B981',
        weight: 2,
        dashArray: '4, 4',
        fillColor: '#10B981',
        fillOpacity: 0.05,
      },
      onEachFeature: (feature, l) => {
        const props = feature.properties || {};
        const provName = props.province || props.state || props.name || 'Kalimantan';
        const baseline = props.baseline_treecover_2000_ha
          ? (props.baseline_treecover_2000_ha / 1000000).toFixed(2)
          : null;
        const loss = props.cumulative_loss_2001_2025_ha
          ? (props.cumulative_loss_2001_2025_ha / 1000000).toFixed(2)
          : null;

        l.bindPopup(`
          <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
            <div style="font-weight: 700; color: #047857; margin-bottom: 4px;">🌳 ${provName}</div>
            <div><b>Cakupan:</b> Wilayah Daratan Kalimantan Indonesia</div>
            ${baseline ? `<div><b>Tutupan 2000:</b> ~${baseline} Juta Hektare</div>` : ''}
            ${loss ? `<div><b>Akumulasi Kehilangan (2001-2025):</b> ~${loss} Juta Ha</div>` : ''}
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

    return () => {
      if (kalimantanLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(kalimantanLayerRef.current);
        kalimantanLayerRef.current = null;
      }
    };
  }, [showKalimantanBoundaries, kalimantanGeoJson]);

  // Render Penanda Hotspot Satelit (VIIRS)
  useEffect(() => {
    const layerGroup = hotspotsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showHotspots) return;

    // Urutkan agar titik yang terpilih dirender paling akhir (di atas titik lain di Canvas)
    const unselected = hotspots.filter((h) => h.id !== selectedHotspot?.id);
    const selected = hotspots.find((h) => h.id === selectedHotspot?.id);
    const ordered = selected ? [...unselected, selected] : unselected;

    ordered.forEach((h) => {
      const isSelected = selectedHotspot?.id === h.id;
      const confidenceColor = HOTSPOT_COLORS[h.confidence] ?? HOTSPOT_COLORS.low;
      const displaySize = isSelected ? 30 : 20;
      const canvasImg = getFlameCanvas(confidenceColor, isSelected);

      const marker = L.circleMarker([h.latitude, h.longitude], {
        radius: isSelected ? 15 : 10,
        canvasImage: canvasImg,
        iconDisplaySize: displaySize,
      } as CanvasMarkerOptions);

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 180px;">
          <div style="font-weight: 700; color: #B45309; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
            <span>🔥</span> Anomali Termal Satelit
          </div>
          <div><b>Satelit/Sensor:</b> ${h.satellite} (${h.instrument})</div>
          <div><b>Waktu:</b> ${h.acq_date} pk. ${h.acq_time} UTC</div>
          <div><b>Koordinat:</b> ${h.latitude.toFixed(3)}°, ${h.longitude.toFixed(3)}°</div>
          ${h.province ? `<div><b>Wilayah:</b> ${h.province}</div>` : ''}
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
      const evidence = r.evidence_assessment;
      const assessmentLabel = evidence?.category_result || 'Belum dapat dinilai';
      const badgeConfig = EVIDENCE_BADGE_CONFIG[assessmentLabel] || EVIDENCE_BADGE_CONFIG['Belum dapat dinilai'];

      const strokeColor = isSelected ? '#1E3A2F' : '#0F172A';
      const radius = isSelected ? 9 : 7;

      const marker = L.circleMarker([r.latitude, r.longitude], {
        radius,
        fillColor: REPORT_COLOR,
        color: strokeColor,
        weight: isSelected ? 3 : 1.5,
        opacity: 0.95,
        fillOpacity: 0.85,
      });

      const catLabel = CATEGORY_LABELS[r.category] || r.category;
      const shortDesc = r.description.length > 80 ? `${r.description.slice(0, 80)}...` : r.description;

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 200px;">
          <div style="font-weight: 600; color: #0284C7; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
            <span>📢 Laporan Warga</span>
            <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${badgeConfig.bg}; color: ${badgeConfig.text}; border: 1px solid ${badgeConfig.border};">
              ${badgeConfig.icon} ${assessmentLabel}
            </span>
          </div>
          <div><b>ID:</b> <code>${r.id}</code></div>
          <div><b>Kategori:</b> ${catLabel}</div>
          <div><b>Koordinat:</b> ${r.latitude.toFixed(3)}°, ${r.longitude.toFixed(3)}° <span style="font-size: 9px; color: #64748B;">(disamarkan)</span></div>
          ${r.province ? `<div><b>Wilayah:</b> ${r.province}</div>` : ''}
          <div><b>Waktu Pengamatan:</b> ${r.observed_at_utc.slice(0, 16).replace('T', ' ')} UTC</div>
          <div style="margin-top: 4px; font-style: italic; color: #475569; background: #F8FAFC; padding: 4px; border-radius: 4px; border: 1px solid #E2E8F0;">
            "${shortDesc}"
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

  const currentBasemapLabel = BASEMAP_OPTIONS.find((o) => o.value === basemap)?.label ?? 'Map Terang';

  return (
    <div className={`mp-map ${isDark ? 'mp-map--dark' : ''}`}>
      {/* Banner Mode Pilih Koordinat */}
      {isPickingLocation && (
        <div className="map-picking-banner">
          <span>?? <b>Mode Pemilihan Titik:</b> Klik pada peta untuk memilih lokasi kejadian di Kalimantan.</span>
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
      <div ref={mapContainerRef} className="mp-map__canvas" />

      {/* Kontrol Zoom */}
      <div className="mp-zoom">
        <button type="button" className="mp-zoom__btn" onClick={() => mapInstanceRef.current?.zoomIn()} aria-label="Perbesar peta">
          <Icon src={zoomInIcon} />
        </button>
        <button type="button" className="mp-zoom__btn" onClick={() => mapInstanceRef.current?.zoomOut()} aria-label="Perkecil peta">
          <Icon src={zoomOutIcon} />
        </button>
      </div>

      {/* Floating Map Control */}
      <div className="mp-controls">
        <button type="button" className="mp-controls__pill" onClick={handleFocusKalimantan} title="Fokuskan Peta ke Pulau Kalimantan">
          Fokus Kalimantan
        </button>

        <span className="mp-controls__divider" aria-hidden="true" />

        <button
          type="button"
          role="checkbox"
          aria-checked={showReports}
          className="mp-toggle mp-toggle--reports"
          onClick={() => setShowReports((v) => !v)}
        >
          <span className={`mp-checkbox ${showReports ? 'is-checked' : ''}`} aria-hidden="true">
            {showReports && <CheckMark />}
          </span>
          <span className="mp-toggle__dot" aria-hidden="true" />
          <span>Laporan</span>
        </button>

        <button
          type="button"
          role="checkbox"
          aria-checked={showHotspots}
          className="mp-toggle"
          onClick={() => setShowHotspots((v) => !v)}
        >
          <span className={`mp-checkbox ${showHotspots ? 'is-checked' : ''}`} aria-hidden="true">
            {showHotspots && <CheckMark />}
          </span>
          <Icon src={hotspotIcon} size={14} />
          <span>Hotspot</span>
        </button>

        <span className="mp-controls__divider" aria-hidden="true" />

        <button
          type="button"
          className="mp-controls__select"
          aria-haspopup="listbox"
          aria-expanded={isMapMenuOpen}
          onClick={() => setIsMapMenuOpen((v) => !v)}
        >
          <span>{currentBasemapLabel}</span>
          <Icon src={arrowDropdown} />
        </button>
      </div>

      {isMapMenuOpen && (
        <ul className="mp-menu" role="listbox" aria-label="Pilih jenis peta">
          {BASEMAP_OPTIONS.map((opt) => (
            <li key={opt.value} role="option" aria-selected={basemap === opt.value}>
              <button
                type="button"
                className={`mp-menu__item ${basemap === opt.value ? 'is-active' : ''}`}
                onClick={() => {
                  setUserBasemap(opt.value);
                  setIsMapMenuOpen(false);
                }}
              >
                {opt.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Legend Card */}
      <div className="mp-legend">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="mp-legend__row" style={{ ['--legend-color' as string]: item.color }}>
            {item.flame ? (
              <Icon src={hotspotIcon} size={14} className="mp-legend__flame" />
            ) : (
              <span className="mp-legend__dot" style={{ background: item.color }} />
            )}
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const CheckMark: React.FC = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M6 12L9.6 15.6L16.8 8.4" stroke="#FFFDFA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);