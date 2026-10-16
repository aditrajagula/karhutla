/**
 * Tipe data untuk Analisis Perubahan Tutupan Pohon (Hansen Global Forest Change 2025 v1.13).
 */

export interface ProvincialLossData {
  province: string;
  baseline_treecover_2000_ha: number;
  cumulative_loss_2001_2025_ha: number;
  percentage_lost: number;
  annual_loss_ha: Record<string, number>;
  recent_loss_2024_2025_ha: number;
  data_status?: string;
  data_verified?: boolean;
  verification_notes?: string;
}

export interface ForestLossSummary {
  dataset: string;
  source: string;
  documentation_url: string;
  coverage: string;
  excluded_territories: string[];
  data_period: string;
  last_updated: string;
  methodology: string;
  limitations: string[];
  data_status?: string;
  data_verified?: boolean;
  verification_notes?: string;
  total_baseline_treecover_2000_ha: number;
  total_cumulative_loss_2001_2025_ha: number;
  total_percentage_lost: number;
  annual_kalimantan_ha: Record<string, number>;
  provincial_data: ProvincialLossData[];
}

/**
 * Hasil klasifikasi tutupan hutan GLAD Forest Extent 2020 tingkat koordinat.
 */
export type ForestClassification = 'FOREST' | 'NON_FOREST' | 'UNKNOWN';

export interface ForestExtentPointResult {
  status: ForestClassification;
  classification: ForestClassification;
  raw_pixel_value: number | null;
  latitude: number;
  longitude: number;
  tile_id?: string | null;
  pixel_row?: number | null;
  pixel_col?: number | null;
  raster_available: boolean;
  raster_file?: string | null;
  crs?: string | null;
  dataset: string;
  layer: string;
  data_period: string;
  resolution_m: number;
  definition: string;
  scientific_caveat: string;
  error_message?: string | null;
  reason?: string | null;
}
