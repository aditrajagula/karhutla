"""
backend/app/weather_client.py
Klien integrasi API Cuaca Open-Meteo untuk inferensi model kerentanan karhutla.
Mendukung query parameter resmi Open-Meteo (current, hourly, daily, past_days=92, wind_speed_unit=ms)
serta mekanisme fallback aman (anti-crash) jika jaringan offline atau respons lambat.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .config import WEATHER_API_BASE_URL, WEATHER_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Nilai klimatologi dasar (mean pelatihan ERA5) jika Open-Meteo offline/timeout
# Digunakan sebagai imputasi teknis netral (z = 0), bukan klaim observasi aktual
KALIMANTAN_CLIMATE_DEFAULTS = {
    "t2m": 28.48,        # Suhu udara rata-rata 28.48 °C
    "h2m": 72.13,        # Kelembaban relatif rata-rata 72.13%
    "w10": 1.66,         # Kecepatan angin rata-rata 1.66 m/s
    "tp": 278.57,        # Rata-rata curah hujan bulanan ERA5 (mm)
    "tp_1": 278.50,      # Rata-rata curah hujan 1 bulan sebelumnya (mm)
    "tp_2": 278.37,      # Rata-rata curah hujan 2 bulan sebelumnya (mm)
    "tp_3": 278.44,      # Rata-rata curah hujan 3 bulan sebelumnya (mm)
    "tp_4": 278.69,      # Rata-rata curah hujan 4 bulan sebelumnya (mm)
    "tp_5": 278.61,      # Rata-rata curah hujan 5 bulan sebelumnya (mm)
}


class WeatherClient:
    """
    Klien untuk mengambil dan memetakan variabel meteorologi dari Open-Meteo API
    ke dalam 9 parameter iklim yang dibutuhkan oleh model regresi logistik prediksi karhutla.
    """

    def __init__(
        self,
        base_url: str = WEATHER_API_BASE_URL,
        timeout_seconds: float = WEATHER_REQUEST_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def build_query_params(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Menyusun parameter kueri resmi Open-Meteo sesuai spesifikasi:
        - daily=precipitation_sum
        - hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m
        - current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation
        - timezone=auto
        - past_days=92 (Batas maksimal resmi endpoint forecast Open-Meteo)
        - forecast_days=1
        - wind_speed_unit=ms
        """
        return {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "daily": "precipitation_sum",
            "timezone": "auto",
            "past_days": 92,
            "forecast_days": 1,
            "wind_speed_unit": "ms",
        }

    def fetch_weather_features(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """
        Mengambil data cuaca dan menyusun fitur iklim untuk model Machine Learning.
        Mengembalikan dictionary yang berisi:
        - t2m, h2m, w10, tp, tp_1, tp_2, tp_3, tp_4, tp_5
        - current_raw: data mentah cuaca saat ini
        - source: 'OPEN_METEO_API' atau 'CLIMATOLOGY_FALLBACK'
        - precipitation_metadata: dokumentasi semantik jendela akumulasi
        - feature_audit: status keterukuran setiap fitur
        """
        params = self.build_query_params(lat, lon)
        query_string = urllib.parse.urlencode(params)
        full_url = f"{self.base_url}?{query_string}"

        try:
            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "FireGuard-Kalimantan-Backend/1.0"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status == 200:
                    raw_data = json.loads(response.read().decode("utf-8"))
                    return self._parse_open_meteo_response(raw_data)
        except Exception as exc:
            logger.warning(
                "Gagal mengambil data Open-Meteo untuk (%s, %s): %s. Menggunakan fallback klimatologi.",
                lat, lon, exc
            )

        # Fallback jika terjadi kegagalan jaringan / timeout
        return {
            **KALIMANTAN_CLIMATE_DEFAULTS,
            "source": "CLIMATOLOGY_FALLBACK",
            "current_raw": None,
            "hourly_summary": None,
            "precipitation_metadata": {
                "aggregation": "CLIMATOLOGY_FALLBACK",
                "calendar_aligned": False,
                "semantic_limitation": "API cuaca offline. Menggunakan nilai dasar klimatologi rata-rata pelatihan.",
                "measured_lags": [],
                "unavailable_lags": ["tp", "tp_1", "tp_2", "tp_3", "tp_4", "tp_5"],
            },
            "feature_audit": {
                feat: {"status": "UNAVAILABLE_FALLBACK", "imputation": "TRAINING_MEAN"}
                for feat in ["t2m", "h2m", "w10", "tp", "tp_1", "tp_2", "tp_3", "tp_4", "tp_5"]
            }
        }

    def _parse_open_meteo_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Memetakan respons JSON Open-Meteo ke fitur iklim model regresi logistik."""
        current = data.get("current", {})
        daily = data.get("daily", {})

        # 1. Parameter saat ini (Current)
        t2m = float(current.get("temperature_2m", KALIMANTAN_CLIMATE_DEFAULTS["t2m"]))
        h2m = float(current.get("relative_humidity_2m", KALIMANTAN_CLIMATE_DEFAULTS["h2m"]))
        w10 = float(current.get("wind_speed_10m", KALIMANTAN_CLIMATE_DEFAULTS["w10"]))

        # 2. Parameter akumulasi curah hujan historis (past_days=92 mencakup ~3 bulan)
        daily_rain: List[Optional[float]] = daily.get("precipitation_sum", [])
        clean_rain = [float(r) for r in daily_rain if r is not None]

        # REVISI SEMANTIK CURAH HUJAN:
        # Pada pelatihan, tp adalah curah hujan bulanan kalender berjalan, tp_1 adalah 1 bulan lalu, dst.
        # Pada inferensi waktu-nyata, bulan kalender belum selesai.
        # Kita menggunakan jendela berjalan 30 hari sebagai proksi kondisi kelembaban berjalan,
        # dan secara tegas MENDOKUMENTASIKAN bahwa ini adalah proksi berjalan (bukan bulan kalender identik).
        # tp: akumulasi 30 hari berjalan terkini (proksi kondisi basah/kering berjalan)
        # tp_1: akumulasi hari ke 31-60 lalu (1 bulan lalu)
        # tp_2: akumulasi hari ke 61-90 lalu (2 bulan lalu)
        # tp_3, tp_4, tp_5: Berada di luar batas 92 hari API forecast, diimputasi dengan mean pelatihan
        # dan DICATAT status ketiadaannya (tidak disamarkan sebagai data aktual).

        tp_measured = len(clean_rain) >= 30
        tp_1_measured = len(clean_rain) >= 60
        tp_2_measured = len(clean_rain) >= 90

        tp = sum(clean_rain[-30:]) if tp_measured else KALIMANTAN_CLIMATE_DEFAULTS["tp"]
        tp_1 = sum(clean_rain[-60:-30]) if tp_1_measured else KALIMANTAN_CLIMATE_DEFAULTS["tp_1"]
        tp_2 = sum(clean_rain[-90:-60]) if tp_2_measured else KALIMANTAN_CLIMATE_DEFAULTS["tp_2"]
        tp_3 = KALIMANTAN_CLIMATE_DEFAULTS["tp_3"]
        tp_4 = KALIMANTAN_CLIMATE_DEFAULTS["tp_4"]
        tp_5 = KALIMANTAN_CLIMATE_DEFAULTS["tp_5"]

        measured_lags = []
        if tp_measured:
            measured_lags.append("tp (30 hari terakhir)")
        if tp_1_measured:
            measured_lags.append("tp_1 (hari ke-31 s.d. 60)")
        if tp_2_measured:
            measured_lags.append("tp_2 (hari ke-61 s.d. 90)")

        unavailable_lags = ["tp_3", "tp_4", "tp_5"]
        if not tp_2_measured:
            unavailable_lags.insert(0, "tp_2")
        if not tp_1_measured:
            unavailable_lags.insert(0, "tp_1")
        if not tp_measured:
            unavailable_lags.insert(0, "tp")

        return {
            "t2m": round(t2m, 2),
            "h2m": round(h2m, 2),
            "w10": round(w10, 2),
            "tp": round(tp, 2),
            "tp_1": round(tp_1, 2),
            "tp_2": round(tp_2, 2),
            "tp_3": round(tp_3, 2),
            "tp_4": round(tp_4, 2),
            "tp_5": round(tp_5, 2),
            "source": "OPEN_METEO_API",
            "current_raw": current,
            "timezone": data.get("timezone", "auto"),
            "elevation": data.get("elevation", 0.0),
            "precipitation_metadata": {
                "aggregation": "ROLLING_30_DAYS_PROXY",
                "calendar_aligned": False,
                "semantic_limitation": "Menggunakan jendela berjalan 30 hari sebagai proksi kondisi basah/kering. Berbeda secara semantik dengan bulan kalender tertutup pada pelatihan.",
                "measured_lags": measured_lags,
                "unavailable_lags": unavailable_lags,
            },
            "feature_audit": {
                "t2m": {"status": "MEASURED_CURRENT", "source": "OPEN_METEO_HOURLY"},
                "h2m": {"status": "MEASURED_CURRENT", "source": "OPEN_METEO_HOURLY"},
                "w10": {"status": "MEASURED_CURRENT", "source": "OPEN_METEO_HOURLY"},
                "tp": {"status": "MEASURED_PROXY_30D" if tp_measured else "IMPUTED_MEAN", "source": "OPEN_METEO_DAILY_SUM"},
                "tp_1": {"status": "MEASURED_PROXY_30D" if tp_1_measured else "IMPUTED_MEAN", "source": "OPEN_METEO_DAILY_SUM"},
                "tp_2": {"status": "MEASURED_PROXY_30D" if tp_2_measured else "IMPUTED_MEAN", "source": "OPEN_METEO_DAILY_SUM"},
                "tp_3": {"status": "UNAVAILABLE_OUT_OF_RANGE", "imputation": "TRAINING_MEAN"},
                "tp_4": {"status": "UNAVAILABLE_OUT_OF_RANGE", "imputation": "TRAINING_MEAN"},
                "tp_5": {"status": "UNAVAILABLE_OUT_OF_RANGE", "imputation": "TRAINING_MEAN"},
            }
        }
