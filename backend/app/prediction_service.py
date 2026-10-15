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
    from .hansen_tile_reader import read_hansen_pixel
except ImportError:
    read_hansen_pixel = None

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
                "risk_probability": None,
                "risk_level": "BELUM_DAPAT_DINILAI",
            }

        # 1. Ambil data cuaca dari Open-Meteo (dengan fallback aman)
        weather = self.weather_client.fetch_weather_features(lat, lon)

        # 2. Ambil data vegetasi dari Hansen Raster 30m jika berada di cakupan tile
        treecover = 70
        detected_prov = province
        if read_hansen_pixel is not None:
            try:
                hansen_res = read_hansen_pixel(lat=lat, lon=lon, province=province)
                if getattr(hansen_res, "treecover2000", None) is not None:
                    treecover = hansen_res.treecover2000
                if getattr(hansen_res, "province", None):
                    detected_prov = hansen_res.province
            except Exception as exc:
                logger.debug("Info raster Hansen tidak dapat diakses untuk koordinat (%s, %s): %s", lat, lon, exc)

        f_prim = round(treecover / 100.0, 4)

        # Cek apakah ada loss tahun lalu (misal jika data lossyear terdeteksi)
        loss_last_prim = 0.0
        loss_last_sec = 0.0

        # Gambut dan Elevasi
        peatd = 0.0
        dem = float(weather.get("elevation", 50.0))

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

        # Klasifikasi level risiko
        if prob < 0.35:
            risk_level = "RENDAH"
            risk_color = "GREEN"
        elif prob < 0.70:
            risk_level = "SEDANG"
            risk_color = "YELLOW"
        else:
            risk_level = "TINGGI"
            risk_color = "RED"

        # 5. Analisis kontribusi faktor pemicu (Driver explainability)
        coefficients = self.model.coef_[0]
        drivers = []
        for feat_name, coef, val in zip(MODEL_FEATURE_NAMES, coefficients, df_input.iloc[0]):
            # Dampak positif memperbesar risiko, negatif memperkecil
            impact = "Meningkatkan Risiko" if coef > 0 else "Menurunkan Risiko"
            drivers.append({
                "feature": feat_name,
                "label": FEATURE_HUMAN_LABELS.get(feat_name, feat_name),
                "value": round(float(val), 2),
                "coefficient": round(float(coef), 4),
                "impact": impact,
            })

        # Urutkan faktor dengan koefisien absolut terbesar
        drivers.sort(key=lambda d: abs(d["coefficient"]), reverse=True)

        return {
            "status": "SUCCESS",
            "coordinates": {"lat": lat, "lon": lon},
            "province": detected_prov or "Wilayah Sekitar Pengguna",
            "risk_probability": round(prob, 4),
            "risk_percentage": prob_percent,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "primary_drivers": drivers[:5],
            "weather_source": weather.get("source", "UNKNOWN"),
            "input_features": feature_dict,
            "model_metadata": {
                "model_type": "Logistic Regression (ERA5 + Open-Meteo + Hansen GFC)",
                "features_count": len(MODEL_FEATURE_NAMES),
                "roc_auc_evaluation": 0.81,
            }
        }


# Global singleton instance
_prediction_service_instance: Optional[FireRiskPredictionService] = None

def get_prediction_service() -> FireRiskPredictionService:
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = FireRiskPredictionService()
    return _prediction_service_instance
