import type { ConfidenceLevel, Hotspot, HotspotFilterParams, HotspotResponse } from '../types/hotspot';
import type { DataSourceMode, SystemStatus } from '../types/status';

const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
// Pastikan tidak ada trailing slash dan sertakan prefix /api/v1
const cleanBase = rawBase.replace(/\/+$/, '');
const API_BASE_URL = cleanBase.endsWith('/api/v1') ? cleanBase : `${cleanBase}/api/v1`;

interface GeoJSONFeature {
  type: string;
  id?: string | number;
  geometry: {
    type: string;
    coordinates: [number, number]; // [lon, lat] RFC 7946
  };
  properties: {
    observation_time_utc?: string;
    acq_date?: string;
    acq_time?: string;
    satellite?: string;
    instrument?: string;
    confidence?: string;
    version?: string;
    bright_ti4?: number;
    bright_ti5?: number;
    frp?: number;
    daynight?: string;
    province?: string;
  };
}

interface GeoJSONResponse {
  type: string;
  provenance?: {
    data_source?: string;
    status?: string;
    sensor_product?: string;
    is_snapshot?: boolean;
    snapshot_type?: string | null;
    fetched_at_utc?: string | null;
    processed_at_utc?: string;
    observation_date_range?: { min: string | null; max: string | null };
    audit_stats?: Record<string, unknown>;
    status_message?: string;
  };
  features: GeoJSONFeature[];
}

function normalizeConfidence(raw: string | undefined): ConfidenceLevel {
  const c = (raw || '').toLowerCase().trim();
  if (c === 'h' || c === 'high') return 'high';
  if (c === 'l' || c === 'low') return 'low';
  return 'nominal';
}

export async function fetchHotspots(params?: HotspotFilterParams): Promise<HotspotResponse> {
  const query = new URLSearchParams();

  // Parameter rentang hari (default 2 hari sesuai default state filter UI)
  const days = params?.dayRange ?? 2;
  query.append('days', days.toString());

  if (params?.startDate) query.append('start_date', params.startDate);
  if (params?.endDate) query.append('end_date', params.endDate);
  if (params?.regionId) query.append('province', params.regionId);
  if (params?.minConfidence) query.append('confidence', params.minConfidence);

  // Jika mode meminta snapshot secara paksa
  if (params?.mode === 'snapshot') {
    query.append('force_snapshot', 'true');
    query.append('mode', 'snapshot');
  }

  const res = await fetch(`${API_BASE_URL}/hotspots?${query.toString()}`);
  if (!res.ok) {
    throw new Error(`Gagal memuat deteksi hotspot dari server (HTTP ${res.status})`);
  }

  const data: GeoJSONResponse = await res.json();
  const provenance = data.provenance || {};
  const features = Array.isArray(data.features) ? data.features : [];

  const records: Hotspot[] = features.map((feat, idx) => {
    const coords = feat.geometry?.coordinates || [0, 0];
    const lon = coords[0] ?? 0;
    const lat = coords[1] ?? 0;
    const props = feat.properties || {};

    const satCode = props.satellite || 'VIIRS';
    const satLabel = satCode === 'N20' ? 'NOAA-20' : satCode === 'N21' ? 'NOAA-21' : satCode;

    return {
      id: feat.id
        ? String(feat.id)
        : `hotspot-${idx}-${props.acq_date}-${props.acq_time}-${lat.toFixed(4)}-${lon.toFixed(4)}`,
      latitude: lat,
      longitude: lon,
      acq_date: props.acq_date || '',
      acq_time: props.acq_time || '',
      satellite: satLabel,
      instrument: props.instrument || 'VIIRS',
      confidence: normalizeConfidence(props.confidence),
      frp: typeof props.frp === 'number' ? props.frp : undefined,
      daynight: props.daynight === 'N' ? 'N' : 'D',
      source_provenance:
        provenance.data_source ||
        (provenance.is_snapshot ? 'LOCAL_TEAM_SNAPSHOT' : 'NASA_FIRMS_API'),
      province: props.province || undefined,
      brightness: props.bright_ti4 || undefined,
    };
  });

  const isSnapshotMode = Boolean(
    provenance.is_snapshot || provenance.status === 'FALLBACK_LOCAL_SNAPSHOT'
  );

  return {
    mode: isSnapshotMode ? 'snapshot' : 'live',
    count: records.length,
    last_sync_utc: provenance.fetched_at_utc || provenance.processed_at_utc,
    records,
    message: provenance.status_message,
  };
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE_URL}/provenance`);
  if (!res.ok) {
    throw new Error(`Gagal memuat status sistem dari server (HTTP ${res.status})`);
  }
  const data = await res.json();

  const isLive = data.status === 'LIVE_API';
  const mode: DataSourceMode = isLive ? 'live' : 'snapshot';

  return {
    apiConfigured: Boolean(data.data_source === 'NASA_FIRMS_API' || data.status === 'LIVE_API'),
    activeMode: mode,
    lastSyncUtc: data.fetched_at_utc || data.processed_at_utc || null,
    snapshotPath: data.snapshot_type || '',
    disclaimer: data.status_message || '',
  };
}

export interface ContextLayersStatus {
  forest_layer: { available: boolean; source: string; status_message: string };
  peatland_layer: { available: boolean; source: string; status_message: string };
  boundary_layer: { available: boolean; source: string; status_message: string; feature_count?: number };
}

export async function fetchContextLayers(): Promise<ContextLayersStatus> {
  const res = await fetch(`${API_BASE_URL}/context-layers`);
  if (!res.ok) {
    throw new Error(`Gagal memuat status context layers (HTTP ${res.status})`);
  }
  return res.json();
}
