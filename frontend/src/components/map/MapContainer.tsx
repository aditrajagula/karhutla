import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';
import {
  fetchKalimantanBoundaries,
  fetchPeatlandGeoJSON,
  fetchForestAreaGeoJSON,
} from '../../services/api';
import type {
  PeatlandGeoJSON,
  ForestAreaGeoJSON,
} from '../../services/api';
import kalimantanGeoJsonFallback from '../../assets/map/kalimantan_provinces.json';
import { getKalimantanLocationDetail, isInsideKalimantan } from '../../services/kalimantanLocation';
import { Icon } from '../common/Icon';
import zoomInIcon from '../../assets/map/zoom-in.svg';
import zoomOutIcon from '../../assets/map/zoom-out.svg';
import arrowDropdown from '../../assets/map/arrow-dropdown.svg';
import hotspotIcon from '../../assets/map/hotspot.svg';
import { PinIcon } from '../common/SvgIcons';
import type { PredictiveHotspotFeature } from '../../types/prediction';

interface MapContainerProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
  predictiveHotspots?: PredictiveHotspotFeature[];
  selectedPredictiveHotspot?: PredictiveHotspotFeature | null;
  onSelectPredictiveHotspot?: (item: PredictiveHotspotFeature) => void;
  reports?: CitizenReport[];
  selectedReport?: CitizenReport | null;
  onSelectReport?: (report: CitizenReport) => void;
  isPickingLocation?: boolean;
  onLocationPicked?: (coords: { lat: number; lng: number }) => void;
  onCancelPickLocation?: () => void;
  isDark?: boolean;
  userCoords?: { lat: number; lon: number; accuracy?: number } | null;
  userRisk?: {
    risk_level: string;
    risk_percentage: number;
    risk_color?: string;
  } | null;
  onOpenNearbyModal?: () => void;
  pickedCoords?: { lat: number; lng: number } | null;
  focusTargetCoords?: { lat: number; lng: number } | null;
}


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

function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16) || 204;
  const g = parseInt(clean.substring(2, 4), 16) || 111;
  const b = parseInt(clean.substring(4, 6), 16) || 0;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Cache offscreen canvas untuk setiap warna dan status terpilih */
