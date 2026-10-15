"""
Pengujian Komprehensif Integrasi Raster Hansen Global Forest Change ke FireGuard.
Mencakup:
Bagian A: hansen_tile_reader (koordinat, tile, layer, NoData, bounds, corrupt file, cache, fallback)
Bagian B: forest_change_service (evaluasi titik, status taxonomy, degradasi tanpa data, demonstrasi metadata)
Bagian C: evidence_service & endpoints (pembukaan_lahan, perubahan_tutupan, isolasi kebakaran FIRMS, privasi)
"""

import os
from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from app.main import app
from app.hansen_tile_reader import (
    clear_pixel_cache,
    get_cache_size,
    get_hansen_tile_id,
    get_tile_bounds,
    is_coordinate_in_kalimantan,
    read_hansen_pixel,
    read_pixel_from_raster,
    resolve_layer_source,
    STATUS_OUT_OF_SCOPE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NO_DATA_OR_NON_FOREST,
    STATUS_NO_LOSS_DETECTED,
    STATUS_LOSS_DETECTED,
)
from app.forest_change_service import (
    calculate_pixel_area_ha,
    evaluate_forest_change_point,
    get_forest_loss_summary,
    HANSEN_PROVINCIAL_BASELINE_HA,
)
from app.evidence_service import assess_report_evidence


@pytest.fixture
def synthetic_hansen_dir(tmp_path: Path):
    """
    Membuat fixture raster GeoTIFF mini sintetis (10x10 piksel)
    untuk tile '00N_110E' dengan proyeksi EPSG:4326.
    Resolusi 0.00025° per piksel, origin (top-left) pada (110.0, 0.0).
    """
    # 1. Layer lossyear
    # (0, 0) -> 15 (kehilangan tahun 2015)
    # (0, 1) -> 0  (tidak ada kehilangan kanopi)
    # (1, 0) -> 23 (kehilangan tahun 2023)
    # (1, 1) -> 99 (nilai lossyear tidak valid / di luar 1..25)
    # (2, 0) -> 0  (baseline non-hutan)
    # (3, 0) -> 0  (air / water)
    # (4, 0) -> 0  (nodata / ocean)
    lossyear_data = np.zeros((10, 10), dtype=np.uint8)
    lossyear_data[0, 0] = 15
    lossyear_data[0, 1] = 0
    lossyear_data[1, 0] = 23
    lossyear_data[1, 1] = 99

    # 2. Layer treecover2000
    treecover_data = np.full((10, 10), 80, dtype=np.uint8)
    treecover_data[0, 0] = 85
    treecover_data[0, 1] = 90
    treecover_data[1, 0] = 75
    treecover_data[2, 0] = 0   # Non-forest baseline

    # 3. Layer datamask (1 = land, 2 = water, 0 = nodata)
    datamask_data = np.ones((10, 10), dtype=np.uint8)
    datamask_data[3, 0] = 2   # Permanent water
    datamask_data[4, 0] = 0   # No data

    transform = from_origin(110.0, 0.0, 0.00025, 0.00025)
    version = "GFC-2025-v1.13"
    tile_id = "00N_110E"

    for layer_name, data in [
        ("lossyear", lossyear_data),
        ("treecover2000", treecover_data),
        ("datamask", datamask_data),
    ]:
        file_path = tmp_path / f"Hansen_{version}_{layer_name}_{tile_id}.tif"
        with rasterio.open(
            file_path,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype=data.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data, 1)

    return tmp_path


# =============================================================================
# BAGIAN A: Pengujian hansen_tile_reader.py
# =============================================================================

def test_tile_determination_coordinates():
    """Menguji penentuan tile Hansen 10x10 derajat untuk berbagai titik."""
    # Titik Kalimantan Barat (Selatan) -> 00N_100E
    assert get_hansen_tile_id(-1.5, 109.5) == "00N_100E"
    # Titik Kalimantan Tengah / Selatan -> 00N_110E
    assert get_hansen_tile_id(-2.21, 113.92) == "00N_110E"
    # Titik Kalimantan Barat (Utara) -> 10N_100E
    assert get_hansen_tile_id(0.8, 109.2) == "10N_100E"
    # Titik Kalimantan Utara -> 10N_110E
    assert get_hansen_tile_id(3.2, 116.5) == "10N_110E"


