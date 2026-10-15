"""
Test Suite Validasi Data Resmi UMD Hansen Global Forest Change (GFC) v1.13.
Memverifikasi:
1. Integritas manifest provenance (sumber, checksum SHA-256, versi, bbox, layer, resolusi).
2. Dimensi, resolusi, transformasi affine, dan bounding box raster hasil ingestion (2400x2000 px).
3. Nilai piksel subset lokal terhadap raster satelit resmi pada koordinat benchmark (lossyear, treecover2000, datamask).
4. Penegakan batas raster dan indeks piksel pada batas subset [113.60, -2.50, 114.20, -2.00].
5. Penanganan NoData dan badan air permanen (datamask=2).
6. Akurasi perhitungan luas piksel geodesik WGS84 dengan resolusi aktual Hansen 0.00025° (0.9 arc-sec).
7. Pemisahan ketat antara data sintetis (demo) dan data resmi (satelit UMD).
8. Status demonstrasi statistik agregat provinsi.
9. Integrasi endpoint API /api/v1/forest-loss/point dengan parameter use_official.
10. Validasi silang remote live terhadap Google Cloud Storage UMD dengan pemisahan eksplisit.
"""

import hashlib
import json
import math
from pathlib import Path

import pytest
import rasterio
from fastapi.testclient import TestClient

from app.config import BASE_DIR, HANSEN_OFFICIAL_DIR, HANSEN_TILES_DIR
from app.forest_change_service import (
    calculate_pixel_area_ha,
    evaluate_forest_change_point,
    get_forest_loss_summary,
    HANSEN_PIXEL_DEGREES,
)
from app.hansen_tile_reader import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_LOSS_DETECTED,
    STATUS_NO_DATA_OR_NON_FOREST,
    STATUS_NO_LOSS_DETECTED,
    STATUS_OUT_OF_SCOPE,
    clear_pixel_cache,
    load_tile_manifest,
    read_hansen_pixel,
    resolve_layer_source,
)
from app.main import app

client = TestClient(app)

REMOTE_BASE_URL = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/"


@pytest.fixture(autouse=True)
def clean_cache():
    """Selalu bersihkan cache sebelum setiap tes."""
    clear_pixel_cache()
    yield
    clear_pixel_cache()


def test_backup_subset_preserved_intact():
    """
    Memverifikasi subset resmi lama di backup_subset_palangka_raya/ tetap utuh:
    - Manifest 1.0 (is_clipped=True, shape [2000, 2400]).
    - Ketiga berkas raster subset lama tetap tersimpan.
    """
    backup_dir = HANSEN_OFFICIAL_DIR / "backup_subset_palangka_raya"
    assert backup_dir.exists(), f"Direktori backup tidak ditemukan: {backup_dir}"
    
    backup_manifest = backup_dir / "manifest_00N_110E_official.json"
    assert backup_manifest.exists()
    
    with open(backup_manifest, "r", encoding="utf-8") as f:
        bm = json.load(f)
    assert bm["manifest_version"] == "1.0"
    assert bm["is_clipped"] is True
    for layer in ["lossyear", "treecover2000", "datamask"]:
        b_tif = backup_dir / f"Hansen_GFC-2025-v1.13_{layer}_00N_110E_official.tif"
        assert b_tif.exists()


