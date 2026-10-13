"""
Pengujian Audit Pipeline Data Mandiri & Kepatuhan Spesifikasi Proyek.

PERINGATAN AUDIT:
Seluruh fixture dan data di dalam file ini adalah DATA SINTETIS BERLABEL 'TEST ONLY'.
Data ini BUKAN DATA OBSERVASI RESMI NASA FIRMS dan TIDAK BOLEH digunakan
dalam lingkungan produksi atau disajikan sebagai hotspot lapangan nyata.
"""

from typing import Any, Dict, List
import pytest

from app.cleaner import clean_and_deduplicate
from app.config import BOUNDARIES_PATH
from app.models import HotspotRecord
from app.pipeline import HotspotPipeline
from app.spatial_filter import IndonesiaSpatialFilter
from app.validation import (
    clean_optional_float,
    clean_optional_str,
    parse_and_validate_row,
    parse_timestamp,
    validate_coordinates,
)


# ==============================================================================
# Fixture Sintetis Khusus Audit (TEST ONLY)
# ==============================================================================

@pytest.fixture
def isolated_synthetic_fixture() -> str:
    """
    Dataset sintetis khusus audit dengan variasi kasus tepi:
    - Baris 1: Riau (Valid, NOAA-20, Day)
    - Baris 2: Riau (Identik dengan Baris 1, Duplikat)
    - Baris 3: Riau (Koordinat sama, tapi Satelit NOAA-21 -> BUKAN duplikat)
    - Baris 4: Riau (Koordinat sama, tapi Jam berbeda 0415 -> BUKAN duplikat)
    - Baris 5: Merauke Papua (Valid Ujung Timur, Jam 3 digit '430' -> 04:30 UTC)
    - Baris 6: Kuala Lumpur Malaysia (Di luar batas Indonesia)
    - Baris 7: Samudera Hindia (Di luar batas Indonesia)
    - Baris 8: Koordinat tidak valid (lat = 95.5 > 90)
    - Baris 9: Koordinat tidak valid (lon = 'bukan_angka')
    - Baris 10: Timestamp corrupt (tanggal 2026-02-31, jam 9999)
    - Baris 11: Baris valid dengan nilai opsional kosong (FRP='', confidence='null', bright_ti4='NaN')
    """
    return (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-13,0400,21,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-13,0415,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
        "-8.49,140.40,330.0,0.5,0.4,2026-10-13,430,20,VIIRS,high,2.0NRT,300.0,28.0,D\n"
        "3.13,101.68,330.0,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,296.0,14.0,D\n"
        "-15.00,95.00,310.0,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,290.0,5.0,N\n"
        "95.50,100.00,320.0,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,292.0,10.0,D\n"
        "abc,100.00,320.0,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,292.0,10.0,D\n"
        "-2.21,113.92,320.0,0.4,0.4,2026-02-31,9999,20,VIIRS,nominal,2.0NRT,292.0,10.0,D\n"
        "-6.20,106.81,NaN,0.4,0.4,2026-10-13,0400,20,VIIRS,null,2.0NRT,,null,D\n"
    )


# ==============================================================================
# Audit Validasi Koordinat, Timestamp, dan Strict Null
# ==============================================================================

def test_audit_coordinate_validation():
    """Audit batas koordinat secara teliti."""
    # Koordinat sah
    assert validate_coordinates("0.0", "0.0") == (0.0, 0.0)
    assert validate_coordinates("-90.0", "180.0") == (-90.0, 180.0)
    assert validate_coordinates("90.0", "-180.0") == (90.0, -180.0)

    # Koordinat melampaui batas geografis
    assert validate_coordinates("90.0001", "100.0") is None
    assert validate_coordinates("-90.0001", "100.0") is None
    assert validate_coordinates("0.0", "180.0001") is None
    assert validate_coordinates("0.0", "-180.0001") is None

    # Tipe invalid
    assert validate_coordinates("NaN", "100.0") is None
    assert validate_coordinates("inf", "100.0") is None
    assert validate_coordinates("-inf", "100.0") is None
    assert validate_coordinates("", "100.0") is None
    assert validate_coordinates(None, None) is None


def test_audit_timestamp_parsing():
    """Audit parsing waktu lintasan satelit ke ISO-8601 UTC."""
    # Jam 4 digit standar
    assert parse_timestamp("2026-10-13", "0400") == "2026-10-13T04:00:00Z"
    # Jam 3 digit (padding leading zero: '400' -> '0400')
    assert parse_timestamp("2026-10-13", "400") == "2026-10-13T04:00:00Z"
    assert parse_timestamp("2026-10-13", "5") == "2026-10-13T00:05:00Z"

    # Waktu tidak sah
    assert parse_timestamp("2026-10-13", "2400") is None   # jam 24:00 tidak sah
    assert parse_timestamp("2026-10-13", "1260") is None   # menit 60 tidak sah
    assert parse_timestamp("2026-10-13", "-100") is None   # negatif
    assert parse_timestamp("2026-02-29", "1200") is None   # 2026 bukan tahun kabisat!
    assert parse_timestamp("2026-13-01", "1200") is None   # bulan 13 tidak ada


def test_audit_strict_null_preservation():
    """Audit bahwa nilai opsional kosong TIDAK diimputasi/ditebak."""
    assert clean_optional_float("") is None
    assert clean_optional_float("null") is None
    assert clean_optional_float("NaN") is None
    assert clean_optional_float("none") is None
    assert clean_optional_float(None) is None
    assert clean_optional_float("0.0") == 0.0

    assert clean_optional_str("") is None
    assert clean_optional_str("   ") is None
    assert clean_optional_str("null") is None
    assert clean_optional_str(None) is None
    assert clean_optional_str("nominal") == "nominal"


