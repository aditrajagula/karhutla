"""
backend/app/prediction_service.py
Service inferensi Machine Learning untuk memprediksi probabilitas risiko karhutla
berdasarkan fitur cuaca mikro terkini (Open-Meteo) dan tutupan kanopi raster (Hansen GFC v1.13).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import pandas as pd

from .config import PREDICTIVE_MODEL_PATH, PREDICTIVE_SCALER_PATH
try:
    from .hansen_tile_reader import read_hansen_pixel, is_coordinate_in_kalimantan
except ImportError:
    read_hansen_pixel = None
    is_coordinate_in_kalimantan = None

from .weather_client import WeatherClient

logger = logging.getLogger(__name__)

# Daftar 14 fitur sesuai model_regresi_logistik.joblib
MODEL_FEATURE_NAMES = [
    "tp", "tp_1", "tp_2", "tp_3", "tp_4", "tp_5",
    "t2m", "h2m", "w10",
    "loss_last_prim", "loss_last_sec",
    "f_prim", "peatd", "dem"
]

FEATURE_HUMAN_LABELS = {
    "tp": "Curah Hujan Bulan Ini",
    "tp_1": "Defisit Curah Hujan 1 Bulan Lalu",
    "tp_2": "Defisit Curah Hujan 2 Bulan Lalu",
    "tp_3": "Defisit Curah Hujan 3 Bulan Lalu",
    "tp_4": "Defisit Curah Hujan 4 Bulan Lalu",
    "tp_5": "Defisit Curah Hujan 5 Bulan Lalu",
    "t2m": "Suhu Udara Permukaan (2m)",
    "h2m": "Kelembaban Relatif Udara (2m)",
    "w10": "Kecepatan Angin (10m)",
    "loss_last_prim": "Kehilangan Hutan Primer Tahun Lalu",
    "loss_last_sec": "Kehilangan Hutan Sekunder Tahun Lalu",
    "f_prim": "Fraksi Kerapatan Kanopi Hutan",
    "peatd": "Kedalaman Lahan Gambut",
    "dem": "Elevasi Topografi (Ketinggian)",
}


class FireRiskPredictionService:
    """Service singleton untuk memuat model dan menjalankan inferensi risiko karhutla."""

    def __init__(
        self,
        model_path: Path = PREDICTIVE_MODEL_PATH,
        scaler_path: Path = PREDICTIVE_SCALER_PATH,
    ):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.weather_client = WeatherClient()
        self.model = None
        self.scaler = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Memuat model dan scaler ke dalam memori."""
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                logger.info(
                    "Model prediksi karhutla dan scaler berhasil dimuat dari %s",
                    self.model_path
                )
            else:
                logger.warning(
                    "File model/scaler tidak ditemukan di: %s atau %s",
                    self.model_path, self.scaler_path
                )
        except Exception as exc:
            logger.error("Gagal memuat model prediksi karhutla: %s", exc)

    def is_available(self) -> bool:
        """Mengecek apakah model dan scaler siap digunakan."""
        return self.model is not None and self.scaler is not None

    def predict_fire_risk(
        self,
        lat: float,
        lon: float,
        province: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Melakukan inferensi probabilitas risiko kebakaran untuk koordinat tertentu.
        1. Query cuaca terkini dari Open-Meteo via WeatherClient.
        2. Query tutupan kanopi dari raster Hansen GFC v1.13.
        3. Normalisasi fitur dengan StandardScaler.
        4. Hitung probabilitas dan tentukan level risiko (RENDAH, SEDANG, TINGGI).
        """
        if not self.is_available():
            return {
                "status": "UNAVAILABLE",
                "message": "Model prediktif belum dimuat di server.",
                "coordinates": {"lat": lat, "lon": lon},
                "province": province,
                "risk_probability": None,
                "risk_percentage": None,
                "risk_level": "TIDAK_DAPAT_DINILAI",
                "risk_label": "Model Tidak Tersedia",
                "risk_color": "GRAY",
                "primary_drivers": [],
            }

        # 1. Validasi cakupan spasial wilayah 5 provinsi Kalimantan
        in_kalimantan = True
        prov_resolved = province
        if is_coordinate_in_kalimantan is not None:
            in_kalimantan, prov_resolved = is_coordinate_in_kalimantan(lat, lon, province=province)

        if not in_kalimantan:
            return {
                "status": "OUT_OF_SCOPE",
                "message": "Koordinat berada di luar wilayah 5 provinsi Kalimantan (model prediktif tidak dapat diterapkan).",
                "coordinates": {"lat": lat, "lon": lon},
                "province": prov_resolved or province or "Di Luar Cakupan",
                "risk_probability": None,
                "risk_percentage": None,
                "risk_level": "TIDAK_DAPAT_DINILAI",
                "risk_label": "Di Luar Cakupan",
                "risk_color": "GRAY",
                "primary_drivers": [],
                "data_quality": {
                    "status": "OUT_OF_SCOPE",
                    "reliability": "NOT_ASSESSABLE",
                    "reason": "Koordinat berada di luar wilayah 5 provinsi Kalimantan.",
                    "missing_or_imputed_features": ["f_prim", "peatd", "loss_last_prim", "loss_last_sec"],
                },
                "model_metadata": {
                    "model_type": "Logistic Regression Baseline (ERA5 2002–2018)",
                    "features_count": len(MODEL_FEATURE_NAMES),
                    "target_type": "Deteksi Anomali Radiasi Termal Satelit (FRP > 0) Resolusi ~25km, BUKAN konfirmasi kebakaran darat",
                    "evaluation_status": "HISTORICAL_BENCHMARK_ONLY",
                    "operational_readiness": "PROTOTIPE_EKSPERIMENTAL",
                    "interpretability_notice": "Lokasi berada di luar cakupan pelatihan model Kalimantan.",
                }
            }

        # 2. Ambil data cuaca dari Open-Meteo (dengan fallback aman)
        weather = self.weather_client.fetch_weather_features(lat, lon)

        # 3. Ambil data vegetasi dari Hansen Raster 30m jika berada di cakupan tile
        treecover = None
        detected_prov = prov_resolved or province
        if read_hansen_pixel is not None:
            try:
                hansen_res = read_hansen_pixel(lat=lat, lon=lon, province=province)
                if getattr(hansen_res, "status", None) == "OUT_OF_SCOPE":
                    return {
                        "status": "OUT_OF_SCOPE",
                        "message": "Tile geospasial berada di luar cakupan tile resmi Kalimantan.",
                        "coordinates": {"lat": lat, "lon": lon},
                        "province": getattr(hansen_res, "province", None) or detected_prov or "Di Luar Cakupan",
                        "risk_probability": None,
                        "risk_percentage": None,
                        "risk_level": "TIDAK_DAPAT_DINILAI",
                        "risk_label": "Di Luar Cakupan",
                        "risk_color": "GRAY",
                        "primary_drivers": [],
                        "data_quality": {
                            "status": "OUT_OF_SCOPE",
                            "reliability": "NOT_ASSESSABLE",
                            "reason": "Tile geospasial di luar cakupan resmi Kalimantan.",
                            "missing_or_imputed_features": ["f_prim", "peatd", "loss_last_prim", "loss_last_sec"],
                        },
                        "model_metadata": {
                            "model_type": "Logistic Regression Baseline (ERA5 2002–2018)",
                            "features_count": len(MODEL_FEATURE_NAMES),
                            "target_type": "Deteksi Anomali Radiasi Termal Satelit (FRP > 0) Resolusi ~25km, BUKAN konfirmasi kebakaran darat",
                            "evaluation_status": "HISTORICAL_BENCHMARK_ONLY",
                            "operational_readiness": "PROTOTIPE_EKSPERIMENTAL",
                            "interpretability_notice": "Tile di luar cakupan.",
                        }
                    }

                if getattr(hansen_res, "treecover2000", None) is not None:
                    treecover = hansen_res.treecover2000
                else:
                    # Fallback ke demo rasters lokal di data/raster/hansen jika official subset belum mencakup titik ini
                    hansen_demo = read_hansen_pixel(lat=lat, lon=lon, province=province, use_official=False)
                    if getattr(hansen_demo, "treecover2000", None) is not None:
                        treecover = hansen_demo.treecover2000
                        hansen_res = hansen_demo

                if getattr(hansen_res, "province", None):
                    detected_prov = hansen_res.province
            except Exception as exc:
                logger.debug("Info raster Hansen tidak dapat diakses untuk koordinat (%s, %s): %s", lat, lon, exc)

        # Jika data kanopi pohon wajib tetap tidak tersedia, laporkan status INSUFFICIENT_DATA (bukan diasumsikan aman)
        if treecover is None:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "Data wajib raster tutupan pohon (f_prim) tidak tersedia untuk koordinat ini (risiko tidak dapat dinilai).",
                "coordinates": {"lat": lat, "lon": lon},
                "province": detected_prov or "Kalimantan",
                "risk_probability": None,
                "risk_percentage": None,
                "risk_level": "TIDAK_DAPAT_DINILAI",
                "risk_label": "Data Tidak Memadai",
                "risk_color": "GRAY",
                "primary_drivers": [],
                "data_quality": {
                    "status": "INSUFFICIENT_DATA",
                    "reliability": "NOT_ASSESSABLE",
                    "reason": "Data wajib raster tutupan kanopi pohon (f_prim) tidak tersedia.",
                    "missing_or_imputed_features": ["f_prim", "peatd", "loss_last_prim", "loss_last_sec"],
                },
                "model_metadata": {
                    "model_type": "Logistic Regression Baseline (ERA5 2002–2018)",
                    "features_count": len(MODEL_FEATURE_NAMES),
                    "target_type": "Deteksi Anomali Radiasi Termal Satelit (FRP > 0) Resolusi ~25km, BUKAN konfirmasi kebakaran darat",
                    "evaluation_status": "HISTORICAL_BENCHMARK_ONLY",
                    "operational_readiness": "PROTOTIPE_EKSPERIMENTAL",
                    "interpretability_notice": "Evaluasi risiko ditolak karena ketiadaan data kanopi wajib.",
                }
            }

        f_prim = round(treecover / 100.0, 4)

        # Penanganan fitur yang belum terintegrasi:
        # Gunakan nilai mean pelatihan scaler (mu) sebagai imputasi teknis netral (z = 0, kontribusi logit = 0)
        # TIDAK disamarkan sebagai nilai nol atau data aktual, dan status dicatat transparan di data_quality.
        idx_loss_prim = MODEL_FEATURE_NAMES.index("loss_last_prim")
        idx_loss_sec = MODEL_FEATURE_NAMES.index("loss_last_sec")
        idx_peatd = MODEL_FEATURE_NAMES.index("peatd")
        idx_dem = MODEL_FEATURE_NAMES.index("dem")

        loss_last_prim = float(self.scaler.mean_[idx_loss_prim])
        loss_last_sec = float(self.scaler.mean_[idx_loss_sec])
        peatd = float(self.scaler.mean_[idx_peatd])
        dem = float(weather.get("elevation", self.scaler.mean_[idx_dem]))

        # 3. Bentuk vektor fitur sebagai DataFrame berlabel
        feature_dict = {
            "tp": weather["tp"],
            "tp_1": weather["tp_1"],
            "tp_2": weather["tp_2"],
            "tp_3": weather["tp_3"],
            "tp_4": weather["tp_4"],
            "tp_5": weather["tp_5"],
            "t2m": weather["t2m"],
            "h2m": weather["h2m"],
            "w10": weather["w10"],
            "loss_last_prim": loss_last_prim,
            "loss_last_sec": loss_last_sec,
            "f_prim": f_prim,
            "peatd": peatd,
            "dem": dem,
        }
        df_input = pd.DataFrame([feature_dict])[MODEL_FEATURE_NAMES]

        # 4. Transformasi scaler dan prediksi probabilitas
        X_scaled = self.scaler.transform(df_input)
        prob = float(self.model.predict_proba(X_scaled)[0, 1])
        prob_percent = round(prob * 100, 2)

        # Klasifikasi level risiko (Indikatif Prototipe)
        if prob < 0.35:
            risk_level = "RENDAH"
            risk_color = "GREEN"
            risk_label = "Rendah (Data Terbatas)"
        elif prob < 0.70:
            risk_level = "SEDANG"
            risk_color = "YELLOW"
            risk_label = "Sedang"
        else:
            risk_level = "TINGGI"
            risk_color = "RED"
            risk_label = "Tinggi"

        # 5. Analisis kontribusi faktor penentu lokal (Local Linear Logit Contribution)
        # Kontribusi linier lokal: delta_logit_i = beta_i * z_i
        coefficients = self.model.coef_[0]
        z_scores = X_scaled[0]
        drivers = []
        for feat_name, coef, val, z_val in zip(MODEL_FEATURE_NAMES, coefficients, df_input.iloc[0], z_scores):
            contrib = float(coef * z_val)
            # Arah dorongan statistik terhadap logit:
            if abs(contrib) < 0.01:
                impact = "Pengaruh Netral (Mendekati Rata-rata)"
            elif contrib > 0:
                impact = "Mendorong Skor Lebih Tinggi"
            else:
                impact = "Menahan Skor Lebih Rendah"

            is_imputed = feat_name in ("peatd", "loss_last_prim", "loss_last_sec", "tp_3", "tp_4", "tp_5")

            drivers.append({
                "feature": feat_name,
                "label": FEATURE_HUMAN_LABELS.get(feat_name, feat_name),
                "value": round(float(val), 2),
                "z_score": round(float(z_val), 3),
                "coefficient": round(float(coef), 4),
                "contribution_to_logit": round(contrib, 4),
                "impact": impact,
                "is_imputed": is_imputed,
            })

        # Urutkan faktor berdasarkan kontribusi absolut lokal terbesar terhadap logit
        drivers.sort(key=lambda d: abs(d["contribution_to_logit"]), reverse=True)

        return {
            "status": "SUCCESS",
            "coordinates": {"lat": lat, "lon": lon},
            "province": detected_prov or "Kalimantan",
            "risk_probability": round(prob, 4),
            "risk_percentage": prob_percent,
            "risk_level": risk_level,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "primary_drivers": drivers[:5],
            "weather_source": weather.get("source", "UNKNOWN"),
            "input_features": feature_dict,
            "data_quality": {
                "status": "PARTIAL",
                "reliability": "LOW_EXPERIMENTAL",
                "missing_or_imputed_features": [
                    "peatd (Kedalaman Gambut)",
                    "loss_last_prim (Kehilangan Hutan Primer)",
                    "loss_last_sec (Kehilangan Hutan Sekunder)",
                    "tp_3", "tp_4", "tp_5 (Defisit Hujan 3-5 Bulan)"
                ],
                "imputation_method": "TECHNICAL_NEUTRAL_MEAN",
                "imputation_caveat": (
                    "Fitur yang layernya belum terintegrasi diimputasi dengan rata-rata pelatihan (z=0) "
                    "agar netral terhadap logit. Imputasi teknis ini TIDAK menjamin validitas prediksi di lapangan."
                ),
                "precipitation_metadata": weather.get("precipitation_metadata", {}),
            },
            "model_metadata": {
                "model_type": "Logistic Regression Baseline (ERA5 2002–2018)",
                "features_count": len(MODEL_FEATURE_NAMES),
                "target_type": "Deteksi Anomali Radiasi Termal Satelit (FRP > 0) Resolusi ~25km, BUKAN konfirmasi kebakaran darat",
                "evaluation_status": "HISTORICAL_BENCHMARK_ONLY",
                "operational_readiness": "PROTOTIPE_EKSPERIMENTAL",
                "interpretability_notice": (
                    "Kontribusi faktor adalah relasi deviasi statistik linier terhadap logit (beta * z), "
                    "bukan bukti kausalitas pemicu kebakaran darat."
                )
            }
        }


# Global singleton instance
_prediction_service_instance: Optional[FireRiskPredictionService] = None

def get_prediction_service() -> FireRiskPredictionService:
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = FireRiskPredictionService()
    return _prediction_service_instance
