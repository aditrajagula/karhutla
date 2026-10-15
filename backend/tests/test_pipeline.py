"""
Pengujian Unit dan Integrasi untuk Pipeline Data Hotspot End-to-End.
"""

from pathlib import Path
from app.config import BOUNDARIES_PATH
from app.pipeline import HotspotPipeline
from app.snapshot_manager import save_team_snapshot


def test_pipeline_with_synthetic_stream(synthetic_csv_content: str, tmp_path: Path):
    """
    Menguji alur lengkap pipeline dengan stream data sintetis TEST ONLY:
    Validasi, pembersihan, deduplikasi, spatial filtering, dan output GeoJSON.
    """
    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key=""
    )

    result = pipeline.run(raw_csv_override=synthetic_csv_content)

    assert result["type"] == "FeatureCollection"
    provenance = result["provenance"]
    assert provenance["data_source"] == "TEST_FIXTURE_STREAM"

    audit = provenance["audit_stats"]
    assert audit["total_initial_records"] == 12

    # Rincian audit:
    # 2 baris invalid koordinat ('95.0' dan 'abc')
    # 1 baris invalid timestamp ('invalid-date')
    # 2 baris duplikat persis
    # 3 baris di luar Indonesia (KL Malaysia, Laut Cina Selatan, Samudera Hindia)
    # 4 baris valid di Indonesia (Riau, Palangkaraya, Pontianak, Jakarta)
    assert audit["reasons"].get("invalid_coordinates") == 2
    assert audit["reasons"].get("invalid_timestamp") == 1
    assert audit["reasons"].get("duplicate_record") == 2
    assert audit["reasons"].get("outside_indonesia_boundary") == 3

    features = result["features"]
    assert len(features) == 4

    # Periksa struktur Feature GeoJSON standar (RFC 7946)
    for feat in features:
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        coords = feat["geometry"]["coordinates"]
        assert len(coords) == 2
        # Koordinat: [longitude, latitude]
        lon, lat = coords
        assert 95.0 <= lon <= 141.5
        assert -11.0 <= lat <= 6.0
        assert feat["properties"]["province"] is not None

    # Periksa titik dengan nilai opsional kosong (fitur terakhir / Jakarta)
    jakarta_feat = [f for f in features if f["geometry"]["coordinates"][1] == -6.20][0]
    assert jakarta_feat["properties"]["confidence"] is None
    assert jakarta_feat["properties"]["frp"] is None
    assert "DKI Jakarta" in jakarta_feat["properties"]["province"] or "Jakarta" in jakarta_feat["properties"]["province"]


def test_pipeline_no_api_key_and_no_snapshot(tmp_path: Path):
    """
    Menguji perilaku pipeline saat API key belum diisi dan belum ada snapshot lokal tim.
    Sistem wajib mengembalikan status informatif tanpa crash.
    """
    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key=""
    )

    result = pipeline.run()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 0
    prov = result["provenance"]
    assert prov["data_source"] == "NONE"
    assert "belum dikonfigurasi" in prov["status_message"]
    assert "belum ada snapshot lokal tim" in prov["status_message"]


def test_pipeline_fallback_to_team_snapshot(tmp_path: Path):
    """
    Menguji mekanisme fallback otomatis ke snapshot lokal tim saat live API tidak memiliki kredensial.
    """
    sample_csv = (
        "latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti4,bright_ti5,frp,daynight\n"
        "0.53,101.44,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,320.0,295.0,12.0,D\n"
    )

    # Simpan snapshot lokal tim terlebih dahulu
    save_team_snapshot(
        raw_csv_content=sample_csv,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        record_count=1
    )

    # Jalankan pipeline tanpa MAP_KEY
    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key=""
    )

    result = pipeline.run()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    prov = result["provenance"]
    assert prov["is_snapshot"] is True
    assert prov["data_source"] == "LOCAL_TEAM_SNAPSHOT"
    assert prov["snapshot_type"] == "TEAM_LOCAL_CAPTURE"
    assert "fallback snapshot lokal tim" in prov["status_message"]
