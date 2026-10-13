"""
Pengujian Unit untuk Validasi Koordinat, Timestamp, dan Penanganan Nilai Kosong.
"""

from app.validation import (
    clean_optional_float,
    clean_optional_str,
    parse_and_validate_row,
    parse_timestamp,
    validate_coordinates,
)


def test_validate_coordinates_valid():
    """Menguji koordinat valid dalam rentang geografis yang benar."""
    coords = validate_coordinates("-2.5", "115.2")
    assert coords == (-2.5, 115.2)

    coords_edge = validate_coordinates(90.0, -180.0)
    assert coords_edge == (90.0, -180.0)


def test_validate_coordinates_invalid():
    """Menguji koordinat yang berada di luar rentang atau non-numerik."""
    assert validate_coordinates(95.0, 100.0) is None       # lat > 90
    assert validate_coordinates(-95.0, 100.0) is None      # lat < -90
    assert validate_coordinates(0.0, 185.0) is None        # lon > 180
    assert validate_coordinates(0.0, -185.0) is None       # lon < -180
    assert validate_coordinates("abc", "100.0") is None    # non-numerik
    assert validate_coordinates(None, 100.0) is None       # None
    assert validate_coordinates(float("nan"), 100.0) is None  # NaN


def test_parse_timestamp_valid():
    """Menguji parsing tanggal dan jam ke format standar ISO-8601 UTC."""
    # Jam 4 digit
    assert parse_timestamp("2026-10-13", "0430") == "2026-10-13T04:30:00Z"
    # Jam 3 digit (zfill)
    assert parse_timestamp("2026-10-13", "345") == "2026-10-13T03:45:00Z"


def test_parse_timestamp_invalid():
    """Menguji penanganan timestamp rusak tanpa crash."""
    assert parse_timestamp("2026-10-13", "9999") is None   # jam 99:99 tidak valid
    assert parse_timestamp("2026-02-31", "1200") is None   # tanggal 31 Februari
    assert parse_timestamp("corrupt-date", "1200") is None
    assert parse_timestamp("2026-10-13", "abcd") is None
    assert parse_timestamp("", "1200") is None
    assert parse_timestamp(None, "1200") is None


def test_clean_optional_values_strict():
    """Menguji bahwa nilai opsional kosong bernilai None tanpa tebakan."""
    assert clean_optional_float("") is None
    assert clean_optional_float("NaN") is None
    assert clean_optional_float("null") is None
    assert clean_optional_float(None) is None
    assert clean_optional_float("15.4") == 15.4

    assert clean_optional_str("") is None
    assert clean_optional_str("null") is None
    assert clean_optional_str(None) is None
    assert clean_optional_str("nominal") == "nominal"


def test_parse_and_validate_row_complete():
    """Menguji parsing satu baris data lengkap dan penanganan nilai kosong."""
    raw_row = {
        "latitude": "-0.5",
        "longitude": "101.5",
        "acq_date": "2026-10-13",
        "acq_time": "0515",
        "satellite": "20",
        "instrument": "VIIRS",
        "confidence": "",          # kosong
        "version": "2.0NRT",
        "bright_ti4": "330.5",
        "bright_ti5": "298.0",
        "frp": "NaN",              # NaN
        "daynight": "D"
    }
    rec, reject_reason = parse_and_validate_row(raw_row)
    assert reject_reason is None
    assert rec is not None
    assert rec.latitude == -0.5
    assert rec.longitude == 101.5
    assert rec.observation_time_utc == "2026-10-13T05:15:00Z"
    assert rec.confidence is None   # Tidak diimputasi
    assert rec.frp is None          # Tidak diimputasi
    assert rec.bright_ti4 == 330.5
