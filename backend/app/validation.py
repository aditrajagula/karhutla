"""
Modul Validasi Data Hotspot.
Memvalidasi batas koordinat, mengurai timestamp ke UTC ISO-8601,
dan menangani nilai kosong tanpa melakukan imputasi atau mengarang nilai.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from .models import HotspotRecord


def validate_coordinates(lat_val: Any, lon_val: Any) -> Optional[Tuple[float, float]]:
    """
    Validasi nilai latitude (-90 s.d. 90) dan longitude (-180 s.d. 180).
    Mengembalikan tuple (latitude, longitude) float atau None jika tidak valid.
    """
    if lat_val is None or lon_val is None:
        return None
    try:
        lat = float(lat_val)
        lon = float(lon_val)
    except (ValueError, TypeError):
        return None

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return None

    if not (-90.0 <= lat <= 90.0):
        return None
    if not (-180.0 <= lon <= 180.0):
        return None

    return lat, lon


def parse_timestamp(acq_date_val: Any, acq_time_val: Any) -> Optional[str]:
    """
    Mengurai acq_date (YYYY-MM-DD) dan acq_time (HHMM UTC) menjadi ISO-8601 UTC.
    Contoh: acq_date='2026-10-13', acq_time='345' -> '2026-10-13T03:45:00Z'
    Mengembalikan None jika format tanggal/waktu corrupt atau tidak valid.
    """
    if not acq_date_val or acq_time_val is None:
        return None

    date_str = str(acq_date_val).strip()
    time_str = str(acq_time_val).strip()

    if not date_str or not time_str:
        return None

    # Normalisasi waktu ke 4 digit (misal: '345' -> '0345')
    time_str = time_str.zfill(4)
    if len(time_str) != 4 or not time_str.isdigit():
        return None

    hh = time_str[:2]
    mm = time_str[2:]

    try:
        dt = datetime.strptime(f"{date_str} {hh}:{mm}:00", "%Y-%m-%d %H:%M:%S")
        dt_utc = dt.replace(tzinfo=timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def clean_optional_float(val: Any) -> Optional[float]:
    """
    Membersihkan nilai float opsional (FRP, brightness temperature).
    Jika kosong, string hampa, atau NaN, kembalikan None (tanpa nilai tebakan).
    """
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip()
        if not val or val.lower() in ("nan", "null", "none"):
            return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return None


def clean_optional_str(val: Any) -> Optional[str]:
    """
    Membersihkan nilai string opsional.
    Jika kosong atau bernilai null, kembalikan None.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "null", "none"):
        return None
    return s


def parse_and_validate_row(row: Dict[str, Any]) -> Tuple[Optional[HotspotRecord], Optional[str]]:
    """
    Validasi satu baris data mentah dari respons FIRMS.
    Mengembalikan: (HotspotRecord, None) jika valid,
    atau (None, "alasan_penolakan") jika ditolak.
    """
    coords = validate_coordinates(row.get("latitude"), row.get("longitude"))
    if coords is None:
        return None, "invalid_coordinates"

    lat, lon = coords

    acq_date = str(row.get("acq_date", "")).strip()
    acq_time = str(row.get("acq_time", "")).strip()
    timestamp_utc = parse_timestamp(acq_date, acq_time)
    if timestamp_utc is None:
        return None, "invalid_timestamp"

    # Penanganan nilai opsional secara ketat tanpa imputasi
    record = HotspotRecord(
        latitude=lat,
        longitude=lon,
        acq_date=acq_date,
        acq_time=acq_time.zfill(4),
        observation_time_utc=timestamp_utc,
        satellite=clean_optional_str(row.get("satellite")),
        instrument=clean_optional_str(row.get("instrument")),
        confidence=clean_optional_str(row.get("confidence")),
        version=clean_optional_str(row.get("version")),
        bright_ti4=clean_optional_float(row.get("bright_ti4")),
        bright_ti5=clean_optional_float(row.get("bright_ti5")),
        frp=clean_optional_float(row.get("frp")),
        daynight=clean_optional_str(row.get("daynight")),
        province=None
    )

    return record, None