const flameCanvasCache = new Map<string, HTMLCanvasElement>();
function getFlameCanvas(color: string, isSelected: boolean): HTMLCanvasElement {
  const cacheKey = `${color}_${isSelected}`;
  const cached = flameCanvasCache.get(cacheKey);
  if (cached) return cached;

  const canvas = document.createElement('canvas');
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  // Kanvas diberi padding melingkar yang lega agar drop shadow dan anti-aliasing tidak pernah terpotong kotak
  const baseSize = isSelected ? 44 : 28;
  canvas.width = baseSize * dpr;
  canvas.height = baseSize * dpr;

  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.scale(dpr, dpr);

    const center = baseSize / 2;
    const badgeRadius = isSelected ? 15 : 10;

    // 1. Soft radial heat halo (selalu berhenti di dalam radius lingkaran kanvas)
    const haloGrad = ctx.createRadialGradient(center, center, badgeRadius * 0.4, center, center, badgeRadius * 1.35);
    haloGrad.addColorStop(0, hexToRgba(color, isSelected ? 0.45 : 0.25));
    haloGrad.addColorStop(1, hexToRgba(color, 0));
    ctx.fillStyle = haloGrad;
    ctx.beginPath();
    ctx.arc(center, center, badgeRadius * 1.35, 0, Math.PI * 2);
    ctx.fill();

    // 2. Lingkaran badge utama dengan drop shadow melingkar yang halus
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.42)';
    ctx.shadowBlur = isSelected ? 6 : 3.5;
    ctx.shadowOffsetY = 1.5;

    ctx.beginPath();
    ctx.arc(center, center, badgeRadius, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // Bingkai lingkaran putih yang bersih dan rapi (crisp white rim)
    ctx.lineWidth = isSelected ? 2.5 : 1.8;
    ctx.strokeStyle = '#FFFFFF';
    ctx.stroke();
    ctx.restore();

    // 3. Jika titik sedang terpilih (selected), tambahkan cincin aksen luar
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(center, center, badgeRadius + 3.5, 0, Math.PI * 2);
      ctx.lineWidth = 1.8;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.stroke();
    }

    // 4. Siluet ikon api putih tajam di tengah badge
    const flameSize = isSelected ? 17 : 12;
    const flameOffset = center - flameSize / 2;

    ctx.save();
    ctx.translate(flameOffset, flameOffset);
    ctx.scale(flameSize / 24, flameSize / 24);

    if (typeof Path2D !== 'undefined') {
      const p = new Path2D(FLAME_PATH_STRING);
      ctx.fillStyle = '#FFFFFF';
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

const BASE_LEGEND_ITEMS = [
  { color: HOTSPOT_COLORS.high, label: 'Hotspot Suhu Tinggi', flame: true },
  { color: HOTSPOT_COLORS.nominal, label: 'Hotspot Suhu Sedang', flame: true },
  { color: HOTSPOT_COLORS.low, label: 'Hotspot Suhu Rendah', flame: true },
  { color: REPORT_COLOR, label: 'Laporan Deforestasi', flame: false },
];

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character] || character);
}

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
  predictiveHotspots = [],
  selectedPredictiveHotspot = null,
  onSelectPredictiveHotspot,
  reports = [],
  selectedReport = null,
  onSelectReport,
  isPickingLocation = false,
  onLocationPicked,
  onCancelPickLocation,
  isDark = false,
  userCoords = null,
  userRisk = null,
  onOpenNearbyModal,
  pickedCoords = null,
  focusTargetCoords = null,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const hotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const fireAnimationLayerRef = useRef<L.LayerGroup | null>(null);
  const fireSvgRendererRef = useRef<L.SVG | null>(null);
  const predictiveHotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const reportsLayerRef = useRef<L.LayerGroup | null>(null);
  const userLayerRef = useRef<L.LayerGroup | null>(null);
  const pickedLocationLayerRef = useRef<L.LayerGroup | null>(null);
  const kalimantanLayerRef = useRef<L.GeoJSON | null>(null);
  const maskLayerRef = useRef<L.GeoJSON | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const refTileLayerRef = useRef<L.TileLayer | null>(null);
  const peatlandLayerRef = useRef<L.GeoJSON | null>(null);
  const peatlandGeoJSONRef = useRef<PeatlandGeoJSON | null>(null);
  const forestLayerRef = useRef<L.GeoJSON | null>(null);
  const forestGeoJSONRef = useRef<ForestAreaGeoJSON | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kalimantanGeoJson, setKalimantanGeoJson] = useState<any>(kalimantanGeoJsonFallback);
  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showPredictiveHotspots, setShowPredictiveHotspots] = useState<boolean>(true);
  const [showReports, setShowReports] = useState<boolean>(true);
  const [showKalimantanBoundaries] = useState<boolean>(true);
  const [showPeatland, setShowPeatland] = useState<boolean>(false);
  const [showForest, setShowForest] = useState<boolean>(false);
  const [peatlandFeatureCount, setPeatlandFeatureCount] = useState<number | null>(null);
  const [forestFeatureCount, setForestFeatureCount] = useState<number | null>(null);
  const [peatlandStatus, setPeatlandStatus] = useState<string | null>(null);
  const [forestStatus, setForestStatus] = useState<string | null>(null);
  const [layerError, setLayerError] = useState<string | null>(null);
  const [isMapMenuOpen, setIsMapMenuOpen] = useState<boolean>(false);

  const basemap: BasemapType = userBasemap ?? (isDark ? 'dark' : 'light');

  // Inisialisasi Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [-0.2, 114.2], // Pusat fokus Pulau Kalimantan
      zoom: 6,
      minZoom: 6,
      maxZoom: 18,
      maxBounds: [
        [-5.2, 108.0],
        [4.8, 119.5],
      ],
      maxBoundsViscosity: 1.0, // Mengunci ketat batas peta pada Pulau Kalimantan saja
      zoomControl: false,
      preferCanvas: true,
    });

    // 1. Custom pane untuk labels basemap (di zIndex 250 agar tertutup maskPane di luar Kalimantan)
    if (!map.getPane('labelsPane')) {
      const labelsPane = map.createPane('labelsPane');
      labelsPane.style.zIndex = '250';
      labelsPane.style.pointerEvents = 'none';
    }

    if (!map.getPane('forestPane')) {
      const forestPane = map.createPane('forestPane');
      forestPane.style.zIndex = '280';
    }

    if (!map.getPane('peatlandPane')) {
      const peatPane = map.createPane('peatlandPane');
      peatPane.style.zIndex = '290';
    }

    // 2. Custom pane untuk mask penutup di luar Kalimantan (zIndex 350: menutupi tiles & labels luar)
    if (!map.getPane('maskPane')) {
      const maskPane = map.createPane('maskPane');
      maskPane.style.zIndex = '350';
      maskPane.style.pointerEvents = 'none';
    }

    // 3. Custom pane untuk efek animasi pembakaran satelit (zIndex 420: di atas mask & polygons)
    if (!map.getPane('fireAnimationPane')) {
      const firePane = map.createPane('fireAnimationPane');
      firePane.style.zIndex = '420';
      firePane.style.pointerEvents = 'none';
    }
    fireSvgRendererRef.current = L.svg({ pane: 'fireAnimationPane' });

    const fireAnimationGroup = L.layerGroup().addTo(map);
    fireAnimationLayerRef.current = fireAnimationGroup;

    const hotspotsGroup = L.layerGroup().addTo(map);
    hotspotsLayerRef.current = hotspotsGroup;

    const predictiveGroup = L.layerGroup().addTo(map);
    predictiveHotspotsLayerRef.current = predictiveGroup;

    const reportsGroup = L.layerGroup().addTo(map);
    reportsLayerRef.current = reportsGroup;

    const userGroup = L.layerGroup().addTo(map);
    userLayerRef.current = userGroup;

    const pickedGroup = L.layerGroup().addTo(map);
    pickedLocationLayerRef.current = pickedGroup;

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      fireAnimationLayerRef.current = null;
      fireSvgRendererRef.current = null;
      tileLayerRef.current = null;
      refTileLayerRef.current = null;
    };
  }, []);

  // Handler mode pilih koordinat di peta
  useEffect(() => {
    const map = mapInstanceRef.current;
    const container = mapContainerRef.current;
    if (!map) return;

    if (isPickingLocation && onLocationPicked) {
      map.closePopup();

      if (container) {
        container.style.cursor = 'crosshair';
      }

      // Nonaktifkan pointer-events pada semua layer interaktif agar klik langsung tembus ke canvas map
      const selectorList = [
        '.leaflet-overlay-pane',
        '.leaflet-marker-pane',
        '.leaflet-shadow-pane',
        '.leaflet-popup-pane',
        '.leaflet-peatlandPane-pane',
        '.leaflet-forestPane-pane',
      ];
      selectorList.forEach((sel) => {
        const el = container?.querySelector(sel) as HTMLElement | null;
        if (el) el.style.pointerEvents = 'none';
      });

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
        selectorList.forEach((sel) => {
          const el = container?.querySelector(sel) as HTMLElement | null;
          if (el) el.style.pointerEvents = '';
        });
      };
    }
  }, [isPickingLocation, onLocationPicked]);

  // Render Penanda Lokasi Terpilih (Pilihan Peta Laporan)
  useEffect(() => {
    const layerGroup = pickedLocationLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!pickedCoords) return;

    const marker = L.circleMarker([pickedCoords.lat, pickedCoords.lng], {
      radius: 9,
      fillColor: '#F59E0B',
      color: '#FFFFFF',
      weight: 3,
      opacity: 1,
      fillOpacity: 1,
    });

    marker.bindPopup(`
      <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
        <div style="font-weight: 700; color: #D97706; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
          <span>📍</span> Titik Terpilih Laporan
        </div>
        <div><b>Koordinat:</b> ${pickedCoords.lat.toFixed(5)}°, ${pickedCoords.lng.toFixed(5)}°</div>
      </div>
    `);

    marker.addTo(layerGroup);
  }, [pickedCoords]);

  // Efek ganti basemap (Esri Gray / Dark / OSM) beserta reference labels nama daerah
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
      tileLayerRef.current = null;
    }
    if (refTileLayerRef.current) {
      map.removeLayer(refTileLayerRef.current);
      refTileLayerRef.current = null;
    }

    let url = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    let refUrl: string | null = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}';
    let attribution = '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ';

    if (basemap === 'dark') {
      url = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
      refUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}';
    } else if (basemap === 'osm') {
      url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
      refUrl = null;
      attribution = '&copy; OpenStreetMap contributors';
    }

    const tileLayer = L.tileLayer(url, {
      attribution,
      maxZoom: 18,
    }).addTo(map);
    tileLayerRef.current = tileLayer;

    if (refUrl) {
      const refLayer = L.tileLayer(refUrl, {
        pane: 'labelsPane',
        maxZoom: 18,
      }).addTo(map);
      refTileLayerRef.current = refLayer;
    }
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
        fillOpacity: 1.0, // 100% Solid Opaque (Menutup total laut & pulau lain di luar Kalimantan)
        stroke: true,
        color: isDark ? '#1E293B' : '#E2E8F0',
        weight: 1.5,
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
        color: '#059669',
        weight: 2,
        dashArray: '5, 5',
        fillColor: 'transparent',
        fillOpacity: 0,
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
          <div style="font-family: inherit; font-size: 12px; line-height: 1.5; min-width: 220px; color: #0F172A;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid #E2E8F0;">
              <div style="font-weight: 700; font-size: 13.5px; color: #065F46; display: flex; align-items: center; gap: 6px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 22v-5"/><path d="M12 2l-6 7h3l-4 6h5v2h4v-2h5l-4-6h3l-6-7z"/>
                </svg>
                ${escapeHtml(provName)}
              </div>
              <span style="font-size: 10px; font-weight: 600; color: #047857; background: #ECFDF5; padding: 2px 7px; border-radius: 999px; border: 1px solid #A7F3D0;">
                Provinsi
              </span>
            </div>

            ${(baseline || loss) ? `
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 6px;">
                ${baseline ? `
                  <div style="background: #F8FAFC; padding: 6px 8px; border-radius: 6px; border: 1px solid #E2E8F0;">
                    <div style="font-size: 10px; color: #64748B;">Tutupan Hutan 2000</div>
                    <div style="font-size: 12.5px; font-weight: 700; color: #0F172A;">${baseline} Jt Ha</div>
                  </div>
                ` : ''}
                ${loss ? `
                  <div style="background: #FEF2F2; padding: 6px 8px; border-radius: 6px; border: 1px solid #FECACA;">
                    <div style="font-size: 10px; color: #991B1B;">Kehilangan (2001-2025)</div>
                    <div style="font-size: 12.5px; font-weight: 700; color: #DC2626;">-${loss} Jt Ha</div>
                  </div>
                ` : ''}
              </div>
            ` : ''}

            <div style="font-size: 10px; color: #64748B; display: flex; justify-content: space-between; align-items: center;">
              <span>Batas Administrasi Wilayah</span>
              <span>Hansen GFC v1.13</span>
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

  // Layer Poligon Gambut Kalimantan (Layer Tematik)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (peatlandLayerRef.current) {
      map.removeLayer(peatlandLayerRef.current);
      peatlandLayerRef.current = null;
    }

    if (!showPeatland) return;

    let isSubscribed = true;
    const controller = new AbortController();

    const loadPeatland = async () => {
      try {
        const geojson =
          peatlandGeoJSONRef.current ||
          (await fetchPeatlandGeoJSON(controller.signal));
        if (!isSubscribed || !mapInstanceRef.current) return;
        peatlandGeoJSONRef.current = geojson;

        const layer = L.geoJSON(geojson, {
          pane: 'peatlandPane',
          style: {
            color: '#7C3AED',
            weight: 1.2,
            fillColor: '#A78BFA',
            fillOpacity: 0.32,
          },
          onEachFeature: (feature, featureLayer) => {
            const properties = feature.properties || {};
            const landform =
              typeof properties.landform === 'string'
                ? escapeHtml(properties.landform)
                : 'Kawasan Gambut';
            const material =
              typeof properties.bhnindk === 'string'
                ? escapeHtml(properties.bhnindk)
                : 'Tidak tersedia';
            const objectId = escapeHtml(properties.objectid || properties.id || '-');

            featureLayer.bindPopup(`
              <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 200px;">
                <div style="font-weight: 700; color: #6D28D9; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
                  <span style="display:inline-block; width:10px; height:10px; background:#A78BFA; border:1px solid #7C3AED; border-radius:2px;"></span>
                  Layer Gambut Kalimantan
                </div>
                <div><b>Klasifikasi:</b> ${landform}</div>
                <div><b>Bahan Induk:</b> ${material}</div>
                <div><b>ID Poligon:</b> ${objectId}</div>
                <div style="margin-top: 6px; font-size: 10px; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px; display: flex; justify-content: space-between;">
                  <span>Peta Sebaran Lahan Gambut</span>
                  <span>BBSDLP / KLHK</span>
                </div>
              </div>
            `);
          },
        });

        layer.addTo(map);
        peatlandLayerRef.current = layer;
        setPeatlandFeatureCount(geojson.features.length);
        setPeatlandStatus(
          `${geojson.features.length.toLocaleString('id-ID')} poligon gambut aktif ditampilkan.`,
        );
      } catch (error: unknown) {
        if (!isSubscribed) return;
        setLayerError(
          error instanceof Error ? error.message : 'Layer gambut gagal dimuat.',
        );
        setPeatlandStatus(null);
      }
    };

    void loadPeatland();
    return () => {
      isSubscribed = false;
      controller.abort();
      if (peatlandLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(peatlandLayerRef.current);
        peatlandLayerRef.current = null;
      }
    };
  }, [showPeatland]);

  // Layer Kawasan Hutan Kalimantan (Layer Poligon Resmi KLHK / SatuPeta)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (forestLayerRef.current) {
      map.removeLayer(forestLayerRef.current);
      forestLayerRef.current = null;
    }

    if (!showForest) return;

    let isSubscribed = true;
    const controller = new AbortController();

    const loadForest = async () => {
      try {
        const geojson =
          forestGeoJSONRef.current ||
          (await fetchForestAreaGeoJSON(controller.signal));
        if (!isSubscribed || !mapInstanceRef.current) return;
        forestGeoJSONRef.current = geojson;

        const layer = L.geoJSON(geojson, {
          pane: 'forestPane',
          style: {
            color: '#059669',
            weight: 1.2,
            fillColor: '#10B981',
            fillOpacity: 0.28,
          },
          onEachFeature: (feature, featureLayer) => {
            const properties = feature.properties || {};
            const forestName = escapeHtml(properties.nkws || properties.namobj || 'Kawasan Hutan');
            const fungsiLabel = escapeHtml(properties.fungsi_label || properties.fungsitap || 'Kawasan Hutan');
            const nosk = escapeHtml(properties.nosktap || '-');
            const objectId = escapeHtml(properties.objectid || properties.id || '-');

            featureLayer.bindPopup(`
              <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 220px;">
                <div style="font-weight: 700; color: #047857; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
                  <span style="display:inline-block; width:10px; height:10px; background:#10B981; border:1px solid #059669; border-radius:2px;"></span>
                  Kawasan Hutan Kalimantan
                </div>
                <div><b>Nama Kawasan:</b> ${forestName}</div>
                <div><b>Fungsi:</b> ${fungsiLabel}</div>
                <div><b>SK Penetapan:</b> ${nosk}</div>
                <div><b>ID Objek:</b> ${objectId}</div>
                <div style="margin-top: 6px; font-size: 10px; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px;">
                  Sumber: Peta Kawasan Hutan Resmi (KLHK / SatuPeta BIG)
                </div>
              </div>
            `);
          },
        });

        layer.addTo(map);
        forestLayerRef.current = layer;
        setForestFeatureCount(geojson.features.length);
        setForestStatus(
          `${geojson.features.length.toLocaleString('id-ID')} poligon kawasan hutan Kalimantan aktif ditampilkan.`
        );
      } catch (error: unknown) {
        if (!isSubscribed) return;
        setLayerError(
          error instanceof Error ? error.message : 'Layer kawasan hutan gagal dimuat.'
        );
        setForestStatus(null);
      }
    };

    void loadForest();
    return () => {
      isSubscribed = false;
      controller.abort();
      if (forestLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(forestLayerRef.current);
        forestLayerRef.current = null;
      }
    };
  }, [showForest]);



  // Render Penanda Hotspot Satelit (VIIRS) & Efek Animasi Pembakaran Berdasarkan Rentang Deteksi
  useEffect(() => {
    const layerGroup = hotspotsLayerRef.current;
    const fireGroup = fireAnimationLayerRef.current;
    if (!layerGroup || !fireGroup) return;

    layerGroup.clearLayers();
    fireGroup.clearLayers();
    if (!showHotspots) return;

    // Filter ketat: Hanya tampilkan titik di dalam Pulau Kalimantan & di Kawasan Hutan / Lahan Gambut
    const targetHotspots = hotspots.filter((h) => {
      const inKalimantan = h.latitude >= -5.2 && h.latitude <= 4.8 && h.longitude >= 108.0 && h.longitude <= 119.5;
      if (!inKalimantan) return false;
      if (h.in_peat !== undefined || h.in_forest !== undefined) {
        return Boolean(h.in_peat || h.in_forest);
      }
      return true;
    });

    // Urutkan agar titik yang terpilih dirender paling akhir (di atas titik lain di Canvas)
    const unselected = targetHotspots.filter((h) => h.id !== selectedHotspot?.id);
    const selected = targetHotspots.find((h) => h.id === selectedHotspot?.id);
    const ordered = selected ? [...unselected, selected] : unselected;

    // 1. RENDER SELURUH TITIK DI CANVAS (Maksimal performa, 0 lag, 60 FPS, GPU blit cepat)
    ordered.forEach((h) => {
      const isSelected = selectedHotspot?.id === h.id;
      const confidenceLevel = h.confidence || 'low';
      const confidenceColor = HOTSPOT_COLORS[confidenceLevel] ?? HOTSPOT_COLORS.low;
      const displaySize = isSelected ? 44 : 28;
      const canvasImg = getFlameCanvas(confidenceColor, isSelected);

      const marker = L.circleMarker([h.latitude, h.longitude], {
        radius: isSelected ? 22 : 14,
        canvasImage: canvasImg,
        iconDisplaySize: displaySize,
      } as CanvasMarkerOptions);

      // Rentang fisik deteksi sensor satelit (footprint dasar ~375m hingga ekspansi berdasarkan intensitas FRP)
      const footprintRadius = Math.min(
        1200,
        Math.max(375, 375 + (h.frp ? Math.round(h.frp * 5) : 0))
      );

      // Resolusi nama Kabupaten/Kota, jarak ke pusat kota/daerah terdekat, dan arah mata angin
      const loc = getKalimantanLocationDetail(h.latitude, h.longitude, h.province);

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.45; min-width: 220px; color: #1E293B;">
          <div style="font-weight: 700; color: ${confidenceColor}; margin-bottom: 2px; display: flex; align-items: center; gap: 5px;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="${confidenceColor}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>
            </svg>
            Anomali Termal Satelit (${confidenceLevel.toUpperCase()})
          </div>
          <div style="font-weight: 700; font-size: 13px; color: #0F172A; margin-top: 4px;">
            ${escapeHtml(loc.kabupaten)}
          </div>
          <div style="font-size: 11px; color: #475569; margin-bottom: 6px;">
            ±${Math.round(loc.distanceKm)} km arah ${escapeHtml(loc.compassDirection)} dari ${escapeHtml(loc.nearestCenter)}<br/>
            <span style="color: #0284C7; font-weight: 600;">${escapeHtml(loc.subRegion)}</span>
          </div>
          <div style="border-top: 1px solid #E2E8F0; padding-top: 5px; display: flex; flex-direction: column; gap: 2px; font-size: 11.5px;">
            <div><b>Provinsi:</b> ${escapeHtml(h.province || loc.subRegion)}</div>
            <div><b>Koordinat:</b> ${h.latitude.toFixed(5)}°, ${h.longitude.toFixed(5)}°</div>
            <div><b>Satelit/Sensor:</b> ${escapeHtml(h.satellite)} (${escapeHtml(h.instrument)})</div>
            <div><b>Waktu Observasi:</b> ${escapeHtml(h.acq_date)} pk. ${escapeHtml(h.acq_time)} UTC</div>
            <div><b>Rentang Sensor:</b> ~${footprintRadius} meter (Pixel 375m)</div>
            ${h.frp ? `<div><b>Daya Termal (FRP):</b> ${h.frp.toFixed(1)} MW</div>` : ''}
            ${h.in_peat ? `<div style="color: #9333ea; font-weight: 600; margin-top: 3px;">⚠️ Terdeteksi di Area Lahan Gambut (${escapeHtml(h.peat_landform || 'Kubah Gambut')})</div>` : ''}
            ${h.in_forest ? `<div style="color: #15803d; font-weight: 600;">🌲 Terdeteksi di Kawasan Hutan (${escapeHtml(h.forest_name || h.forest_fungsi || 'Kawasan Hutan')})</div>` : ''}
          </div>
          <div style="margin-top: 6px; font-size: 10px; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px; display: flex; justify-content: space-between; align-items: center;">
            <span>Sensor Satelit VIIRS 375m</span>
            <span>NASA FIRMS</span>
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.bindTooltip(
        `<div style="font-size: 11px; line-height: 1.3;">
          <b>${escapeHtml(loc.kabupaten)}</b><br/>
          <span style="opacity: 0.85;">±${Math.round(loc.distanceKm)} km dari ${escapeHtml(loc.nearestCenter)}</span>
        </div>`,
        {
          direction: 'top',
          offset: [0, -12],
          className: 'mp-hotspot-tooltip',
        }
      );

      marker.on('click', () => {
        onSelectHotspot(h);
      });

      layerGroup.addLayer(marker);
    });

    // 2. LAYER EFEK ANIMASI PEMBAKARAN (FIRE BURN RANGE ANIMATION)
    // a. Titik yang sedang dipilih pengguna (Selected Hotspot) - Gelombang Panas & Percikan Penuh
    if (selectedHotspot) {
      const h = selectedHotspot;
      const confidenceLevel = h.confidence || 'low';
      const confidenceColor = HOTSPOT_COLORS[confidenceLevel] ?? HOTSPOT_COLORS.low;
      const footprintRadius = Math.min(
        1200,
        Math.max(375, 375 + (h.frp ? Math.round(h.frp * 5) : 0))
      );

      // Perimeter fisik rentang sensor 375m (Pulsing circle SVG murni)
      const perimeterCircle = L.circle([h.latitude, h.longitude], {
        radius: footprintRadius,
        pane: 'fireAnimationPane',
        renderer: fireSvgRendererRef.current || undefined,
        interactive: false,
        className: `fire-burn-perimeter fire-burn-perimeter--${confidenceLevel} is-selected`,
        color: confidenceColor,
        weight: 2.5,
        dashArray: '4, 4',
        fillColor: confidenceColor,
        fillOpacity: 0.22,
      });
      fireGroup.addLayer(perimeterCircle);

      // Gelombang pendaran api membakar intensif 60px
      const auraSize = 60;
      const auraIcon = L.divIcon({
        className: `fire-burn-aura-icon fire-burn-aura--${confidenceLevel} is-selected`,
        html: `
          <div class="fire-burn-wrapper" style="width: ${auraSize}px; height: ${auraSize}px;">
            <div class="fire-burn-wave wave-1"></div>
            <div class="fire-burn-wave wave-2"></div>
            <div class="fire-burn-wave wave-3"></div>
            <div class="fire-burn-core"></div>
            <div class="fire-spark spark-1"></div>
            <div class="fire-spark spark-2"></div>
          </div>
        `,
        iconSize: [auraSize, auraSize],
        iconAnchor: [auraSize / 2, auraSize / 2],
      });

      const auraMarker = L.marker([h.latitude, h.longitude], {
        icon: auraIcon,
        pane: 'fireAnimationPane',
        interactive: false,
      });
      fireGroup.addLayer(auraMarker);
    }

    // b. Efek animasi api membakar untuk titik-titik paling intensif di Kalimantan (Top 16 Titik)
    const activeFires = targetHotspots
      .filter((h) => h.id !== selectedHotspot?.id)
      .sort((a, b) => {
        const confWeight = (c: string) => (c === 'high' ? 3 : c === 'nominal' ? 2 : 1);
        const wDiff = confWeight(b.confidence) - confWeight(a.confidence);
        if (wDiff !== 0) return wDiff;
        return (b.frp || 0) - (a.frp || 0);
      })
      .slice(0, 16);

    activeFires.forEach((h) => {
      const confidenceLevel = h.confidence || 'low';
      const auraSize = 38;
      const auraIcon = L.divIcon({
        className: `fire-burn-aura-icon fire-burn-aura--${confidenceLevel}`,
        html: `
          <div class="fire-burn-wrapper" style="width: ${auraSize}px; height: ${auraSize}px;">
            <div class="fire-burn-wave wave-1"></div>
            <div class="fire-burn-wave wave-2"></div>
            <div class="fire-burn-core"></div>
            <div class="fire-spark spark-1"></div>
          </div>
        `,
        iconSize: [auraSize, auraSize],
        iconAnchor: [auraSize / 2, auraSize / 2],
      });

      const auraMarker = L.marker([h.latitude, h.longitude], {
        icon: auraIcon,
        pane: 'fireAnimationPane',
        interactive: false,
      });
      fireGroup.addLayer(auraMarker);
    });
  }, [hotspots, selectedHotspot, onSelectHotspot, showHotspots]);

  // Render Penanda Laporan Partisipasi Warga
  useEffect(() => {
    const layerGroup = reportsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showReports) return;

    // Filter laporan: hanya di Kalimantan dan bukan status REJECTED
    const activeReports = reports.filter(
      (r) =>
        r.status !== 'REJECTED' &&
        r.latitude >= -5.2 &&
        r.latitude <= 4.8 &&
        r.longitude >= 108.0 &&
        r.longitude <= 119.5
    );

    activeReports.forEach((r) => {
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
      const loc = getKalimantanLocationDetail(r.latitude, r.longitude, r.province || undefined);

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 200px;">
          <div style="font-weight: 600; color: #0284C7; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
            <span style="display: flex; align-items: center; gap: 4px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-5"/><path d="M12 2l-6 7h3l-4 6h5v2h4v-2h5l-4-6h3l-6-7z"/></svg>
              Laporan Deforestasi
            </span>
            <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${badgeConfig.bg}; color: ${badgeConfig.text}; border: 1px solid ${badgeConfig.border}; font-weight: 600;">
              ${assessmentLabel}
            </span>
          </div>
          <div style="font-weight: 700; font-size: 12.5px; color: #0F172A; margin-top: 2px;">${escapeHtml(loc.kabupaten)}</div>
          <div style="font-size: 10.5px; color: #64748B; margin-bottom: 4px;">±${Math.round(loc.distanceKm)} km dari ${escapeHtml(loc.nearestCenter)} (${escapeHtml(loc.subRegion)})</div>
          <div><b>ID:</b> <code>${escapeHtml(r.id)}</code></div>
          <div><b>Kategori:</b> ${escapeHtml(catLabel)}</div>
          <div><b>Koordinat:</b> ${r.latitude.toFixed(3)}°, ${r.longitude.toFixed(3)}° <span style="font-size: 9px; color: #64748B;">(disamarkan)</span></div>
          <div><b>Waktu Pengamatan:</b> ${r.observed_at_utc.slice(0, 16).replace('T', ' ')} UTC</div>
          <div style="margin-top: 4px; font-style: italic; color: #475569; background: #F8FAFC; padding: 4px; border-radius: 4px; border: 1px solid #E2E8F0;">
            "${escapeHtml(shortDesc)}"
          </div>
          ${r.photo_url ? '<div style="margin-top: 4px; color: #0284C7; font-size: 11px; display: flex; align-items: center; gap: 4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg> Ada foto pendukung</div>' : ''}
          ${r.is_duplicate_suspect ? '<div style="margin-top: 2px; color: #D97706; font-size: 10px; font-weight: 600; display: flex; align-items: center; gap: 4px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Indikasi Duplikasi Area</div>' : ''}
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

  // Render Penanda Hotspot Prediksi Model (Harian: Sedang s.d. Tinggi)
  useEffect(() => {
    const layerGroup = predictiveHotspotsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showPredictiveHotspots) return;

    const validPredictive = predictiveHotspots.filter(
      (p) =>
        p.properties.latitude >= -5.2 &&
        p.properties.latitude <= 4.8 &&
        p.properties.longitude >= 108.0 &&
        p.properties.longitude <= 119.5
    );

    validPredictive.forEach((p) => {
      const props = p.properties;
      const isSelected = selectedPredictiveHotspot?.id === props.id;
      const isTinggi = props.risk_level === 'TINGGI';

      // Warna bertema waspada/siaga yang kontras dan berbeda dari ikon api NASA FIRMS
      const cautionColor = isTinggi ? '#EA580C' : '#D97706';
      const borderColor = isTinggi ? '#7C2D12' : '#92400E';
      const badgeBg = isTinggi ? '#FFEDD5' : '#FEF3C7';
      const badgeText = isTinggi ? '#9A3412' : '#92400E';
      const size = isSelected ? 24 : 18;

      // 1. Lingkaran buffer zona waspada bergaris putus-putus (radius 15 km)
      const bufferZone = L.circle([props.latitude, props.longitude], {
        radius: 15000,
        // Zona hanya visual; jangan biarkan poligonnya menutupi klik hotspot lain di dalam radius.
        interactive: false,
        color: cautionColor,
        weight: isSelected ? 2 : 1.2,
        dashArray: '4, 4',
        fillColor: cautionColor,
        fillOpacity: isSelected ? 0.15 : 0.08,
      });
      bufferZone.addTo(layerGroup);

      // 2. Diamond / Belah Ketupat Marker dengan simbol seru waspada
      const diamondIcon = L.divIcon({
        className: 'mp-predictive-diamond-icon',
        html: `
          <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
            <div style="
              width: ${size}px;
              height: ${size}px;
              background: ${cautionColor};
              border: ${isSelected ? '2.5px solid #FFFFFF' : `1.8px solid ${borderColor}`};
              transform: rotate(45deg);
              border-radius: 3px;
              box-shadow: 0 2px 6px rgba(0,0,0,0.35);
              transition: transform 0.2s;
            "></div>
            <div style="
              position: absolute;
              top: 50%;
              left: 50%;
              transform: translate(-50%, -50%);
              font-family: ui-monospace, monospace, sans-serif;
              font-size: ${isSelected ? '12px' : '10px'};
              font-weight: 900;
              color: #FFFFFF;
              pointer-events: none;
              line-height: 1;
              text-shadow: 0 1px 2px rgba(0,0,0,0.4);
            ">!</div>
          </div>
        `,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker([props.latitude, props.longitude], {
        icon: diamondIcon,
        zIndexOffset: isSelected ? 1000 : 500,
      });

      const weather = props.weather_summary || {};
      const tempStr = weather.temperature_2m !== undefined ? `${weather.temperature_2m}°C` : '-';
      const rhStr = weather.humidity_2m !== undefined ? `${weather.humidity_2m}%` : '-';
      const windStr = weather.wind_speed_10m !== undefined ? `${weather.wind_speed_10m} m/s` : '-';
      const rainStr = weather.precipitation_30d !== undefined ? `${weather.precipitation_30d} mm` : '-';

      const popupHtml = `
        <div style="font-family: inherit; font-size: 12px; line-height: 1.45; min-width: 230px;">
          <div style="font-weight: 700; color: ${cautionColor}; margin-bottom: 5px; display: flex; align-items: center; justify-content: space-between;">
            <span style="display: flex; align-items: center; gap: 5px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${cautionColor}" stroke-width="2.5"><polygon points="12,2 22,12 12,22 2,12"/></svg>
              Hotspot Prediksi Model
            </span>
            <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${badgeBg}; color: ${badgeText}; font-weight: 700; border: 1px solid ${borderColor}44;">
              ${props.caution_level} (${props.risk_percentage}%)
            </span>
          </div>
          <div><b>Wilayah:</b> ${props.location_name}</div>
          <div><b>Provinsi:</b> ${props.province}</div>
          <div><b>Koordinat:</b> ${props.latitude.toFixed(4)}°, ${props.longitude.toFixed(4)}°</div>
          <div><b>Periode Prediksi:</b> Harian (${props.prediction_date})</div>
          <div><b>Masa Berlaku:</b> 24 Jam (Hari Ini)</div>
          
          <div style="margin-top: 5px; padding: 5px 6px; background: rgba(0,0,0,0.03); border-radius: 4px; border: 1px solid rgba(0,0,0,0.08); font-size: 11px;">
            <div><b>Cuaca Terkini:</b> ${tempStr} | RH ${rhStr} | Angin ${windStr}</div>
            <div><b>Akumulasi Hujan 30 Hari:</b> ${rainStr}</div>
          </div>

          <div style="margin-top: 6px; font-size: 10.5px; color: #9A3412; background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 4px; padding: 4px 6px; line-height: 1.35;">
            <b>Rekomendasi:</b> Estimasi potensi risiko cuaca & kanopi untuk prioritas patroli lapangan.
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on('click', () => {
        if (onSelectPredictiveHotspot) {
          onSelectPredictiveHotspot(p);
        }
      });

      marker.addTo(layerGroup);
    });
  }, [predictiveHotspots, selectedPredictiveHotspot, onSelectPredictiveHotspot, showPredictiveHotspots]);

  // Efek fokus peta saat titik prediksi model dipilih
  useEffect(() => {
    if (!selectedPredictiveHotspot || !mapInstanceRef.current) return;
    const { latitude, longitude } = selectedPredictiveHotspot.properties;
    mapInstanceRef.current.flyTo([latitude, longitude], 10, { duration: 1.2 });
  }, [selectedPredictiveHotspot]);

  // Efek layer lokasi pengguna GPS & Radius Buffer Risiko
  useEffect(() => {
    const layerGroup = userLayerRef.current;
    const map = mapInstanceRef.current;
    if (!layerGroup || !map) return;

    layerGroup.clearLayers();
    // Hanya tampilkan jika koordinat GPS ada dan berada strictly di wilayah Pulau Kalimantan
    if (!userCoords || !isInsideKalimantan(userCoords.lat, userCoords.lon)) return;

    const riskColor =
      userRisk?.risk_level === 'TINGGI'
        ? '#EF4444'
        : userRisk?.risk_level === 'SEDANG'
        ? '#CC6F00'
        : userRisk?.risk_level === 'RENDAH'
        ? '#10B981'
        : '#6B7280';

    // 1. Lingkaran buffer area sekitar (radius 25 km = 25.000 meter)
    const bufferCircle = L.circle([userCoords.lat, userCoords.lon], {
      radius: 25000,
      color: riskColor,
      weight: 2,
      dashArray: '5, 5',
      fillColor: riskColor,
      fillOpacity: 0.1,
    });
    bufferCircle.addTo(layerGroup);

    // 2. Lingkaran akurasi GPS jika akurasi ada
    if (userCoords.accuracy && userCoords.accuracy > 50) {
      const accuracyCircle = L.circle([userCoords.lat, userCoords.lon], {
        radius: userCoords.accuracy,
        color: '#30AFFF',
        weight: 1,
        fillColor: '#30AFFF',
        fillOpacity: 0.15,
      });
      accuracyCircle.addTo(layerGroup);
    }

    // 3. Pinpoint Marker Lokasi Pengguna
    const marker = L.circleMarker([userCoords.lat, userCoords.lon], {
      radius: 9,
      fillColor: riskColor,
      color: '#FFFFFF',
      weight: 3,
      opacity: 1,
      fillOpacity: 1,
    });

    const popupHtml = `
      <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 180px;">
        <div style="font-weight: 700; color: #2563EB; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
          Posisi GPS Anda
        </div>
        <div><b>Koordinat:</b> ${userCoords.lat.toFixed(4)}°, ${userCoords.lon.toFixed(4)}°</div>
        ${
          userRisk
            ? `<div style="margin-top: 4px;"><b>Risiko Karhutla:</b> <span style="font-weight: 700; color: ${riskColor};">${userRisk.risk_percentage !== null && userRisk.risk_percentage !== undefined ? `RISIKO ${userRisk.risk_level} (${userRisk.risk_percentage.toFixed(1)}%)` : `${userRisk.risk_level}`}</span></div>`
            : '<div style="font-size: 11px; color: #64748B; margin-top: 2px;">Menganalisis cuaca mikro & risiko...</div>'
        }
        <div style="margin-top: 6px; font-size: 10px; color: #64748B;">
          Radius buffer pantauan: 25 km di sekitar lokasi Anda.
        </div>
      </div>
    `;

    marker.bindPopup(popupHtml);
    if (onOpenNearbyModal) {
      marker.on('click', onOpenNearbyModal);
    }
    marker.addTo(layerGroup);

    // CATATAN: map.flyTo sengaja ditiadakan dari effect otomatis ini agar tidak merebut kamera peta saat demo/analisis.
    // Kamera peta hanya berpindah jika pengguna secara eksplisit menekan tombol 'Pusatkan di peta'.
  }, [userCoords, userRisk, onOpenNearbyModal]);

  // Efek fokus kamera saat pengguna secara eksplisit meminta 'Pusatkan di peta'
  useEffect(() => {
    if (!focusTargetCoords || !mapInstanceRef.current) return;
    const { lat, lng } = focusTargetCoords;
    if (isInsideKalimantan(lat, lng)) {
      mapInstanceRef.current.flyTo([lat, lng], 10, {
        duration: 1.0,
      });
    }
  }, [focusTargetCoords]);

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
    // Jika laporan berstatus REJECTED (batal/ditolak), titik tidak ada di peta sehingga tidak perlu panTo
    if (selectedReport.status === 'REJECTED') return;
    mapInstanceRef.current.panTo([selectedReport.latitude, selectedReport.longitude], {
      animate: true,
      duration: 0.5,
    });
  }, [selectedReport]);


  const currentBasemapLabel = BASEMAP_OPTIONS.find((o) => o.value === basemap)?.label ?? 'Map Terang';

  const legendItems = [
    ...BASE_LEGEND_ITEMS,
    ...(userCoords && isInsideKalimantan(userCoords.lat, userCoords.lon)
      ? [
          {
            color:
              userRisk?.risk_level === 'TINGGI'
                ? '#EF4444'
                : userRisk?.risk_level === 'SEDANG'
                ? '#CC6F00'
                : '#10B981',
            label: 'Posisi GPS Anda (25 km)',
            flame: false,
          },
        ]
      : []),
  ];

  return (
    <div className={`mp-map ${isDark ? 'mp-map--dark' : ''} ${isPickingLocation ? 'mp-map--picking' : ''}`}>
      {/* Banner Mode Pilih Koordinat */}
      {isPickingLocation && (
        <div className="map-picking-banner" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <PinIcon size={16} color="#CC6F00" />
          <span><b>Mode Pemilihan Titik:</b> Klik pada peta untuk memilih lokasi kejadian di Kalimantan.</span>
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
                marginLeft: 'auto',
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
          <span>Laporan Deforestasi</span>
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
          <span>Hotspot (FIRMS)</span>
        </button>

        <button
          type="button"
          role="checkbox"
          aria-checked={showPredictiveHotspots}
          className="mp-toggle mp-toggle--predictive"
          onClick={() => setShowPredictiveHotspots((v) => !v)}
          title="Tampilkan Hotspot Prediksi Model Harian (Zona Kerawanan Sedang-Tinggi)"
        >
          <span className={`mp-checkbox ${showPredictiveHotspots ? 'is-checked' : ''}`} aria-hidden="true">
            {showPredictiveHotspots && <CheckMark />}
          </span>
          <span
            style={{
              width: '10px',
              height: '10px',
              transform: 'rotate(45deg)',
              background: '#F59E0B',
              border: '1.2px solid #B45309',
              borderRadius: '2px',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span>Hotspot Prediksi{predictiveHotspots.length > 0 ? ` (${predictiveHotspots.length})` : ''}</span>
        </button>

        <button
          type="button"
          role="checkbox"
          aria-checked={showPeatland}
          className="mp-toggle mp-toggle--peatland"
          onClick={() => {
            if (!showPeatland) setPeatlandStatus('Memuat poligon gambut Kalimantan...');
            setShowPeatland((v) => !v);
          }}
          title="Tampilkan Poligon Sebaran Gambut Kalimantan"
        >
          <span className={`mp-checkbox ${showPeatland ? 'is-checked' : ''}`} aria-hidden="true">
            {showPeatland && <CheckMark />}
          </span>
          <span
            style={{
              width: '12px',
              height: '12px',
              background: '#A78BFA',
              border: '1.2px solid #7C3AED',
              borderRadius: '2px',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span>Gambut{peatlandFeatureCount ? ` (${peatlandFeatureCount})` : ''}</span>
        </button>

        <button
          type="button"
          role="checkbox"
          aria-checked={showForest}
          className="mp-toggle mp-toggle--forest"
          onClick={() => {
            if (!showForest) {
              setForestStatus('Memuat kawasan hutan Kalimantan...');
            }
            setShowForest((v) => !v);
          }}
          title="Tampilkan Poligon Kawasan Hutan Kalimantan (KLHK / SatuPeta)"
        >
          <span className={`mp-checkbox ${showForest ? 'is-checked' : ''}`} aria-hidden="true">
            {showForest && <CheckMark />}
          </span>
          <span
            style={{
              width: '12px',
              height: '12px',
              background: '#10B981',
              border: '1.2px solid #059669',
              borderRadius: '2px',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span>Hutan{forestFeatureCount ? ` (${forestFeatureCount})` : ''}</span>
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
        {legendItems.map((item) => (
          <div key={item.label} className="mp-legend__row" style={{ ['--legend-color' as string]: item.color }}>
            {item.flame ? (
              <Icon src={hotspotIcon} size={14} className="mp-legend__flame" />
            ) : (
              <span className="mp-legend__dot" style={{ background: item.color }} />
            )}
            <span>{item.label}</span>
          </div>
        ))}
        {showPeatland && (
          <div className="mp-legend__row" style={{ ['--legend-color' as string]: '#A78BFA' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                background: '#A78BFA',
                border: '1.2px solid #7C3AED',
                borderRadius: '2px',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            <span>Poligon Gambut (Layer Tematik BIG)</span>
          </div>
        )}
        {showForest && (
          <div className="mp-legend__row" style={{ ['--legend-color' as string]: '#10B981' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                background: '#10B981',
                border: '1.2px solid #059669',
                borderRadius: '2px',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            <span>Kawasan Hutan (Layer Resmi KLHK)</span>
          </div>
        )}
        {showPredictiveHotspots && predictiveHotspots.length > 0 && (
          <div className="mp-legend__row" style={{ ['--legend-color' as string]: '#F59E0B' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                transform: 'rotate(45deg)',
                background: '#F59E0B',
                border: '1.2px solid #B45309',
                borderRadius: '2px',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            <span>Hotspot Prediksi Model (Waspada/Siaga Harian)</span>
          </div>
        )}
        {(peatlandStatus || forestStatus || layerError) && (
          <div
            style={{
              marginTop: '4px',
              fontSize: '11px',
              color: layerError ? '#EF4444' : isDark ? '#94A3B8' : '#64748B',
              borderTop: '1px solid rgba(148, 163, 184, 0.25)',
              paddingTop: '6px',
              lineHeight: 1.35,
            }}
          >
            {layerError || forestStatus || peatlandStatus}
          </div>
        )}
      </div>
    </div>
  );
};

const CheckMark: React.FC = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M6 12L9.6 15.6L16.8 8.4" stroke="#FFFDFA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
