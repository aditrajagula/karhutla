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
