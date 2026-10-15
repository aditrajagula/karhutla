import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, STATUS_LABELS } from '../../types/report';
import {
  fetchClassifiedHotspotsGeoJSON,
  fetchContextLayers,
  fetchFirmsMapManifest,
  fetchKalimantanBoundaries,
  fetchPeatlandGeoJSON,
} from '../../services/api';
import type {
  ClassifiedHotspotsGeoJSON,
  FirmsMapManifest,
  PeatlandGeoJSON,
} from '../../services/api';

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
  const peatlandLayerRef = useRef<L.GeoJSON | null>(null);
  const classifiedHotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const classifiedHotspotsLayersRef = useRef<{ peat: L.GeoJSON; nonPeat: L.GeoJSON } | null>(null);
  const peatlandGeoJSONRef = useRef<PeatlandGeoJSON | null>(null);
  const classifiedHotspotsGeoJSONRef = useRef<ClassifiedHotspotsGeoJSON | null>(null);
  const firmsManifestRef = useRef<FirmsMapManifest | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const [userBasemap, setUserBasemap] = useState<BasemapType | null>(null);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showReports, setShowReports] = useState<boolean>(true);
  const [showKalimantanBoundaries, setShowKalimantanBoundaries] = useState<boolean>(true);
  const [showPeatland, setShowPeatland] = useState<boolean>(false);
  const [showClassifiedHotspots, setShowClassifiedHotspots] = useState<boolean>(false);
  const [classifiedHotspotFilter, setClassifiedHotspotFilter] = useState<'all' | 'peat'>('all');
  const [peatlandFeatureCount, setPeatlandFeatureCount] = useState<number | null>(null);
  const [classifiedHotspotCount, setClassifiedHotspotCount] = useState<number | null>(null);
  const [classifiedHotspotInfo, setClassifiedHotspotInfo] = useState<string | null>(null);
  const [peatlandStatus, setPeatlandStatus] = useState<string | null>(null);
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
    const peatlandPane = map.createPane('peatlandPane');
    peatlandPane.style.zIndex = '350';

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
        setContextStatus(layers.forest_layer.status_message);
      })
      .catch((error: unknown) => {
        if (!isSubscribed) return;
        setLayerError(error instanceof Error ? error.message : 'Status layer konteks gagal dimuat.');
      });
    return () => {
      isSubscribed = false;
    };
  }, []);

  // Layer poligon gambut resmi; data disederhanakan khusus untuk tampilan peta.
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
        const geojson = peatlandGeoJSONRef.current
          || await fetchPeatlandGeoJSON(controller.signal);
        if (!isSubscribed || !mapInstanceRef.current) return;
        peatlandGeoJSONRef.current = geojson;

        const layer = L.geoJSON(geojson, {
          pane: 'peatlandPane',
          style: {
            color: '#7C3AED',
            weight: 1,
            fillColor: '#A78BFA',
            fillOpacity: 0.32,
          },
          onEachFeature: (feature, featureLayer) => {
            const properties = feature.properties || {};
            const landform = typeof properties.landform === 'string'
              ? escapeHtml(properties.landform)
              : 'Kawasan gambut';
            const material = typeof properties.bhnindk === 'string'
              ? escapeHtml(properties.bhnindk)
              : 'Tidak tersedia';

            featureLayer.bindPopup(`
              <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
                <div style="font-weight: 700; color: #6D28D9; margin-bottom: 4px;">Layer Gambut Kalimantan</div>
                <div><b>Klasifikasi:</b> ${landform}</div>
                <div><b>Bahan induk:</b> ${material}</div>
                <div style="margin-top: 5px; font-size: 10px; color: #64748B;">
                  Poligon gambut bukan batas area terbakar. Tahun/sumber data perlu diverifikasi dari metadata asal.
                </div>
              </div>
            `);
          },
        });
        layer.addTo(map);
        peatlandLayerRef.current = layer;
        setPeatlandFeatureCount(geojson.features.length);
        setPeatlandStatus(
          `${geojson.features.length.toLocaleString('id-ID')} poligon dimuat. Tahun dan provenance dataset belum tercatat.`,
        );
      } catch (error: unknown) {
        if (!isSubscribed) return;
        setLayerError(error instanceof Error ? error.message : 'Layer gambut gagal dimuat.');
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

  // Dataset FIRMS statis mempertahankan label klasifikasi gambut dari manifest lokal.
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (classifiedHotspotsLayerRef.current) {
      map.removeLayer(classifiedHotspotsLayerRef.current);
      classifiedHotspotsLayerRef.current = null;
    }
    if (!showClassifiedHotspots) return;

    let isSubscribed = true;
    const controller = new AbortController();

    const loadClassifiedHotspots = async () => {
      try {
        const [geojson, manifest] = await Promise.all([
          classifiedHotspotsGeoJSONRef.current
            ? Promise.resolve(classifiedHotspotsGeoJSONRef.current)
            : fetchClassifiedHotspotsGeoJSON(controller.signal),
          firmsManifestRef.current
            ? Promise.resolve(firmsManifestRef.current)
            : fetchFirmsMapManifest(controller.signal),
        ]);
        if (!isSubscribed || !mapInstanceRef.current) return;
        classifiedHotspotsGeoJSONRef.current = geojson;
        firmsManifestRef.current = manifest;

        const peatCount = geojson.features.filter(
          (feature) => feature.properties?.in_peat === true,
        ).length;
        if (!classifiedHotspotsLayersRef.current) {
          const hotspotRenderer = L.canvas({ padding: 0.5 });
          const createLayer = (inPeat: boolean) => L.geoJSON(geojson, {
            filter: (feature) => feature.properties?.in_peat === inPeat,
            pointToLayer: (feature, latlng) => {
              const priority = String(feature.properties?.fire_risk_priority || '');
              const color = priority.startsWith('KRITIS')
                ? '#7F1D1D'
                : priority.startsWith('Tinggi')
                  ? '#DC2626'
                  : priority.startsWith('Sedang')
                    ? '#F97316'
                    : '#64748B';
              return L.circleMarker(latlng, {
                radius: 4,
                color: '#FFFFFF',
                weight: 0.7,
                fillColor: color,
                fillOpacity: 0.9,
                renderer: hotspotRenderer,
              });
            },
            onEachFeature: (feature, featureLayer) => {
              const properties = feature.properties || {};
              const date = escapeHtml(properties.acq_date || '-');
              const time = escapeHtml(String(properties.acq_time ?? '-').padStart(4, '0'));
              const peatClass = escapeHtml(properties.peat_class || 'Tidak diketahui');
              const risk = escapeHtml(properties.fire_risk_priority || 'Tidak tersedia');
              const satellite = escapeHtml(properties.satellite || 'VIIRS');
              const confidence = escapeHtml(properties.confidence || 'Tidak tersedia');
              const frp = typeof properties.frp === 'number'
                ? `${properties.frp.toFixed(2)} MW`
                : 'Tidak tersedia';
              featureLayer.bindPopup(`
                <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
                  <div style="font-weight: 700; color: #B45309; margin-bottom: 4px;">Anomali Termal FIRMS</div>
                  <div><b>Wilayah gambut:</b> ${inPeat ? 'Ya' : 'Tidak'}</div>
                  <div><b>Kelas gambut:</b> ${peatClass}</div>
                  <div><b>Prioritas dataset:</b> ${risk}</div>
                  <div><b>Satelit:</b> ${satellite} (${confidence})</div>
                  <div><b>Waktu:</b> ${date} ${time} UTC</div>
                  <div><b>FRP:</b> ${frp}</div>
                  <div style="margin-top: 5px; font-size: 10px; color: #64748B;">
                    Hotspot adalah indikasi anomali termal, bukan konfirmasi kebakaran atau batas area terbakar.
                  </div>
                </div>
              `);
            },
          });
          classifiedHotspotsLayersRef.current = {
            peat: createLayer(true),
            nonPeat: createLayer(false),
          };
        }

        const preparedLayers = classifiedHotspotsLayersRef.current;
        const visibleLayers = classifiedHotspotFilter === 'peat'
          ? [preparedLayers.peat]
          : [preparedLayers.peat, preparedLayers.nonPeat];
        const layerGroup = L.layerGroup(visibleLayers).addTo(map);
        classifiedHotspotsLayerRef.current = layerGroup;
        const renderedCount = classifiedHotspotFilter === 'peat'
          ? peatCount
          : geojson.features.length;
        setClassifiedHotspotCount(renderedCount);
        setClassifiedHotspotInfo(
          `${renderedCount.toLocaleString('id-ID')} titik ditampilkan; ${peatCount.toLocaleString('id-ID')} berada dalam poligon gambut. Snapshot ${manifest.fetched_at_utc.replace('T', ' ').replace('Z', ' UTC')}.`,
        );
      } catch (error: unknown) {
        if (!isSubscribed) return;
        setLayerError(error instanceof Error ? error.message : 'Dataset hotspot terklasifikasi gagal dimuat.');
        setClassifiedHotspotInfo(null);
      }
    };

    void loadClassifiedHotspots();
    return () => {
      isSubscribed = false;
      controller.abort();
      if (classifiedHotspotsLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(classifiedHotspotsLayerRef.current);
        classifiedHotspotsLayerRef.current = null;
      }
    };
  }, [showClassifiedHotspots, classifiedHotspotFilter]);

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

        {/* Toggle layer sebaran gambut */}
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
            checked={showPeatland}
            onChange={(event) => {
              if (event.target.checked) setPeatlandStatus('Memuat poligon gambut Kalimantan...');
              setShowPeatland(event.target.checked);
            }}
          />
          <span style={{ width: '9px', height: '9px', background: '#A78BFA', border: '1px solid #7C3AED', display: 'inline-block' }} />
          <span>Poligon gambut{peatlandFeatureCount ? ` (${peatlandFeatureCount})` : ''}</span>
        </label>

        {/* Toggle dataset hotspot yang sudah diklasifikasikan dengan poligon gambut */}
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
            checked={showClassifiedHotspots}
            onChange={(event) => {
              if (event.target.checked) {
                setClassifiedHotspotInfo('Memuat snapshot FIRMS terklasifikasi...');
              }
              setShowClassifiedHotspots(event.target.checked);
            }}
          />
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#DC2626', display: 'inline-block' }} />
          <span>Snapshot FIRMS terklasifikasi{classifiedHotspotCount !== null ? ` (${classifiedHotspotCount.toLocaleString('id-ID')})` : ''}</span>
        </label>

        {showClassifiedHotspots && (
          <select
            aria-label="Filter snapshot hotspot berdasarkan wilayah gambut"
            value={classifiedHotspotFilter}
            onChange={(event) => {
              setClassifiedHotspotInfo('Memperbarui filter hotspot...');
              setClassifiedHotspotFilter(event.target.value as 'all' | 'peat');
            }}
            style={{
              fontSize: '11px',
              padding: '4px 6px',
              borderRadius: '4px',
              border: `1px solid ${isDark ? '#475569' : '#CBD5E1'}`,
              background: isDark ? '#1E293B' : '#F1F5F9',
              color: isDark ? '#F8FAFC' : '#0F172A',
              minHeight: '30px',
            }}
          >
            <option value="all">Semua titik snapshot</option>
            <option value="peat">Hanya titik di gambut</option>
          </select>
        )}

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
        {showPeatland && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <span style={{ width: '10px', height: '10px', background: '#A78BFA', border: '1px solid #7C3AED', display: 'inline-block', flexShrink: 0 }} />
            <span><b>Poligon gambut</b> (layer tematik; bukan area terbakar)</span>
          </div>
        )}
        {showClassifiedHotspots && (
          <>
            <div style={{ fontSize: '10px', marginBottom: '4px' }}>
              {classifiedHotspotInfo || 'Memuat dataset hotspot...'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#7F1D1D', display: 'inline-block', flexShrink: 0 }} />
              <span>Prioritas dataset tinggi/kritis; abu-abu = bukan gambut</span>
            </div>
          </>
        )}
        {peatlandStatus && (
          <div style={{ fontSize: '10px', marginBottom: '4px' }}>{peatlandStatus}</div>
        )}
        <div style={{ fontSize: '10px', color: isDark ? '#94A3B8' : '#64748B', borderTop: '1px solid var(--color-border)', paddingTop: '4px' }}>
          Snapshot klasifikasi statis berbeda dari hotspot near-real-time. Hotspot bukan konfirmasi kebakaran atau batas area terbakar.
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
