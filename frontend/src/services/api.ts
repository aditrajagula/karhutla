import type { ConfidenceLevel, Hotspot, HotspotFilterParams, HotspotResponse } from '../types/hotspot';
import type { DataSourceMode, SystemStatus } from '../types/status';
import type {
  CitizenReport,
  CitizenReportsResponse,
  CreateCitizenReportPayload,
  CreateReportResponse,
  UpdateReportResponse,
  UpdateReportStatusPayload,
} from '../types/report';

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

/**
 * Mengambil daftar laporan masyarakat dari backend.
 */
export async function fetchCitizenReports(filters?: {
  category?: string;
  status?: string;
  province?: string;
  region?: string;
}): Promise<CitizenReportsResponse> {
  const query = new URLSearchParams();
  if (filters?.category) query.append('category', filters.category);
  if (filters?.status) query.append('status', filters.status);
  if (filters?.province) query.append('province', filters.province);
  if (filters?.region) query.append('region', filters.region);

  const res = await fetch(`${API_BASE_URL}/reports?${query.toString()}`);
  if (!res.ok) {
    throw new Error(`Gagal memuat laporan masyarakat dari server (HTTP ${res.status})`);
  }
  return res.json();
}

/**
 * Mengambil detail satu laporan masyarakat.
 */
export async function fetchCitizenReportDetail(reportId: string): Promise<CitizenReport> {
  const res = await fetch(`${API_BASE_URL}/reports/${reportId}`);
  if (!res.ok) {
    throw new Error(`Laporan tidak ditemukan atau gagal dimuat (HTTP ${res.status})`);
  }
  return res.json();
}

/**
 * Mengirimkan laporan baru dari masyarakat.
 */
export async function submitCitizenReport(
  payload: CreateCitizenReportPayload
): Promise<CreateReportResponse> {
  const res = await fetch(`${API_BASE_URL}/reports`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data?.detail || `Gagal menyimpan laporan (HTTP ${res.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

/**
 * Memperbarui status verifikasi laporan oleh operator (dipertahankan untuk kompatibilitas).
 */
export async function updateReportStatus(
  reportId: string,
  payload: UpdateReportStatusPayload
): Promise<UpdateReportResponse> {
  const res = await fetch(`${API_BASE_URL}/reports/${reportId}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data?.detail || `Gagal memperbarui status laporan (HTTP ${res.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

/**
 * Mengambil ringkasan data kehilangan tutupan pohon Hansen GFC 2025 v1.13 untuk 5 provinsi Kalimantan.
 */
export async function fetchForestLossSummary(): Promise<import('../types/forest').ForestLossSummary> {
  const res = await fetch(`${API_BASE_URL}/forest-loss/summary`);
  if (!res.ok) {
    throw new Error(`Gagal memuat ringkasan tutupan pohon Hansen GFC (HTTP ${res.status})`);
  }
  return res.json();
}

/**
 * Mengambil poligon batas 5 provinsi Kalimantan Indonesia (GeoJSON).
 */
export async function fetchKalimantanBoundaries(): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/boundaries/kalimantan`);
  if (!res.ok) {
    throw new Error(`Gagal memuat batas wilayah 5 provinsi Kalimantan (HTTP ${res.status})`);
  }
  return res.json();
}

import type { FireRiskPrediction } from '../types/prediction';

/**
 * Mengambil estimasi probabilitas risiko kebakaran berbasis model ML dan cuaca real-time.
 */
export async function fetchFireRiskPrediction(
  lat: number,
  lon: number,
  province?: string
): Promise<FireRiskPrediction> {
  const params = new URLSearchParams({ latitude: lat.toString(), longitude: lon.toString() });
  if (province) params.append('province', province);
  const res = await fetch(`${API_BASE_URL}/predict/fire-risk?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Gagal memuat prediksi risiko karhutla (HTTP ${res.status})`);
  }
  return res.json();
}


