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

# Nilai klimatologi dasar untuk Kalimantan jika Open-Meteo offline/timeout
KALIMANTAN_CLIMATE_DEFAULTS = {
    "t2m": 28.5,        # Suhu udara rata-rata 28.5 °C
    "h2m": 76.0,        # Kelembaban relatif rata-rata 76%
    "w10": 2.2,         # Kecepatan angin rata-rata 2.2 m/s
    "tp": 10.0,         # Curah hujan harian/berjalan (mm)
    "tp_1": 180.0,      # Akumulasi curah hujan 1 bulan sebelumnya (mm)
    "tp_2": 210.0,      # Akumulasi curah hujan 2 bulan sebelumnya (mm)
    "tp_3": 240.0,      # Akumulasi curah hujan 3 bulan sebelumnya (mm)
    "tp_4": 260.0,      # Akumulasi curah hujan 4 bulan sebelumnya (mm)
    "tp_5": 280.0,      # Akumulasi curah hujan 5 bulan sebelumnya (mm)
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
        - past_days=92
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
        }

    def _parse_open_meteo_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Memetakan respons JSON Open-Meteo ke fitur iklim model regresi logistik."""
        current = data.get("current", {})
        daily = data.get("daily", {})

        # 1. Parameter saat ini (Current)
        t2m = float(current.get("temperature_2m", KALIMANTAN_CLIMATE_DEFAULTS["t2m"]))
        h2m = float(current.get("relative_humidity_2m", KALIMANTAN_CLIMATE_DEFAULTS["h2m"]))
        w10 = float(current.get("wind_speed_10m", KALIMANTAN_CLIMATE_DEFAULTS["w10"]))
        tp = float(current.get("precipitation", KALIMANTAN_CLIMATE_DEFAULTS["tp"]))

        # 2. Parameter akumulasi curah hujan historis (past_days=92 mencakup ~3 bulan)
        daily_rain: List[Optional[float]] = daily.get("precipitation_sum", [])
        clean_rain = [float(r) for r in daily_rain if r is not None]

        # Bagi menjadi jendela 30 hari ke belakang:
        # tp_1: 30 hari terakhir (bulan lalu)
        # tp_2: hari ke 31-60 lalu (2 bulan lalu)
        # tp_3: hari ke 61-90 lalu (3 bulan lalu)
        tp_1 = sum(clean_rain[-30:]) if len(clean_rain) >= 30 else KALIMANTAN_CLIMATE_DEFAULTS["tp_1"]
        tp_2 = sum(clean_rain[-60:-30]) if len(clean_rain) >= 60 else KALIMANTAN_CLIMATE_DEFAULTS["tp_2"]
        tp_3 = sum(clean_rain[-90:-60]) if len(clean_rain) >= 90 else KALIMANTAN_CLIMATE_DEFAULTS["tp_3"]
        tp_4 = KALIMANTAN_CLIMATE_DEFAULTS["tp_4"]
        tp_5 = KALIMANTAN_CLIMATE_DEFAULTS["tp_5"]

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
        }