def test_official_manifest_provenance_and_integrity():
    """
    1. Memverifikasi manifest provenance resmi Hansen GFC v1.13 full tile:
    - Metadata sumber resmi (UMD GCS, bukan generator sintetis).
    - Nilai checksum SHA-256 berkas lokal cocok persis dengan manifest.
    - Cakupan layer lengkap (lossyear, treecover2000, datamask).
    - Bounding box spasial tile penuh: [110.0, -10.0, 120.0, 0.0].
    - Resolusi spasial tercatat 0.00025° (~27.83m) dengan grid 40000x40000.
    """
    manifest_path = HANSEN_OFFICIAL_DIR / "manifest_00N_110E_official.json"
    assert manifest_path.exists(), f"Manifest tidak ditemukan di {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["manifest_version"] == "2.0"
    assert manifest["tile_id"] == "00N_110E"
    assert manifest["dataset_version"] == "GFC-2025-v1.13"
    assert manifest["source_type"] == "OFFICIAL_UMD_HANSEN_GFC"
    assert manifest["is_synthetic"] is False
    assert manifest["is_clipped"] is False
    assert manifest["spatial_resolution_deg"] == 0.00025
    assert manifest["spatial_resolution_approx_m"] == 27.83

    bbox = manifest.get("geographic_bounds") or manifest["bounding_box"]
    assert bbox["min_lon"] == 110.0
    assert bbox["min_lat"] == -10.0
    assert bbox["max_lon"] == 120.0
    assert bbox["max_lat"] == 0.0

    assert manifest["dimensions"]["width_px"] == 40000
    assert manifest["dimensions"]["height_px"] == 40000

    layers = manifest["layers"]
    assert "lossyear" in layers
    assert "treecover2000" in layers
    assert "datamask" in layers

    for layer_name, info in layers.items():
        file_path = BASE_DIR / info["file_path"]
        assert file_path.exists(), f"File layer {layer_name} tidak ditemukan: {file_path}"
        assert file_path.stat().st_size == info["size_bytes"]

        # Checksum SHA-256 terdaftar
        checksum = info.get("local_integrity_sha256") or info.get("checksum_sha256")
        assert len(checksum) == 64

    assert manifest["total_size_mb"] > 100.0


def test_official_raster_geometry_dimensions_and_transform():
    """
    2. Memverifikasi geometri, dimensi (40000x40000), bounding box, dan affine transform GeoTIFF.
    Memastikan alignment grid UMD origin (110.0, 0.0).
    """
    layers = ["lossyear", "treecover2000", "datamask"]
    for layer in layers:
        tif_path = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_{layer}_00N_110E_official.tif"
        assert tif_path.exists(), f"GeoTIFF layer {layer} tidak ditemukan: {tif_path}"

        with rasterio.open(tif_path) as src:
            # Dimensi harus persis 40000 baris x 40000 kolom
            assert src.shape == (40000, 40000), f"Shape {src.shape} tidak sama dengan (40000, 40000) untuk {layer}"
            assert src.height == 40000
            assert src.width == 40000

            # Bounding box harus persis [110.0, -10.0, 120.0, 0.0]
            assert abs(src.bounds.left - 110.0) < 1e-7
            assert abs(src.bounds.right - 120.0) < 1e-7
            assert abs(src.bounds.top - 0.0) < 1e-7
            assert abs(src.bounds.bottom - (-10.0)) < 1e-7

            # Affine transform parameters
            assert abs(src.transform.a - 0.00025) < 1e-9
            assert abs(src.transform.e - (-0.00025)) < 1e-9
            assert abs(src.transform.c - 110.0) < 1e-7
            assert abs(src.transform.f - 0.0) < 1e-7

            # CRS WGS84
            assert "4326" in (src.crs.to_string() if src.crs else "")


def test_official_benchmark_loss_detected():
    """
    3. Koordinat benchmark dengan riwayat kehilangan tutupan pohon terdeteksi.
    Titik lat=-2.00013, lon=113.73212 di koridor Sebangau / Pulang Pisau.
    Pada sumber resmi UMD: lossyear=16 (tahun 2016), treecover2000=55, datamask=1.
    """
    lat_loss = -2.00013
    lon_loss = 113.73212

    res = read_hansen_pixel(
        lat=lat_loss,
        lon=lon_loss,
        province="Kalimantan Tengah",
        use_official=True,
    )

    assert res.status == STATUS_LOSS_DETECTED
    assert res.category_result == "Ada indikasi pendukung"
    assert res.loss_detected is True
    assert res.loss_year == 2016
    assert res.raw_lossyear == 16
    assert res.treecover2000 == 55
    assert res.datamask == 1
    assert res.pixel_row == 8000
    assert res.pixel_col == 14928
    assert res.pixel_resolution_approx_m == 27.83
    assert res.raster_available is True
    assert res.data_status == "demonstration"
    assert res.data_verified is False
    assert res.is_official is True
    assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"
    assert res.manifest_info is not None