def test_tile_boundaries_and_edges():
    """Menguji perhitungan batas geografis tile dan koordinat tepat di perbatasan."""
    bounds = get_tile_bounds("00N_110E")
    # min_lon, min_lat, max_lon, max_lat
    assert bounds == (110.0, -10.0, 120.0, 0.0)

    # Koordinat tepat pada khatulistiwa (0.0): masuk ke tile 00N
    assert get_hansen_tile_id(0.0, 110.5) == "00N_110E"
    # Koordinat tepat pada garis bujur 110.0: masuk ke tile 110E
    assert get_hansen_tile_id(-1.0, 110.0) == "00N_110E"


def test_reader_out_of_scope_coordinates():
    """Menguji penolakan koordinat di luar cakupan 5 provinsi Kalimantan."""
    clear_pixel_cache()
    # Jawa Barat (di luar Kalimantan)
    res_jawa = read_hansen_pixel(lat=-6.9, lon=107.6, province="Jawa Barat")
    assert res_jawa.status == STATUS_OUT_OF_SCOPE
    assert res_jawa.category_result == "Belum dapat dinilai"
    assert res_jawa.raster_available is False
    assert res_jawa.data_verified is False

    # Sarawak, Malaysia
    res_sarawak = read_hansen_pixel(lat=2.5, lon=113.0, province="Sarawak")
    assert res_sarawak.status == STATUS_OUT_OF_SCOPE
    assert res_sarawak.category_result == "Belum dapat dinilai"


