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
        self._daily_cache: Dict[str, Dict[str, Any]] = {}
        import threading
        self._cache_lock = threading.Lock()
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
        province: Optional[str] = None,
        allow_imputed_canopy: bool = True
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

        idx_f_prim = MODEL_FEATURE_NAMES.index("f_prim")
        is_canopy_imputed = False
        if treecover is None:
            if not allow_imputed_canopy:
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
            # Fallback imputasi rata-rata pelatihan ERA5 (~48.96%) jika pixel belum ter-download lokal
            treecover = float(self.scaler.mean_[idx_f_prim]) * 100.0
            is_canopy_imputed = True

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
                    *(["f_prim (Imputasi Rata-rata Pelatihan ERA5)"] if is_canopy_imputed else []),
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

    def get_daily_predictive_hotspots(self) -> Dict[str, Any]:
        """
        Menghasilkan GeoJSON FeatureCollection titik hotspot prediktif harian (Siklus 24 Jam)
        di seluruh wilayah 5 provinsi Kalimantan, difilter hanya untuk level risiko Sedang s.d. Tinggi.
        Hasil di-cache berdasarkan tanggal kalender (YYYY-MM-DD). Data hari sebelumnya otomatis dibuang
        dan diganti baru setiap hari kalender berganti.
        """
        import concurrent.futures
        from datetime import datetime, timezone

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._cache_lock:
            cached = self._daily_cache.get(today_str)
            if cached is not None:
                return cached

        # Jika belum ada di cache untuk hari ini, hitung secara paralel dengan kontrol burst
        import time

        def evaluate_point(pt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            try:
                time.sleep(0.06)  # Hindari rate limit burst Open-Meteo
                res = self.predict_fire_risk(
                    lat=pt["lat"],
                    lon=pt["lon"],
                    province=pt["province"],
                    allow_imputed_canopy=True
                )
                if res.get("status") == "SUCCESS":
                    level = res.get("risk_level", "RENDAH")
                    # Sesuai permintaan pengguna: hanya tampilkan hasil output SEDANG s.d. TINGGI
                    if level in ("SEDANG", "TINGGI"):
                        return {
                            "point": pt,
                            "prediction": res
                        }
            except Exception as err:
                logger.debug("Evaluasi prediksi untuk %s gagal: %s", pt.get("name"), err)
            return None

        evaluated_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_pt = {executor.submit(evaluate_point, pt): pt for pt in KALIMANTAN_MONITORING_POINTS}
            for future in concurrent.futures.as_completed(future_to_pt):
                result = future.result()
                if result:
                    evaluated_items.append(result)

        # Urutkan berdasarkan persentase risiko tertinggi
        evaluated_items.sort(key=lambda x: x["prediction"].get("risk_percentage", 0), reverse=True)

        features = []
        for item in evaluated_items:
            pt = item["point"]
            res = item["prediction"]
            features.append({
                "type": "Feature",
                "id": f"pred_{pt['id']}_{today_str}",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(pt["lon"], 4), round(pt["lat"], 4)]
                },
                "properties": {
                    "id": f"pred_{pt['id']}_{today_str}",
                    "location_name": pt["name"],
                    "province": pt["province"],
                    "latitude": round(pt["lat"], 4),
                    "longitude": round(pt["lon"], 4),
                    "risk_level": res["risk_level"],
                    "risk_label": res.get("risk_label", res["risk_level"]),
                    "risk_percentage": res["risk_percentage"],
                    "risk_probability": res["risk_probability"],
                    "prediction_date": today_str,
                    "validity_period": "Harian (Berlaku 24 Jam)",
                    "caution_level": "Waspada" if res["risk_level"] == "SEDANG" else "Siaga",
                    "weather_summary": {
                        "temperature_2m": res.get("input_features", {}).get("t2m"),
                        "humidity_2m": res.get("input_features", {}).get("h2m"),
                        "wind_speed_10m": res.get("input_features", {}).get("w10"),
                        "precipitation_30d": res.get("input_features", {}).get("tp"),
                    },
                    "primary_drivers": res.get("primary_drivers", []),
                    "caution_notice": (
                        "Indikasi waspada potensi kerawanan lingkungan harian berbasis model regresi logistik cuaca dan kanopi. "
                        "BUKAN titik api fisik aktif yang teramati satelit NASA FIRMS. Prioritaskan patroli pencegahan."
                    ),
                    "is_predictive": True
                }
            })

        response_payload = {
            "type": "FeatureCollection",
            "prediction_date": today_str,
            "validity": "Harian (Siklus 24 Jam)",
            "update_cycle": "Diperbarui Setiap Hari Baru (Hari Sebelumnya Dibuang Otomatis)",
            "total_features": len(features),
            "model_type": "Logistic Regression Baseline (ERA5 + Open-Meteo Harian)",
            "caution_statement": (
                "Data hotspot prediktif ini menyajikan zona kerawanan karhutla berbasis cuaca mikro dan tutupan lahan. "
                "Data ini berbeda dari hotspot satelit empiris NASA FIRMS dan harus disikapi dengan kewaspadaan pencegahan dini."
            ),
            "features": features
        }

        with self._cache_lock:
            # Buang cache hari-hari lama untuk menghemat memori
            self._daily_cache.clear()
            self._daily_cache[today_str] = response_payload

        return response_payload