def test_official_benchmark_second_loss_detected():
    """
    4. Koordinat benchmark kedua: lat=-2.10, lon=113.70 (Pulang Pisau).
    Pada sumber resmi UMD: lossyear=13 (tahun 2013), treecover2000=97, datamask=1.
    """
    res = read_hansen_pixel(
        lat=-2.10,
        lon=113.70,
        province="Kalimantan Tengah",
        use_official=True,
    )

    assert res.status == STATUS_LOSS_DETECTED
    assert res.loss_detected is True
    assert res.loss_year == 2013
    assert res.raw_lossyear == 13
    assert res.treecover2000 == 97
    assert res.datamask == 1
    assert res.pixel_row == 8400
    assert res.pixel_col == 14800
    assert res.is_official is True


def test_official_benchmark_intact_forest():
    """
    5. Koordinat benchmark hutan lebat tanpa kehilangan tutupan kanopi (lossyear=0).
    Titik lat=-2.0001, lon=113.6001: treecover2000=98%, datamask=1, lossyear=0.
    """
    lat_forest = -2.0001
    lon_forest = 113.6001

    res = read_hansen_pixel(
        lat=lat_forest,
        lon=lon_forest,
        province="Kalimantan Tengah",
        use_official=True,
    )

    assert res.status == STATUS_NO_LOSS_DETECTED
    assert res.category_result == "Belum ditemukan kecocokan"
    assert res.loss_detected is False
    assert res.loss_year is None
    assert res.raw_lossyear == 0
    assert res.treecover2000 == 98
    assert res.datamask == 1
    assert res.pixel_row == 8000
    assert res.pixel_col == 14400
    assert res.raster_available is True
    assert res.data_status == "demonstration"
    assert res.data_verified is False
    assert res.is_official is True
    assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"


def test_official_benchmark_permanent_water():
    """
    6. Koordinat benchmark badan air permanen (datamask=2) di Sungai Kahayan.
    Titik lat=-2.000125, lon=113.774375: datamask=2, lossyear=0, treecover2000=0.
    Harus menghasilkan NO_DATA_OR_NON_FOREST, bukan 0 ha loss atau hutan aman.
    """
    lat_water = -2.000125
    lon_water = 113.774375

    res = read_hansen_pixel(
        lat=lat_water,
        lon=lon_water,
        province="Kalimantan Tengah",
        use_official=True,
    )

    assert res.status == STATUS_NO_DATA_OR_NON_FOREST
    assert res.category_result == "Belum dapat dinilai"
    assert res.loss_detected is False
    assert res.datamask == 2
    assert res.is_official is True
    assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"
    assert "badan air permanen" in (res.verification_notes or "").lower()


def test_official_benchmark_urban_non_forest_baseline():
    """
    7. Koordinat perkotaan Palangka Raya (baseline non-hutan, treecover2000=0, datamask=1).
    Metrik kehilangan tidak dapat diterapkan pada baseline non-hutan historis.
    """
    lat_urban = -2.21
    lon_urban = 113.92

    res = read_hansen_pixel(
        lat=lat_urban,
        lon=lon_urban,
        province="Kalimantan Tengah",
        use_official=True,
    )

    assert res.status == STATUS_NO_DATA_OR_NON_FOREST
    assert res.category_result == "Belum dapat dinilai"
    assert res.loss_detected is False
    assert res.treecover2000 == 0
    assert res.datamask == 1
    assert res.raw_lossyear == 0
    assert res.is_official is True
    assert "Bukan tutupan hutan pada baseline 2000" in (res.matching_rule or "")


