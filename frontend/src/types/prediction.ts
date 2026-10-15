/**
 * Tipe data inferensi model Machine Learning untuk prediksi probabilitas risiko kebakaran hutan/lahan.
 */

export interface PredictionDriver {
  feature: string;
  label: string;
  value: number;
  coefficient: number;
  impact: string;
}

export interface FireRiskPrediction {
  status: 'SUCCESS' | 'UNAVAILABLE' | string;
  message?: string;
  coordinates: {
    lat: number;
    lon: number;
  };
  province?: string;
  risk_probability: number | null;
  risk_percentage: number | null;
  risk_level: 'RENDAH' | 'SEDANG' | 'TINGGI' | 'BELUM_DAPAT_DINILAI' | string;
  risk_color?: 'GREEN' | 'YELLOW' | 'RED' | string;
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
  model_metadata?: {
    model_type?: string;
    features_count?: number;
    roc_auc_evaluation?: number;
  };
}