# ==============================================================================
# Audit Deduplikasi
# ==============================================================================

def test_audit_deduplication_rules():
    """
    Audit aturan deduplikasi:
    - Duplikat persis dieliminasi.
    - Observasi di koordinat sama dari satelit berbeda dipertahankan.
    - Observasi di koordinat sama pada waktu berbeda dipertahankan.
    """
    rows = [
        {"latitude": "0.53", "longitude": "101.44", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        {"latitude": "0.53", "longitude": "101.44", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"}, # Duplikat
        {"latitude": "0.53", "longitude": "101.44", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "21"}, # Beda satelit
        {"latitude": "0.53", "longitude": "101.44", "acq_date": "2026-10-13", "acq_time": "0415", "satellite": "20"}, # Beda waktu
    ]

    valid, stats = clean_and_deduplicate(rows)

    assert len(valid) == 3
    assert stats.total_initial_records == 4
    assert stats.total_valid_records == 3
    assert stats.total_rejected_records == 1
    assert stats.reasons.get("duplicate_record") == 1


# ==============================================================================
# Audit Filter Geospasial Point-in-Polygon
# ==============================================================================

def test_audit_spatial_filtering_points():
    """Audit pengujian titik di dalam daratan Indonesia vs luar daratan."""
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Titik daratan Indonesia
    assert spatial_filter.is_inside(101.44, 0.53)[0] is True   # Riau
    assert spatial_filter.is_inside(140.40, -8.49)[0] is True  # Merauke Papua
    assert spatial_filter.is_inside(95.31, 5.89)[0] is True    # Sabang Aceh
    assert spatial_filter.is_inside(123.05, -10.74)[0] is True # Rote Ndao NTT

    # Titik luar daratan Indonesia
    assert spatial_filter.is_inside(101.68, 3.13)[0] is False  # Kuala Lumpur
    assert spatial_filter.is_inside(95.00, -15.00)[0] is False # Samudera Hindia
    assert spatial_filter.is_inside(108.00, 8.00)[0] is False  # Laut Cina Selatan
    assert spatial_filter.is_inside(130.84, -12.46)[0] is False# Darwin Australia


# ==============================================================================
# Audit Kepatuhan GeoJSON (RFC 7946) & Urutan Koordinat
# ==============================================================================

def test_audit_geojson_rfc7946_spec(isolated_synthetic_fixture: str, tmp_path):
    """
    Audit kepatuhan keluaran GeoJSON terhadap standar RFC 7946:
    1. Tipe root adalah FeatureCollection.
    2. Setiap elemen dalam features bertipe Feature.
    3. Geometri bertipe Point.
    4. Koordinat WGS84: index 0 = LONGITUDE, index 1 = LATITUDE.
    5. Preservasi atribut tanpa imputasi.
    """
    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key=""
    )

    result = pipeline.run(raw_csv_override=isolated_synthetic_fixture)

    # 1. Root FeatureCollection
    assert result["type"] == "FeatureCollection"
    assert "features" in result
    assert "provenance" in result

    features = result["features"]
    # Total baris sintetis 11:
    # - 1 duplikat ditolak
    # - 3 di luar Indonesia ditolak (KL, Samudera Hindia)
    # - 3 invalid ditolak (lat 95.5, lon 'abc', tgl 2026-02-31)
    # - Lolos: Baris 1 (Riau sat 20), Baris 3 (Riau sat 21), Baris 4 (Riau jam 0415),
    #          Baris 5 (Merauke), Baris 11 (Jakarta null)
    # Total lolos = 5 fitur
    assert len(features) == 5

    for feat in features:
        # 2. Tipe Feature
        assert feat["type"] == "Feature"

        # 3. Geometri Point
        geom = feat["geometry"]
        assert geom["type"] == "Point"

        # 4. Urutan Koordinat: [longitude, latitude]
        coords = geom["coordinates"]
        assert isinstance(coords, list)
        assert len(coords) == 2
        lon, lat = coords[0], coords[1]

        # Longitude Indonesia: ~95 s.d. 141.5
        assert 95.0 <= lon <= 141.5
        # Latitude Indonesia: ~ -11.0 s.d. 6.0
        assert -11.0 <= lat <= 6.0

        # 5. Preservasi Atribut
        props = feat["properties"]
        assert "observation_time_utc" in props
        assert "acq_date" in props
        assert "acq_time" in props
        assert "satellite" in props
        assert "instrument" in props
        assert "confidence" in props
        assert "frp" in props
        assert "province" in props
        assert props["province"] is not None

    # Periksa fitur dengan nilai opsional null (Baris 11 / Jakarta)
    null_feat = [f for f in features if f["geometry"]["coordinates"][1] == -6.20][0]
    assert null_feat["properties"]["confidence"] is None
    assert null_feat["properties"]["frp"] is None
    assert null_feat["properties"]["bright_ti4"] is None


# ==============================================================================
# Audit Isolasi Provenance Data Sintetis
# ==============================================================================

def test_audit_provenance_synthetic_isolation(isolated_synthetic_fixture: str, tmp_path):
    """
    Audit bahwa data sintetis TIDAK PERNAH mengklaim 'LIVE_API'
    atau menyamar sebagai data live nyata.
    """
    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key=""
    )

    result = pipeline.run(raw_csv_override=isolated_synthetic_fixture)
    prov = result["provenance"]

    # Wajib bertipe TEST_FIXTURE_STREAM dan status TEST_FIXTURE
    assert prov["data_source"] == "TEST_FIXTURE_STREAM"
    assert prov["status"] == "TEST_FIXTURE"
    assert "TEST ONLY" in prov["status_message"]
    assert prov["status"] != "LIVE_API"
    assert prov["is_snapshot"] is False