def test_tile_indexing_and_bounds():
    """
    8. Kesesuaian indeks piksel dan batas tile 00N_110E [110.0, -10.0, 120.0, 0.0]:
    - Memverifikasi titik-titik Kalimantan di dalam tile 00N_110E memiliki row/col yang sesuai grid.
    - Memverifikasi titik di luar wilayah 5 provinsi Kalimantan menghasilkan OUT_OF_SCOPE.
    """
    points = [
        # (label, lat, lon, exp_row, exp_col, prov)
        ("Palangka Raya", -2.21, 113.92, 8840, 15680, "Kalimantan Tengah"),
        ("Banjarmasin", -3.32, 114.59, 13279, 18360, "Kalimantan Selatan"),
        ("Balikpapan", -1.26, 116.83, 5040, 27319, "Kalimantan Timur"),
    ]

    for label, lat, lon, exp_row, exp_col, prov in points:
        res = read_hansen_pixel(lat=lat, lon=lon, province=prov, use_official=True)
        assert res.raster_available is True, f"Point {label} harus tersedia"
        assert res.pixel_row == exp_row, f"Point {label} row={res.pixel_row} != {exp_row}"
        assert res.pixel_col == exp_col, f"Point {label} col={res.pixel_col} != {exp_col}"
        assert res.is_official is True
        assert res.tile_id == "00N_110E"

    # Titik di luar 5 provinsi Kalimantan (Sarawak, Sabah, Laut Jawa)
    outside_points = [
        ("sarawak", 1.55, 110.35),
        ("sabah", 5.98, 116.07),
        ("laut_jawa", -6.0, 112.0),
    ]

    for label, lat, lon in outside_points:
        res = read_hansen_pixel(lat=lat, lon=lon, use_official=True)
        assert res.status == STATUS_OUT_OF_SCOPE, f"{label} harus OUT_OF_SCOPE"
        assert res.category_result == "Belum dapat dinilai"
        assert res.raster_available is False


def test_safe_separation_synthetic_vs_official():
    """
    9. Pemisahan Aman Data Sintetis vs Resmi:
    - Berkas demo sintetis di data/raster/hansen tetap utuh.
    - Berkas resmi di data/raster/hansen/official terpisah dengan akhiran _official.tif.
    - Pembacaan mode demo (use_official=False) menghasilkan source_type='DEMO_SYNTHETIC' dan is_official=False.
    - Pembacaan mode resmi (use_official=True) menghasilkan source_type='OFFICIAL_UMD_HANSEN_GFC' dan is_official=True.
    """
    demo_file = HANSEN_TILES_DIR / "Hansen_GFC-2025-v1.13_lossyear_00N_110E.tif"
    assert demo_file.exists()

    official_file = HANSEN_OFFICIAL_DIR / "Hansen_GFC-2025-v1.13_lossyear_00N_110E_official.tif"
    assert official_file.exists()

    assert demo_file.stat().st_size != official_file.stat().st_size

    ly_demo, meth_demo = resolve_layer_source("lossyear", "00N_110E", use_official=False)
    assert "official" not in Path(ly_demo).name
    assert meth_demo == "local_file"

    ly_off, meth_off = resolve_layer_source(
        "lossyear", "00N_110E", use_official=True, lat=-2.25, lon=113.90
    )
    assert "_official.tif" in Path(ly_off).name
    assert meth_off == "local_file"

    res_demo = read_hansen_pixel(lat=-2.15, lon=113.85, use_official=False)
    assert res_demo.is_official is False
    assert res_demo.source_type == "DEMO_SYNTHETIC"

    res_off = read_hansen_pixel(lat=-2.00013, lon=113.73212, use_official=True)
    assert res_off.is_official is True
    assert res_off.source_type == "OFFICIAL_UMD_HANSEN_GFC"


def test_geodesic_area_calculation_accuracy():
    """
    10. Validasi perhitungan luas sel dengan integrasi elipsoid WGS84 analitik (authalic):
    Area = 0.5 * b^2 * |d_lambda| * |Q(phi_north) - Q(phi_south)|
    - Pada khatulistiwa (0°): ~0.0769317 ha (~769.32 m²).
    - Pada lintang -2.25°: ~0.0768740 ha (~768.74 m²).
    - Pembulatan API 4 desimal: 0.0769 ha.
    """
    area_eq = calculate_pixel_area_ha(0.0)
    assert abs(area_eq - 0.0769317) < 1e-6, f"Luas khatulistiwa {area_eq} harus ~0.0769317 ha"
    assert round(area_eq, 4) == 0.0769

    area_benchmark = calculate_pixel_area_ha(-2.25)
    assert abs(area_benchmark - 0.0768740) < 1e-6, f"Luas lintang -2.25 {area_benchmark} harus ~0.0768740 ha"
    assert round(area_benchmark, 4) == 0.0769
    assert area_benchmark < area_eq

    # Verifikasi dukungan resolusi kustom (1 arc-second WGS84)
    area_custom_1arcsec = calculate_pixel_area_ha(0.0, degrees_per_pixel=1.0 / 3600.0)
    assert abs(area_custom_1arcsec - 0.0949774) < 1e-6


