export type ConfidenceLevel = 'low' | 'nominal' | 'high';

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
}

export interface HotspotFilterParams {
  startDate?: string;
  endDate?: string;
  regionId?: string;
  satellite?: string;
  minConfidence?: ConfidenceLevel;
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
