export type ConfidenceLevel = 'low' | 'nominal' | 'high';
export type ThermalTier = 'low' | 'mid' | 'high';

export interface Hotspot {
  id: string;
  latitude: number;
  longitude: number;
  acq_date: string; // YYYY-MM-DD
  acq_time: string; // HHMM dalam UTC
  satellite: string; // e.g., 'NOAA-20', 'NOAA-21'
  instrument: string; // 'VIIRS'
  confidence: ConfidenceLevel;
  frp?: number; // Fire Radiative Power (MW)
  daynight: 'D' | 'N';
  source_provenance: string; // 'NASA_FIRMS_API' | 'JOINTS_BENCHMARK_SNAPSHOT'
  province?: string;
  brightness?: number;
}

export interface HotspotFilterParams {
  startDate?: string;
  endDate?: string;
  regionId?: string;
  searchQuery?: string;
  satellite?: string;
  minConfidence?: ConfidenceLevel;
  thermalTier?: ThermalTier;
  mode?: 'auto' | 'live' | 'snapshot';
  dayRange?: number;
}

export interface HotspotResponse {
  mode: 'live' | 'snapshot' | string;
  count: number;
  last_sync_utc?: string;
  records: Hotspot[];
  message?: string;
}

export function getThermalCategory(frp?: number): {
  tier: ThermalTier;
  label: string;
  shortLabel: string;
  color: string;
  halo: string;
} {
  if (frp === undefined || frp === null || frp < 15) {
    return {
      tier: 'low',
      label: 'Suhu Rendah (< 15 MW)',
      shortLabel: 'Rendah',
      color: '#EAB308',
      halo: 'rgba(234, 179, 8, 0.22)',
    };
  }
  if (frp <= 50) {
    return {
      tier: 'mid',
      label: 'Suhu Sedang (15-50 MW)',
      shortLabel: 'Sedang',
      color: '#F97316',
      halo: 'rgba(249, 115, 22, 0.26)',
    };
  }
  return {
    tier: 'high',
    label: 'Suhu Tinggi (> 50 MW)',
    shortLabel: 'Tinggi',
    color: '#EF4444',
    halo: 'rgba(239, 68, 68, 0.32)',
  };
}
