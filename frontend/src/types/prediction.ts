/**
 * Tipe data inferensi model Machine Learning untuk prediksi probabilitas risiko kebakaran hutan/lahan.
 */

export interface PredictionDriver {
  feature: string;
  label: string;
  value: number;
  coefficient: number;
  impact: string;
  z_score?: number;
  contribution_to_logit?: number;
  is_imputed?: boolean;
}

export interface DataQualityInfo {
  status: 'COMPLETE' | 'PARTIAL' | 'INSUFFICIENT' | string;
  reliability?: string;
  missing_or_imputed_features?: string[];
  imputation_method?: string;
  imputation_caveat?: string;
  precipitation_metadata?: {
    aggregation?: string;
    calendar_aligned?: boolean;
    semantic_limitation?: string;
    measured_lags?: string[];
    unavailable_lags?: string[];
  };
}

export interface FireRiskPrediction {
  status: 'SUCCESS' | 'OUT_OF_SCOPE' | 'INSUFFICIENT_DATA' | 'UNAVAILABLE' | string;
  message?: string;
  coordinates: {
    lat: number;
    lon: number;
  };
  province?: string;
  risk_probability: number | null;
  risk_percentage: number | null;
  risk_level: 'RENDAH' | 'SEDANG' | 'TINGGI' | 'TIDAK_DAPAT_DINILAI' | 'BELUM_DAPAT_DINILAI' | string;
  risk_label?: string;
  risk_color?: 'GREEN' | 'YELLOW' | 'RED' | 'GRAY' | string;
  primary_drivers?: PredictionDriver[];
  weather_source?: string;
  input_features?: {
    tp?: number;
    tp_1?: number;
    tp_2?: number;
    tp_3?: number;
    tp_4?: number;
    tp_5?: number;
    t2m?: number;
    h2m?: number;
    w10?: number;
    loss_last_prim?: number;
    loss_last_sec?: number;
    f_prim?: number;
    peatd?: number;
    dem?: number;
    [key: string]: number | undefined;
  };
  data_quality?: DataQualityInfo;
  model_metadata?: {
    model_type?: string;
    features_count?: number;
    target_type?: string;
    evaluation_status?: string;
    operational_readiness?: string;
    interpretability_notice?: string;
    roc_auc_evaluation?: number;
  };
}