def test_reader_valid_loss_pixel(synthetic_hansen_dir: Path):
    """Menguji pembacaan piksel dengan kehilangan tutupan pohon (lossyear = 15 -> 2015)."""
    clear_pixel_cache()
    # Koordinat piksel (0, 0): lon = 110.0001, lat = -0.0001
    res = read_hansen_pixel(
        lat=-0.0001,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res.status == STATUS_LOSS_DETECTED
    assert res.loss_detected is True
    assert res.loss_year == 2015
    assert res.raw_lossyear == 15
    assert res.treecover2000 == 85
    assert res.datamask == 1
    assert res.category_result == "Ada indikasi pendukung"
    assert res.data_status == "raster_verified"
    assert res.data_verified is True
    assert res.raster_available is True
    assert res.tile_id == "00N_110E"
    assert res.pixel_row == 0
    assert res.pixel_col == 0


def test_reader_valid_no_loss_pixel(synthetic_hansen_dir: Path):
    """Menguji pembacaan piksel tanpa kehilangan pada data valid (lossyear = 0)."""
    clear_pixel_cache()
    # Koordinat piksel (0, 1): lon = 110.00035, lat = -0.0001
    res = read_hansen_pixel(
        lat=-0.0001,
        lon=110.00035,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res.status == STATUS_NO_LOSS_DETECTED
    assert res.loss_detected is False
    assert res.loss_year is None
    assert res.raw_lossyear == 0
    assert res.treecover2000 == 90
    assert res.category_result == "Belum ditemukan kecocokan"
    assert res.data_status == "raster_verified"
    assert res.data_verified is True
    assert res.raster_available is True


def test_reader_nodata_and_water_handling(synthetic_hansen_dir: Path):
    """Menguji pemisahan area air permanen dan nodata dari tidak ada kehilangan."""
    clear_pixel_cache()
    # Piksel (3, 0): datamask = 2 (air) -> lat = -0.00075, lon = 110.0001
    res_water = read_hansen_pixel(
        lat=-0.00075,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res_water.status == STATUS_NO_DATA_OR_NON_FOREST
    assert res_water.loss_detected is False
    assert res_water.category_result == "Belum dapat dinilai"
    assert res_water.datamask == 2

    # Piksel (4, 0): datamask = 0 (NoData / laut) -> lat = -0.00100, lon = 110.0001
    res_nodata = read_hansen_pixel(
        lat=-0.00100,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res_nodata.status == STATUS_NO_DATA_OR_NON_FOREST
    assert res_nodata.loss_detected is False
    assert res_nodata.category_result == "Belum dapat dinilai"
    assert res_nodata.datamask == 0


def test_reader_non_forest_baseline_handling(synthetic_hansen_dir: Path):
    """Menguji area non-hutan (treecover2000=0 dan lossyear=0)."""
    clear_pixel_cache()
    # Piksel (2, 0): treecover2000 = 0, lossyear = 0 -> lat = -0.0005, lon = 110.0001
    res_non_forest = read_hansen_pixel(
        lat=-0.0005,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res_non_forest.status == STATUS_NO_DATA_OR_NON_FOREST
    assert res_non_forest.category_result == "Belum dapat dinilai"


def test_reader_invalid_lossyear_value(synthetic_hansen_dir: Path):
    """Menguji penanganan nilai lossyear di luar rentang valid 1..25."""
    clear_pixel_cache()
    # Piksel (1, 1): lossyear = 99 -> lat = -0.00035, lon = 110.00035
    res = read_hansen_pixel(
        lat=-0.00035,
        lon=110.00035,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.data_verified is False
    assert "tidak valid" in (res.error_message or "").lower()


def test_reader_corrupt_raster_file(tmp_path: Path):
    """Menguji penanganan berkas raster GeoTIFF yang rusak (corrupt)."""
    clear_pixel_cache()
    corrupt_file = tmp_path / "Hansen_GFC-2025-v1.13_lossyear_00N_110E.tif"
    corrupt_file.write_bytes(b"BOGUS_CORRUPTED_TIFF_HEADER_1234567890")

    res = read_hansen_pixel(
        lat=-0.0001,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=tmp_path,
        enable_remote=False,
    )
    # PENTING: File corrupt TIDAK BOLEH dianggap lossyear=0 (no loss)!
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.category_result == "Belum dapat dinilai"
    assert res.loss_detected is False
    assert res.raster_available is False
    assert res.error_message is not None
    assert "kegagalan infrastruktur" in res.error_message.lower()


def test_reader_missing_tile_fallback(tmp_path: Path):
    """Menguji jika file tile lokal tidak ada dan akses remote non-aktif."""
    clear_pixel_cache()
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)

    res = read_hansen_pixel(
        lat=-2.21,
        lon=113.92,
        province="Kalimantan Tengah",
        tiles_dir=empty_dir,
        enable_remote=False,
    )
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.category_result == "Belum dapat dinilai"
    assert res.raster_available is False
    assert res.data_status == "demonstration"
    assert res.data_verified is False


def test_reader_cache_functionality(synthetic_hansen_dir: Path):
    """Menguji bahwa cache memori menyimpan hasil dan dapat dibersihkan."""
    clear_pixel_cache()
    assert get_cache_size() == 0

    # Panggilan pertama: cache miss
    res1 = read_hansen_pixel(
        lat=-0.0001,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
        use_cache=True,
    )
    assert get_cache_size() == 1

    # Panggilan kedua: membaca dari cache
    res2 = read_hansen_pixel(
        lat=-0.0001,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
        use_cache=True,
    )
    assert get_cache_size() == 1
    assert res1.status == res2.status
    assert res1.loss_year == res2.loss_year

    clear_pixel_cache()
    assert get_cache_size() == 0


# =============================================================================
# BAGIAN B: Pengujian forest_change_service.py Integrasi Raster
# =============================================================================

def test_forest_change_service_pixel_loss(synthetic_hansen_dir: Path):
    """Menguji evaluate_forest_change_point dengan raster aktual (kehilangan terdeteksi)."""
    clear_pixel_cache()
    eval_res = evaluate_forest_change_point(
        lat=-0.0001,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert eval_res["status"] == "SUPPORTING_INDICATION"
    assert eval_res["internal_status"] == STATUS_LOSS_DETECTED
    assert eval_res["category_result"] == "Ada indikasi pendukung"
    assert eval_res["data_status"] == "raster_verified"
    assert eval_res["data_verified"] is True
    assert eval_res["raster_available"] is True
    assert eval_res["pixel_data"]["loss_detected"] is True
    assert eval_res["pixel_data"]["loss_year"] == 2015
    assert "tidak secara otomatis membuktikan" in eval_res["scientific_caveat"].lower()


def test_forest_change_service_pixel_no_loss(synthetic_hansen_dir: Path):
    """Menguji evaluate_forest_change_point dengan raster aktual (tidak ada kehilangan)."""
    clear_pixel_cache()
    eval_res = evaluate_forest_change_point(
        lat=-0.0001,
        lon=110.00035,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert eval_res["status"] == "NO_MATCH_FOUND"
    assert eval_res["internal_status"] == STATUS_NO_LOSS_DETECTED
    assert eval_res["category_result"] == "Belum ditemukan kecocokan"
    assert eval_res["data_status"] == "raster_verified"
    assert eval_res["data_verified"] is True
    assert eval_res["raster_available"] is True
    assert eval_res["pixel_data"]["loss_detected"] is False


def test_forest_change_service_no_data_or_non_forest(synthetic_hansen_dir: Path):
    """Menguji evaluasi tutupan pohon pada perairan atau area tanpa data."""
    clear_pixel_cache()
    eval_res = evaluate_forest_change_point(
        lat=-0.00075,
        lon=110.0001,
        province="Kalimantan Tengah",
        tiles_dir=synthetic_hansen_dir,
        enable_remote=False,
    )
    assert eval_res["status"] == STATUS_NO_DATA_OR_NON_FOREST
    assert eval_res["category_result"] == "Belum dapat dinilai"
    assert eval_res["raster_available"] is True
    assert eval_res["data_verified"] is True


def test_forest_change_service_demonstration_baseline_remains_unverified():
    """Memverifikasi bahwa agregat statistik provinsi TETAP berstatus demonstrasi."""
    summary = get_forest_loss_summary()
    assert summary["data_status"] == "demonstration"
    assert summary["data_verified"] is False
    for prov in summary["provincial_data"]:
        assert prov["data_status"] == "demonstration"
        assert prov["data_verified"] is False
        assert "belum diverifikasi" in prov["verification_notes"].lower()


# =============================================================================
# BAGIAN C: Pengujian evidence_service.py dan API Endpoints
# =============================================================================

def test_evidence_service_land_clearing_with_loss_pixel(synthetic_hansen_dir: Path, monkeypatch):
    """
    Menguji bahwa laporan pembukaan_lahan menghasilkan SUPPORTING_INDICATION
    ketika raster memvalidasi kehilangan tutupan kanopi pohon.
    """
    clear_pixel_cache()
    # Atur direktori tile default ke fixture sintetis
    monkeypatch.setattr("app.forest_change_service.HANSEN_TILES_DIR", synthetic_hansen_dir)
    monkeypatch.setattr("app.hansen_tile_reader.HANSEN_TILES_DIR", synthetic_hansen_dir)

    report = {
        "category": "pembukaan_lahan",
        "latitude": -0.0001,
        "longitude": 110.0001,
        "observed_at_utc": "2026-10-10T08:00:00Z",
        "province": "Kalimantan Tengah",
    }
    evidence = assess_report_evidence(report, hotspots=[], firms_available=True)
    assert evidence["assessment_code"] == "SUPPORTING_INDICATION"
    assert evidence["category_result"] == "Ada indikasi pendukung"
    assert evidence["evidence_type"] == "hansen_gfc_treecover_loss"
    assert evidence["details"]["pixel_data"]["loss_detected"] is True
    assert evidence["details"]["pixel_data"]["loss_year"] == 2015
    assert "tidak digunakan sebagai bukti pembukaan lahan" in evidence["limitations_caveat"].lower()


def test_evidence_service_land_clearing_with_no_loss_pixel(synthetic_hansen_dir: Path, monkeypatch):
    """
    Menguji bahwa laporan pembukaan_lahan menghasilkan NO_MATCH_FOUND
    ketika raster valid tidak menemukan kehilangan kanopi.
    """
    clear_pixel_cache()
    monkeypatch.setattr("app.forest_change_service.HANSEN_TILES_DIR", synthetic_hansen_dir)
    monkeypatch.setattr("app.hansen_tile_reader.HANSEN_TILES_DIR", synthetic_hansen_dir)

    report = {
        "category": "pembukaan_lahan",
        "latitude": -0.0001,
        "longitude": 110.00035,
        "observed_at_utc": "2026-10-10T08:00:00Z",
        "province": "Kalimantan Tengah",
    }
    evidence = assess_report_evidence(report, hotspots=[], firms_available=True)
    assert evidence["assessment_code"] == "NO_MATCH_FOUND"
    assert evidence["category_result"] == "Belum ditemukan kecocokan"
    assert evidence["evidence_type"] == "hansen_gfc_treecover_loss"


def test_evidence_service_land_clearing_nodata_yields_insufficient_data(synthetic_hansen_dir: Path, monkeypatch):
    """
    Menguji bahwa area air atau NoData menghasilkan INSUFFICIENT_DATA ('Belum dapat dinilai').
    """
    clear_pixel_cache()
    monkeypatch.setattr("app.forest_change_service.HANSEN_TILES_DIR", synthetic_hansen_dir)
    monkeypatch.setattr("app.hansen_tile_reader.HANSEN_TILES_DIR", synthetic_hansen_dir)

    report = {
        "category": "perubahan_tutupan",
        "latitude": -0.00075,
        "longitude": 110.0001,
        "observed_at_utc": "2026-10-10T08:00:00Z",
        "province": "Kalimantan Tengah",
    }
    evidence = assess_report_evidence(report, hotspots=[], firms_available=True)
    assert evidence["assessment_code"] == "INSUFFICIENT_DATA"
    assert evidence["category_result"] == "Belum dapat dinilai"
    assert "badan air" in evidence["summary"].lower() or "bukan tutupan kanopi" in evidence["summary"].lower()


def test_fire_category_logic_unaffected(synthetic_hansen_dir: Path, monkeypatch):
    """
    Memastikan logika kategori kebakaran NASA FIRMS sama sekali tidak terpengaruh
    oleh integrasi reader Hansen.
    """
    monkeypatch.setattr("app.forest_change_service.HANSEN_TILES_DIR", synthetic_hansen_dir)
    monkeypatch.setattr("app.hansen_tile_reader.HANSEN_TILES_DIR", synthetic_hansen_dir)

    report_fire = {
        "category": "kebakaran",
        "latitude": -0.02,
        "longitude": 109.34,
        "observed_at_utc": "2026-10-10T04:00:00Z",
        "province": "Kalimantan Barat",
    }
    mock_hotspots = [
        {
            "geometry": {"coordinates": [109.345, -0.021]},
            "properties": {"satellite": "VIIRS", "acq_date": "2026-10-10", "acq_time": "0400", "frp": 30.0}
        }
    ]
    ev = assess_report_evidence(report_fire, hotspots=mock_hotspots, firms_available=True)
    assert ev["evidence_type"] == "thermal_anomaly_satellite"
    assert ev["assessment_code"] == "SUPPORTING_INDICATION"
    assert ev["category_result"] == "Ada indikasi pendukung"


def test_api_forest_loss_point_with_raster_fixture(synthetic_hansen_dir: Path, monkeypatch):
    """
    Menguji endpoint REST API /api/v1/forest-loss/point saat file raster lokal tersedia.
    """
    clear_pixel_cache()
    monkeypatch.setattr("app.forest_change_service.HANSEN_TILES_DIR", synthetic_hansen_dir)
    monkeypatch.setattr("app.hansen_tile_reader.HANSEN_TILES_DIR", synthetic_hansen_dir)

    client = TestClient(app)
    # Titik piksel (0, 0) yang memiliki kehilangan kanopi
    res = client.get("/api/v1/forest-loss/point?latitude=-0.0001&longitude=110.0001&province=Kalimantan%20Tengah")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUPPORTING_INDICATION"
    assert data["category_result"] == "Ada indikasi pendukung"
    assert data["data_status"] == "raster_verified"
    assert data["data_verified"] is True
    assert data["raster_available"] is True
    assert data["pixel_data"]["loss_detected"] is True
    assert data["pixel_data"]["loss_year"] == 2015


def test_province_spoofing_outside_kalimantan_strictly_rejected():
    """
    Audit Geospasial: Memastikan parameter nama provinsi tidak dapat membuat
    koordinat yang sebenarnya di luar wilayah 5 provinsi Kalimantan menjadi valid.
    """
    clear_pixel_cache()
    # 1. Titik di Sarawak (lat 3.5, lon 114.0) dengan klaim provinsi 'Kalimantan Timur'
    inside, prov = is_coordinate_in_kalimantan(3.5, 114.0, province="Kalimantan Timur")
    assert inside is False
    assert prov is None

    res_sarawak = read_hansen_pixel(3.5, 114.0, province="Kalimantan Timur")
    assert res_sarawak.status == STATUS_OUT_OF_SCOPE
    assert res_sarawak.category_result == "Belum dapat dinilai"

    # 2. Titik di Laut Jawa / Selat Makassar (lat -4.5, lon 118.0) dengan klaim 'Kalimantan Selatan'
    inside_ocean, prov_ocean = is_coordinate_in_kalimantan(-4.5, 118.0, province="Kalimantan Selatan")
    assert inside_ocean is False
    assert prov_ocean is None

    # 3. Titik di Kuching (lat 1.55, lon 110.35) dengan klaim 'Kalimantan Barat'
    inside_kuching, prov_kuching = is_coordinate_in_kalimantan(1.55, 110.35, province="Kalimantan Barat")
    assert inside_kuching is False


def test_out_of_scope_with_mock_raster_pixel_value_rejected():
    """
    Audit Geospasial: Memastikan bahwa titik di luar wilayah Kalimantan
    TIDAK BISA dipaksa menjadi SUPPORTING_INDICATION meskipun pemanggil
    menyuplai raster_pixel_value mock.
    """
    clear_pixel_cache()
    eval_res = evaluate_forest_change_point(
        lat=3.5,
        lon=114.0,
        province="Sarawak",
        pixel_raster_available=True,
        raster_pixel_value={"loss_detected": True, "loss_year": 2024, "treecover2000": 90}
    )
    assert eval_res["status"] == "INSUFFICIENT_DATA"
    assert eval_res["internal_status"] == STATUS_OUT_OF_SCOPE
    assert eval_res["category_result"] == "Belum dapat dinilai"
    assert eval_res["raster_available"] is False


def test_remote_failure_never_converts_to_no_loss(monkeypatch):
    """
    Audit Keamanan & Integritas: Memastikan kegagalan akses remote atau lokal
    TIDAK PERNAH diubah menjadi NO_LOSS_DETECTED (lossyear=0).
    """
    clear_pixel_cache()

    def mock_read_error(*args, **kwargs):
        raise rasterio.errors.RasterioIOError("HTTP 500: Remote GCS gateway timeout simulated")

    monkeypatch.setattr("app.hansen_tile_reader.read_pixel_from_raster", mock_read_error)
    monkeypatch.setattr("app.hansen_tile_reader.resolve_layer_source", lambda *args, **kwargs: ("https://mock.tif", "remote_range"))

    res = read_hansen_pixel(
        lat=-2.21,
        lon=113.92,
        province="Kalimantan Tengah",
        enable_remote=True,
        use_cache=False
    )
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.status != STATUS_NO_LOSS_DETECTED
    assert res.loss_detected is False
    assert res.category_result == "Belum dapat dinilai"
    assert res.raster_available is False
    assert res.data_verified is False
    assert "kegagalan infrastruktur" in (res.error_message or "").lower()
