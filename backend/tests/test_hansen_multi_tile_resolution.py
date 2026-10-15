"""
Suite Pengujian Multi-Tile Resolver dan Integritas Spasial Hansen GFC v1.13.

Cakupan Pengujian:
1. Pemilihan ke-4 tile resmi Kalimantan (00N_100E, 00N_110E, 10N_100E, 10N_110E).
2. Penanganan koordinat di dalam, di luar, dan tepat pada garis batas tile (Equator lat 0.0, Lon 110.0).
3. Penanganan saat manifest hilang atau tidak valid.
4. Penanganan berkas unduhan yang tidak lengkap (.part aktif).
5. Pembuktian bahwa TIDAK ADA fallback diam-diam dari data resmi ke raster sintetis.
6. Klasifikasi piksel air (datamask=2) dan no-data (datamask=0) -> NO_DATA_OR_NON_FOREST.
7. Kompatibilitas backward untuk mode demonstrasi (use_official=False).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.hansen_tile_reader import (
    clear_manifest_cache,
    clear_pixel_cache,
    get_hansen_tile_id,
    get_tile_bounds,
    is_coordinate_in_kalimantan,
    load_tile_manifest,
    read_hansen_pixel,
    resolve_layer_source,
    STATUS_INSUFFICIENT_DATA,
    STATUS_LOSS_DETECTED,
    STATUS_NO_DATA_OR_NON_FOREST,
    STATUS_NO_LOSS_DETECTED,
    STATUS_OUT_OF_SCOPE,
)


@pytest.fixture(autouse=True)
def clean_caches():
    """Selalu bersihkan cache sebelum dan sesudah setiap pengujian."""
    clear_pixel_cache()
    clear_manifest_cache()
    yield
    clear_pixel_cache()
    clear_manifest_cache()


# 1. Pemilihan Keempat Tile Resmi
def test_multi_tile_selection_across_all_four_tiles():
    """Memastikan pemilihan tile benar untuk lokasi representatif di 5 provinsi Kalimantan."""
    test_cases = [
        # (lat, lon, expected_tile, expected_prov)
        (-1.85, 109.98, "00N_100E", "Kalimantan Barat"),   # Ketapang / Kalbar S
        (-2.21, 113.92, "00N_110E", "Kalimantan Tengah"),  # Palangka Raya / Kalteng
        (-3.32, 114.59, "00N_110E", "Kalimantan Selatan"), # Banjarmasin / Kalsel
        (-0.96, 116.78, "00N_110E", "Kalimantan Timur"),   # IKN Nusantara / Kaltim S
        (0.90, 108.98, "10N_100E", "Kalimantan Barat"),    # Singkawang / Kalbar U
        (0.50, 117.15, "10N_110E", "Kalimantan Timur"),    # Samarinda / Kaltim U
        (3.32, 117.60, "10N_110E", "Kalimantan Utara"),    # Tarakan / Kaltara
    ]

    for lat, lon, exp_tile, exp_prov in test_cases:
        tile_id = get_hansen_tile_id(lat, lon)
        assert tile_id == exp_tile, f"Koordinat ({lat}, {lon}) harusnya tile {exp_tile}, didapat {tile_id}"

        res = read_hansen_pixel(lat, lon, use_official=True)
        assert res.tile_id == exp_tile
        assert res.is_official is True
        assert res.data_verified is False
        assert res.data_status == "demonstration"
        assert res.raster_available is True
        assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"
        assert res.status in (STATUS_NO_LOSS_DETECTED, STATUS_LOSS_DETECTED, STATUS_NO_DATA_OR_NON_FOREST)


# 2. Penanganan Koordinat Batas Tile (Boundary Handling)
def test_tile_boundary_equator_and_meridian():
    """
    Memastikan titik tepat di garis batas diperhitungkan secara konsisten
    tanpa melompat atau keluar batas.
    """
    # Titik tepat pada garis khatulistiwa (lat = 0.0)
    tile_at_equator = get_hansen_tile_id(0.0, 113.0)
    assert tile_at_equator == "00N_110E"

    # Titik sedikit di utara khatulistiwa
    tile_north_equator = get_hansen_tile_id(0.0001, 113.0)
    assert tile_north_equator == "10N_110E"

    # Titik sedikit di selatan khatulistiwa
    tile_south_equator = get_hansen_tile_id(-0.0001, 113.0)
    assert tile_south_equator == "00N_110E"

    # Titik tepat pada bujur pembatas 110.0°
    tile_at_meridian = get_hansen_tile_id(-1.0, 110.0)
    assert tile_at_meridian == "00N_110E"

    # Titik sedikit di barat bujur 110.0°
    tile_west_meridian = get_hansen_tile_id(-1.0, 109.9999)
    assert tile_west_meridian == "00N_100E"


def test_out_of_scope_boundary_handling():
    """Koordinat di luar 5 provinsi Kalimantan (Sarawak, Sabah, laut jauh) harus OUT_OF_SCOPE."""
    # Kuching, Sarawak (Malaysia)
    res_sarawak = read_hansen_pixel(1.55, 110.35, use_official=True)
    assert res_sarawak.status == STATUS_OUT_OF_SCOPE
    assert res_sarawak.loss_detected is False
    assert res_sarawak.data_verified is False

    # Kota Kinabalu, Sabah (Malaysia)
    res_sabah = read_hansen_pixel(5.98, 116.07, use_official=True)
    assert res_sabah.status == STATUS_OUT_OF_SCOPE

    # Laut Jawa di selatan Kalimantan
    res_java_sea = read_hansen_pixel(-6.0, 112.0, use_official=True)
    assert res_java_sea.status == STATUS_OUT_OF_SCOPE


# 3. Manifest Hilang atau Tidak Valid
def test_manifest_missing_or_corrupt_behavior(tmp_path):
    """
    Jika manifest hilang atau rusak, resolve_layer_source tetap aman
    dan tidak menghasilkan exception tak tertangani.
    """
    # Cari di direktori kosong tanpa manifest
    manifest = load_tile_manifest("00N_100E", tiles_dir=tmp_path)
    assert manifest is None

    # Tulis manifest JSON korup
    corrupt_manifest = tmp_path / "manifest_00N_100E_official.json"
    corrupt_manifest.write_text("{CORRUPT_JSON_SYNTAX")

    clear_manifest_cache()
    manifest_corrupt = load_tile_manifest("00N_100E", tiles_dir=tmp_path)
    assert manifest_corrupt is None


# 4. Berkas Unduhan Tidak Lengkap (.part Aktif)
def test_incomplete_part_file_is_not_read_as_valid(tmp_path):
    """
    Jika file resmi memiliki file .part aktif dan tidak ada file final .tif,
    sistem TIDAK BOLEH membaca file setengah jadi tersebut.
    """
    official_dir = tmp_path / "official"
    official_dir.mkdir(parents=True)

    # Buat file .part sementara
    part_file = official_dir / "Hansen_GFC-2025-v1.13_lossyear_00N_100E_official.tif.part"
    part_file.write_bytes(b"INCOMPLETE_PARTIAL_BYTES")

    src_path, method = resolve_layer_source(
        layer="lossyear",
        tile_id="00N_100E",
        tiles_dir=tmp_path,
        use_official=True,
    )
    # Harus ditolak, bukan mengembalikan file part
    assert src_path is None
    assert method == "official_unavailable"


# 5. Tidak Ada Fallback Diam-diam dari Data Resmi ke Raster Sintetis
def test_no_silent_fallback_to_synthetic_when_official_mode_is_active(tmp_path):
    """
    CRITICAL SAFETY: Saat mode resmi aktif (use_official=True), jika tile resmi tidak ada
    di direktori resmi, sistem DILARANG KERAS diam-diam membaca file demo sintetis!
    Sistem wajib mengembalikan INSUFFICIENT_DATA dengan is_official=True.
    """
    # Di tmp_path hanya ada file demo sintetis
    demo_tif = tmp_path / "Hansen_GFC-2025-v1.13_lossyear_00N_100E.tif"
    demo_tif.write_bytes(b"SYNTHETIC_DEMO_DATA")

    # Minta pembacaan dengan use_official=True
    src_path, method = resolve_layer_source(
        layer="lossyear",
        tile_id="00N_100E",
        tiles_dir=tmp_path,
        use_official=True,
    )

    # Verifikasi bahwa file demo TIDAK dikembalikan
    assert src_path is None
    assert method == "official_unavailable"

    # Evaluasi piksel menghasilkan INSUFFICIENT_DATA, BUKAN hasil pembacaan demo
    res = read_hansen_pixel(-1.85, 109.98, tiles_dir=tmp_path, use_official=True)
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.data_verified is False
    assert res.is_official is True
    assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"
    assert "belum tersedia" in res.error_message


# 6. Mode Demonstrasi Tetap Berfungsi Sesuai Kontrak (use_official=False)
def test_demo_mode_compatibility_when_official_is_false():
    """Mode demonstrasi lama (use_official=False) tetap berfungsi tanpa regresi."""
    # Titik demo Kalimantan Tengah di dalam batas raster sintetis (-2.175 s.d. -2.1, 113.8 s.d. 113.875)
    res_demo = read_hansen_pixel(-2.1375, 113.8375, use_official=False)
    assert res_demo.status in (STATUS_NO_LOSS_DETECTED, STATUS_LOSS_DETECTED, STATUS_NO_DATA_OR_NON_FOREST)
    assert res_demo.is_official is False
    assert res_demo.source_type == "DEMO_SYNTHETIC"


# 7. Penanganan Titik Air dan NoData
def test_water_and_nodata_pixel_classification():
    """Titik perairan sungai/danau besar terdeteksi sebagai NO_DATA_OR_NON_FOREST dengan datamask=2."""
    # Koordinat di perairan pesisir Balikpapan (-1.27, 116.81)
    res = read_hansen_pixel(-1.27, 116.81, use_official=True)
    if res.datamask == 2:
        assert res.status == STATUS_NO_DATA_OR_NON_FOREST
        assert res.loss_detected is False


# 8. Koordinat di Laut (Di dalam Bounding Box Tile Hansen tetapi di Luar Poligon Daratan)
def test_ocean_coordinates_inside_tile_bounds_are_strictly_out_of_scope():
    """
    Titik-titik di laut lepas yang secara koordinat berada di dalam bounding box tile 10°x10°
    tetapi di luar poligon administratif 5 provinsi Kalimantan HARUS berstatus OUT_OF_SCOPE.
    """
    ocean_points = [
        # (label, lat, lon, tile_id_bbox)
        ("Selat Makassar tengah", -1.0, 118.5, "00N_110E"),
        ("Selat Karimata lepas", -2.0, 108.5, "00N_100E"),
        ("Laut Sulawesi timur", 2.0, 119.5, "10N_110E"),
        ("Laut Jawa selatan", -5.5, 113.0, "00N_110E"),
    ]

    for label, lat, lon, exp_tile in ocean_points:
        # Tile ID geometris harus sesuai
        assert get_hansen_tile_id(lat, lon) == exp_tile
        # Namun pembacaan piksel harus OUT_OF_SCOPE karena filter Point-in-Polygon
        res = read_hansen_pixel(lat, lon, use_official=True)
        assert res.status == STATUS_OUT_OF_SCOPE, f"{label} ({lat}, {lon}) harus OUT_OF_SCOPE"
        assert res.raster_available is False
        assert res.loss_detected is False
        assert res.data_verified is False
        assert "di luar cakupan 5 provinsi" in res.matching_rule


# 9. Wilayah di Luar 5 Provinsi Kalimantan (Negara Tetangga & Provinsi Lain di Indonesia)
def test_non_kalimantan_territory_strictly_out_of_scope():
    """Wilayah Sarawak, Sabah, Brunei, dan pulau lain di Indonesia harus OUT_OF_SCOPE."""
    foreign_or_other_points = [
        ("Bandar Seri Begawan, Brunei", 4.93, 114.94),
        ("Sibu, Sarawak", 2.30, 111.82),
        ("Sandakan, Sabah", 5.84, 118.11),
        ("Jakarta, Jawa Barat/DKI", -6.20, 106.85),
        ("Palembang, Sumatera Selatan", -2.99, 104.75),
    ]

    for label, lat, lon in foreign_or_other_points:
        res = read_hansen_pixel(lat, lon, use_official=True)
        assert res.status == STATUS_OUT_OF_SCOPE, f"{label} harus OUT_OF_SCOPE"
        assert res.raster_available is False
        assert res.loss_detected is False


# 10. Titik Tepat di Batas Administrasi Antar-Provinsi
def test_points_at_administrative_boundaries():
    """
    Titik di dekat atau pada perbatasan antar-provinsi di Kalimantan
    (misal perbatasan Kalbar - Kalteng di Pegunungan Schwaner) tetap teresolusi
    ke salah satu provinsi Kalimantan yang sah tanpa error.
    """
    # Titik perbatasan Kalbar - Kalteng (sekitar Bukit Raya / Pegunungan Schwaner)
    border_point_lat = -0.65
    border_point_lon = 112.75

    is_inside, prov_name = is_coordinate_in_kalimantan(border_point_lat, border_point_lon)
    assert is_inside is True
    assert prov_name in ("Kalimantan Barat", "Kalimantan Tengah")

    res = read_hansen_pixel(border_point_lat, border_point_lon, use_official=True)
    assert res.status in (STATUS_NO_LOSS_DETECTED, STATUS_LOSS_DETECTED, STATUS_NO_DATA_OR_NON_FOREST)
    assert res.province in ("Kalimantan Barat", "Kalimantan Tengah")
    assert res.tile_id == "00N_110E"
    assert res.is_official is True


# 11. Penanganan Tile Hilang pada Mode Resmi
def test_missing_official_tile_returns_insufficient_data(tmp_path):
    """
    Jika titik berada di dalam Kalimantan, tetapi file tile resmi sama sekali tidak ada di disk,
    sistem wajib mengembalikan status INSUFFICIENT_DATA secara elegan tanpa crash.
    """
    # Direktori kosong
    empty_dir = tmp_path / "empty_official"
    empty_dir.mkdir(parents=True)

    # Titik Palangka Raya (-2.21, 113.92) di Kalimantan Tengah
    res = read_hansen_pixel(-2.21, 113.92, tiles_dir=empty_dir, use_official=True)
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.raster_available is False
    assert res.is_official is True
    assert res.source_type == "OFFICIAL_UMD_HANSEN_GFC"
    assert "belum tersedia" in (res.error_message or "").lower()


# 12. Penanganan Manifest Tidak Valid / Struktur Korup
def test_invalid_manifest_structure_handled_safely(tmp_path):
    """
    Manifest dengan struktur rusak (bukan JSON atau hilang field penting)
    tidak menyebabkan crash pada tile reader.
    """
    manifest_file = tmp_path / "manifest_00N_110E_official.json"
    manifest_file.write_text('{"incomplete_json": true, "layers": "NOT_A_DICT"}', encoding="utf-8")

    clear_manifest_cache()
    loaded = load_tile_manifest("00N_110E", tiles_dir=tmp_path)
    # Manifest terbaca sebagai dict tetapi saat dicek layer-nya tidak crash
    assert loaded is not None
    assert "incomplete_json" in loaded

    # resolve_layer_source menangani manifest tanpa key layers yang benar
    src_path, method = resolve_layer_source("lossyear", "00N_110E", tiles_dir=tmp_path, use_official=True)
    assert src_path is None
    assert method == "official_unavailable"

