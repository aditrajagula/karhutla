import type { HotspotFilterParams, HotspotResponse } from '../types/hotspot';
import type { SystemStatus } from '../types/status';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export async function fetchHotspots(params?: HotspotFilterParams): Promise<HotspotResponse> {
  const query = new URLSearchParams();
  if (params?.startDate) query.append('start_date', params.startDate);
  if (params?.endDate) query.append('end_date', params.endDate);
  if (params?.regionId) query.append('region_id', params.regionId);
  if (params?.mode) query.append('mode', params.mode);
  if (params?.minConfidence) query.append('confidence', params.minConfidence);
  if (params?.dayRange) query.append('day_range', params.dayRange.toString());

  const res = await fetch(`${API_BASE_URL}/hotspots?${query.toString()}`);
  if (!res.ok) {
    throw new Error('Gagal memuat deteksi hotspot dari server');
  }
  return res.json();
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE_URL}/status`);
  if (!res.ok) {
    throw new Error('Gagal memuat status sistem');
  }
  return res.json();
}