KALIMANTAN_MONITORING_POINTS = [
    # Kalimantan Tengah (Pusat gambut & rawan karhutla)
    {"id": "kalteng_palangka_raya", "name": "Palangka Raya (Sebangau)", "province": "Kalimantan Tengah", "lat": -2.2161, "lon": 113.9140},
    {"id": "kalteng_pulang_pisau", "name": "Pulang Pisau (Kahayan Hilir)", "province": "Kalimantan Tengah", "lat": -2.7500, "lon": 114.2500},
    {"id": "kalteng_sampit", "name": "Sampit (Kotawaringin Timur)", "province": "Kalimantan Tengah", "lat": -2.5333, "lon": 112.9500},
    {"id": "kalteng_kapuas", "name": "Kuala Kapuas (Kapuas Murung)", "province": "Kalimantan Tengah", "lat": -3.0090, "lon": 114.3850},
    {"id": "kalteng_katingan", "name": "Kasongan (Katingan Hilir)", "province": "Kalimantan Tengah", "lat": -1.9000, "lon": 113.3800},
    {"id": "kalteng_pangkalan_bun", "name": "Pangkalan Bun (Kumai)", "province": "Kalimantan Tengah", "lat": -2.6833, "lon": 111.6167},
    {"id": "kalteng_sukamara", "name": "Sukamara (Pantai Jelai)", "province": "Kalimantan Tengah", "lat": -2.6280, "lon": 111.2370},

    # Kalimantan Barat (Gambut pesisir & batas hutan)
    {"id": "kalbar_pontianak", "name": "Pontianak (Siantan)", "province": "Kalimantan Barat", "lat": -0.0263, "lon": 109.3425},
    {"id": "kalbar_kubu_raya", "name": "Kubu Raya (Rasau Jaya)", "province": "Kalimantan Barat", "lat": -0.1500, "lon": 109.4500},
    {"id": "kalbar_ketapang", "name": "Ketapang (Matan Hilir Selatan)", "province": "Kalimantan Barat", "lat": -1.8500, "lon": 109.9800},
    {"id": "kalbar_kendawangan", "name": "Kendawangan (Pesisir Selatan)", "province": "Kalimantan Barat", "lat": -2.5333, "lon": 110.2000},
    {"id": "kalbar_sambas", "name": "Sambas (Paloh)", "province": "Kalimantan Barat", "lat": 1.3667, "lon": 109.3000},
    {"id": "kalbar_mempawah", "name": "Mempawah (Sungai Pinyuh)", "province": "Kalimantan Barat", "lat": 0.3500, "lon": 108.9667},
    {"id": "kalbar_sintang", "name": "Sintang (Sepauk)", "province": "Kalimantan Barat", "lat": 0.0700, "lon": 111.4980},
    {"id": "kalbar_sanggau", "name": "Sanggau (Kapuas)", "province": "Kalimantan Barat", "lat": 0.1200, "lon": 110.5800},

    # Kalimantan Selatan (Rawa gambut & savana kering)
    {"id": "kalsel_banjarmasin", "name": "Banjarmasin (Banjarmasin Barat)", "province": "Kalimantan Selatan", "lat": -3.3167, "lon": 114.5901},
    {"id": "kalsel_banjarbaru", "name": "Banjarbaru (Guntung Payung)", "province": "Kalimantan Selatan", "lat": -3.4500, "lon": 114.8300},
    {"id": "kalsel_tanah_laut", "name": "Pelaihari (Bati-Bati)", "province": "Kalimantan Selatan", "lat": -3.8000, "lon": 114.7600},
    {"id": "kalsel_barito_kuala", "name": "Marabahan (Alalak)", "province": "Kalimantan Selatan", "lat": -2.9800, "lon": 114.7700},
    {"id": "kalsel_tapin", "name": "Rantau (Bakarangan)", "province": "Kalimantan Selatan", "lat": -2.9300, "lon": 115.1500},
    {"id": "kalsel_hulu_sungai_selatan", "name": "Kandangan (Simpur)", "province": "Kalimantan Selatan", "lat": -2.7800, "lon": 115.2500},

    # Kalimantan Timur
    {"id": "kaltim_samarinda", "name": "Samarinda (Palaran)", "province": "Kalimantan Timur", "lat": -0.5016, "lon": 117.1537},
    {"id": "kaltim_balikpapan", "name": "Balikpapan (Balikpapan Utara)", "province": "Kalimantan Timur", "lat": -1.2654, "lon": 116.8312},
    {"id": "kaltim_kukar_tenggarong", "name": "Tenggarong (Muara Kaman)", "province": "Kalimantan Timur", "lat": -0.4100, "lon": 116.9800},
    {"id": "kaltim_berau", "name": "Tanjung Redeb (Segah)", "province": "Kalimantan Timur", "lat": 2.1500, "lon": 117.4800},
    {"id": "kaltim_paser", "name": "Tanah Grogot (Kuaro)", "province": "Kalimantan Timur", "lat": -1.9000, "lon": 116.2000},
    {"id": "kaltim_kutai_timur", "name": "Sangatta (Bengalon)", "province": "Kalimantan Timur", "lat": 0.4800, "lon": 117.5500},

    # Kalimantan Utara
    {"id": "kaltara_tanjung_selor", "name": "Tanjung Selor (Tanjung Palas)", "province": "Kalimantan Utara", "lat": 2.8375, "lon": 117.3653},
    {"id": "kaltara_tarakan", "name": "Tarakan (Tarakan Timur)", "province": "Kalimantan Utara", "lat": 3.3000, "lon": 117.6000},
    {"id": "kaltara_malinau", "name": "Malinau (Mentarang)", "province": "Kalimantan Utara", "lat": 3.5800, "lon": 116.6300},
    {"id": "kaltara_nunukan", "name": "Nunukan (Sebatik Barat)", "province": "Kalimantan Utara", "lat": 4.1300, "lon": 117.6500},
]


# Global singleton instance
_prediction_service_instance: Optional[FireRiskPredictionService] = None

def get_prediction_service() -> FireRiskPredictionService:
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = FireRiskPredictionService()
    return _prediction_service_instance
