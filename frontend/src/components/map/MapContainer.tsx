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
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const hotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const predictiveHotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const reportsLayerRef = useRef<L.LayerGroup | null>(null);
  const userLayerRef = useRef<L.LayerGroup | null>(null);
  const pickedLocationLayerRef = useRef<L.LayerGroup | null>(null);
  const kalimantanLayerRef = useRef<L.GeoJSON | null>(null);
  const maskLayerRef = useRef<L.GeoJSON | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
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

    if (!map.getPane('forestPane')) {
      const forestPane = map.createPane('forestPane');
      forestPane.style.zIndex = '355';
    }

    if (!map.getPane('peatlandPane')) {
      const peatPane = map.createPane('peatlandPane');
      peatPane.style.zIndex = '360';
    }

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
            <div style="font-weight: 700; color: #047857; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#047857" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-5"/><path d="M12 2l-6 7h3l-4 6h5v2h4v-2h5l-4-6h3l-6-7z"/></svg>
              ${provName}
            </div>
            <div><b>Cakupan:</b> Wilayah Daratan Kalimantan Indonesia</div>
            ${baseline ? `<div><b>Tutupan 2000:</b> ~${baseline} Juta Hektare</div>` : ''}
            ${loss ? `<div><b>Akumulasi Kehilangan (2001-2025):</b> ~${loss} Juta Ha</div>` : ''}
            <div style="margin-top: 4px; font-size: 10px; color: #D97706; background: rgba(245, 158, 11, 0.1); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.3);">
              <b>Status Data:</b> Data Demonstrasi (Belum Terverifikasi Raster)
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
                <div style="margin-top: 6px; font-size: 10px; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px;">
                  Poligon gambut adalah layer tematik resmi, bukan konfirmasi kebakaran atau area terbakar.
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



  // Render Penanda Hotspot Satelit (VIIRS)
  useEffect(() => {
    const layerGroup = hotspotsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showHotspots) return;

    // Filter ketat: Hanya tampilkan titik di Kawasan Hutan atau Lahan Gambut Pulau Kalimantan
    const targetHotspots = hotspots.filter((h) => {
      if (h.in_peat !== undefined || h.in_forest !== undefined) {
        return Boolean(h.in_peat || h.in_forest);
      }
      return true;
    });

    // Urutkan agar titik yang terpilih dirender paling akhir (di atas titik lain di Canvas)
    const unselected = targetHotspots.filter((h) => h.id !== selectedHotspot?.id);
    const selected = targetHotspots.find((h) => h.id === selectedHotspot?.id);
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
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; min-width: 190px;">
          <div style="font-weight: 700; color: #CC6F00; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#CC6F00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>
            Anomali Termal Satelit
          </div>
          <div><b>Satelit/Sensor:</b> ${h.satellite} (${h.instrument})</div>
          <div><b>Waktu:</b> ${h.acq_date} pk. ${h.acq_time} UTC</div>
          <div><b>Koordinat:</b> ${h.latitude.toFixed(3)}°, ${h.longitude.toFixed(3)}°</div>
          ${h.province ? `<div><b>Wilayah:</b> ${h.province}</div>` : ''}
          ${h.in_peat ? `<div style="color: #9333ea; font-weight: 600;"><b>Lahan Gambut:</b> ${h.peat_landform || 'Wilayah Gambut'}</div>` : ''}
          ${h.in_forest ? `<div style="color: #15803d; font-weight: 600;"><b>Kawasan Hutan:</b> ${h.forest_name || h.forest_fungsi || 'Kawasan Hutan'}</div>` : ''}
          <div><b>Tingkat Keyakinan:</b> <span style="font-weight: 600; color: ${confidenceColor};">${h.confidence === 'high' ? 'Tinggi' : h.confidence === 'nominal' ? 'Sedang' : 'Rendah'}</span></div>
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

  // Render Penanda Laporan Partisipasi Warga
  useEffect(() => {
    const layerGroup = reportsLayerRef.current;
    if (!layerGroup) return;

    layerGroup.clearLayers();
    if (!showReports) return;

    // Filter laporan: jika status laporan REJECTED (ditolak / batal), titik penanda dihapus dari peta
    const activeReports = reports.filter((r) => r.status !== 'REJECTED');

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
          <div><b>ID:</b> <code>${r.id}</code></div>
          <div><b>Kategori:</b> ${catLabel}</div>
          <div><b>Koordinat:</b> ${r.latitude.toFixed(3)}°, ${r.longitude.toFixed(3)}° <span style="font-size: 9px; color: #64748B;">(disamarkan)</span></div>
          ${r.province ? `<div><b>Wilayah:</b> ${r.province}</div>` : ''}
          <div><b>Waktu Pengamatan:</b> ${r.observed_at_utc.slice(0, 16).replace('T', ' ')} UTC</div>
          <div style="margin-top: 4px; font-style: italic; color: #475569; background: #F8FAFC; padding: 4px; border-radius: 4px; border: 1px solid #E2E8F0;">
            "${shortDesc}"
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

    predictiveHotspots.forEach((p) => {
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

          <div style="margin-top: 6px; font-size: 10px; color: #9A3412; background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 4px; padding: 5px; line-height: 1.35;">
            <b>Kesan Hati-hati:</b> Indikasi potensi kerawanan lingkungan berbasis model cuaca dan kanopi. <b>BUKAN</b> deteksi api fisik satelit NASA FIRMS. Prioritaskan patroli pemantauan lapangan.
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
    if (!userCoords) return;

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

    map.flyTo([userCoords.lat, userCoords.lon], 11, {
      duration: 1.2,
    });
  }, [userCoords, userRisk, onOpenNearbyModal]);

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
    ...(userCoords
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