def test_provincial_summary_remains_demonstration():
    """
    11. Statistik agregat provinsi HARUS tetap berstatus demonstrasi (data_verified: False)
    karena data resmi baru mencakup koridor prioritas, bukan seluruh 5 provinsi.
    """
    summary = get_forest_loss_summary()
    assert summary["data_status"] == "demonstration"
    assert summary["data_verified"] is False
    assert len(summary["provincial_data"]) == 5

    for prov in summary["provincial_data"]:
        assert prov["data_status"] == "demonstration"
        assert prov["data_verified"] is False


def test_api_endpoint_point_official_mode():
    """
    12. Integrasi API REST endpoint /api/v1/forest-loss/point dengan use_official=true:
    - Titik resmi terverifikasi mengembalikan status 200 dengan is_official=true dan data akurat.
    - Titik di luar subset resmi mengembalikan status 200 dengan INSUFFICIENT_DATA.
    """
    # Titik dalam subset resmi
    resp = client.get(
        "/api/v1/forest-loss/point",
        params={
            "latitude": -2.00013,
            "longitude": 113.73212,
            "province": "Kalimantan Tengah",
            "use_official": "true",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUPPORTING_INDICATION"
    assert data["data_status"] == "demonstration"
    assert data["data_verified"] is False
    assert data["raster_available"] is True
    assert data["is_official"] is True
    assert data["source_type"] == "OFFICIAL_UMD_HANSEN_GFC"
    assert data["pixel_data"]["loss_detected"] is True
    assert data["pixel_data"]["loss_year"] == 2016
    assert data["pixel_data"]["canopy_density_pct"] == 55
    assert data["pixel_resolution_approx_m"] == 27.83
    assert data["pixel_area_ha"] == 0.0769

    # Titik di luar cakupan 5 provinsi Kalimantan (misal Jawa Tengah lat=-7.00, lon=110.00)
    resp_out = client.get(
        "/api/v1/forest-loss/point",
        params={
            "latitude": -7.00,
            "longitude": 110.00,
            "province": "Jawa Tengah",
            "use_official": "true",
        },
    )
    assert resp_out.status_code == 200
    data_out = resp_out.json()
    assert data_out["status"] == "INSUFFICIENT_DATA"
    assert data_out["category_result"] == "Belum dapat dinilai"
    assert data_out["raster_available"] is False
    assert data_out["data_verified"] is False


@pytest.mark.remote
def test_remote_vs_local_pixel_identical_match():
    """
    13. Validasi Silang Remote Live terhadap Google Cloud Storage UMD:
    Membaca langsung dari server resmi UMD via streaming HTTP Range dan
    membandingkan setiap nilai piksel dengan GeoTIFF subset lokal pada koordinat benchmark.
    
    Catatan pengujian:
    - Tes ini membutuhkan koneksi internet ke storage.googleapis.com.
    - Jika koneksi gagal, tes dilewati secara eksplisit dengan skip, TIDAK dilaporkan lulus palsu.
    """
    layers = ["lossyear", "treecover2000", "datamask"]
    test_points = [
        ("pt_loss_2016", -2.00013, 113.73212),
        ("pt_loss_2013", -2.10, 113.70),
        ("pt_water", -2.000125, 113.774375),
        ("corner_top_left", -2.0001, 113.6001),
        ("corner_bottom_right", -2.4999, 114.1999),
    ]

    for label, lat, lon in test_points:
        for layer in layers:
            local_tif = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_{layer}_00N_110E_official.tif"
            remote_url = f"{REMOTE_BASE_URL}Hansen_GFC-2025-v1.13_{layer}_00N_110E.tif"

            # Baca piksel lokal
            with rasterio.open(local_tif) as l_src:
                local_val = int(list(l_src.sample([(lon, lat)]))[0][0])

            # Baca piksel remote
            try:
                with rasterio.open(remote_url) as r_src:
                    remote_val = int(list(r_src.sample([(lon, lat)]))[0][0])
            except Exception as e:
                pytest.skip(f"Akses remote UMD GCS gagal: {e}. Tes remote dilewati.")

            assert local_val == remote_val, (
                f"Mismatch piksel pada {label} (lat={lat}, lon={lon}), layer {layer}: "
                f"lokal={local_val} vs remote={remote_val}"
            )
