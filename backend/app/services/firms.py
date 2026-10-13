import csv
import io
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.schemas.hotspot import Hotspot

# In-memory cache: (cache_key) -> (timestamp, list_of_hotspots, mode, sync_time_str)
_CACHE: Dict[str, Tuple[float, List[Hotspot], str, str]] = {}
CACHE_TTL_SECONDS = 300  # 5 menit

CONFIDENCE_MAP = {
    "l": "low",
    "n": "nominal",
    "h": "high",
}

SATELLITE_MAP = {
    "N20": "NOAA-20",
    "N21": "NOAA-21",
    "N": "Suomi NPP",
    "Terra": "Terra",
    "Aqua": "Aqua",
}


def _parse_csv_content(csv_text: str, source_provenance: str) -> List[Hotspot]:
    reader = csv.DictReader(io.StringIO(csv_text))
    results: List[Hotspot] = []
    
    for row in reader:
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
            # Batas koordinat Indonesia
            if not (-11.0 <= lat <= 6.0 and 95.0 <= lon <= 141.0):
                continue

            acq_date = row.get("acq_date", "")
            acq_time = str(row.get("acq_time", "")).strip().zfill(4)
            sat_raw = row.get("satellite", "")
            sat = SATELLITE_MAP.get(sat_raw, sat_raw)
            conf_raw = str(row.get("confidence", "")).lower()
            conf = CONFIDENCE_MAP.get(conf_raw, conf_raw or "nominal")
            
            frp_val = None
            if row.get("frp"):
                try:
                    frp_val = round(float(row["frp"]), 2)
                except ValueError:
                    frp_val = None

            hotspot_id = f"{lat:.4f}_{lon:.4f}_{acq_date}_{acq_time}_{sat_raw}"
            
            results.append(
                Hotspot(
                    id=hotspot_id,
                    latitude=lat,
                    longitude=lon,
                    acq_date=acq_date,
                    acq_time=acq_time,
                    satellite=sat,
                    instrument=row.get("instrument", "VIIRS"),
                    confidence=conf,
                    frp=frp_val,
                    daynight=row.get("daynight", "D"),
                    source_provenance=source_provenance,
                )
            )
        except (ValueError, KeyError):
            continue

    return results


def _load_snapshot() -> Tuple[List[Hotspot], str]:
    # Cari berkas snapshot fallback
    candidates = [
        settings.SNAPSHOT_FALLBACK_PATH,
        "./data/snapshots/joints_benchmark_7days.csv",
        "../data/snapshots/joints_benchmark_7days.csv",
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            mtime = os.path.getmtime(path)
            sync_time = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return _parse_csv_content(content, "JOINTS_BENCHMARK_SNAPSHOT"), sync_time
    
    return [], datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_hotspots_data(
    mode: str = "auto",
    day_range: int = 2,
    sensor: Optional[str] = None,
) -> Tuple[str, List[Hotspot], str, Optional[str]]:
    """
    Mengambil data hotspot:
    - mode 'live': paksa live FIRMS API
    - mode 'snapshot': paksa muat file snapshot lokal
    - mode 'auto': coba live FIRMS API, fallback ke snapshot jika gagal
    Returns: (resolved_mode, records, sync_time_utc, error_message)
    """
    active_sensor = sensor or settings.DEFAULT_SENSOR
    now = time.time()
    cache_key = f"{mode}_{day_range}_{active_sensor}"

    if cache_key in _CACHE:
        cached_time, records, resolved_mode, sync_str = _CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return resolved_mode, records, sync_str, None

    if mode == "snapshot":
        records, sync_str = _load_snapshot()
        _CACHE[cache_key] = (now, records, "snapshot", sync_str)
        return "snapshot", records, sync_str, None

    # Live API call
    key = settings.FIRMS_MAP_KEY
    if not key or key == "YOUR_NASA_FIRMS_MAP_KEY_HERE":
        if mode == "live":
            return "live", [], "", "FIRMS_MAP_KEY belum dikonfigurasi di server."
        records, sync_str = _load_snapshot()
        _CACHE[cache_key] = (now, records, "snapshot", sync_str)
        return "snapshot", records, sync_str, "Menggunakan snapshot: FIRMS_MAP_KEY belum dikonfigurasi."

    url = f"{settings.FIRMS_BASE_URL}/{key}/{active_sensor}/95,-11,141,6/{day_range}"
    
    try:
        resp = httpx.get(url, timeout=8.0)
        resp.raise_for_status()
        csv_text = resp.text
        
        # Validasi respon NASA FIRMS (jika error kuota/kunci tidak valid)
        if "Invalid MAP_KEY" in csv_text or "No data available" in csv_text and len(csv_text) < 100:
            if mode == "live":
                return "live", [], "", "Kunci API FIRMS tidak valid atau ditolak oleh NASA."
            records, sync_str = _load_snapshot()
            return "snapshot", records, sync_str, "Kunci API FIRMS ditolak; beralih ke snapshot lokal."

        records = _parse_csv_content(csv_text, "NASA_FIRMS_API")
        sync_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _CACHE[cache_key] = (now, records, "live", sync_str)
        try:
            with open(settings.SNAPSHOT_FALLBACK_PATH, "w", encoding="utf-8") as f:
                f.write(csv_text)
        except Exception:
            pass
        return "live", records, sync_str, None

    except Exception as exc:
        if mode == "live":
            return "live", [], "", f"Gagal menghubungi NASA FIRMS: {str(exc)}"
        records, sync_str = _load_snapshot()
        _CACHE[cache_key] = (now, records, "snapshot", sync_str)
        return "snapshot", records, sync_str, f"Koneksi FIRMS gagal ({str(exc)}); beralih ke snapshot lokal."

