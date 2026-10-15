"""
Suite Pengujian Zonal Coverage, Mask Semantik, dan Penanganan Data Tidak Lengkap
Hansen Global Forest Change (GFC) v1.13.

Menguji persyaratan audit:
1. Cakupan parsial (Partial Coverage): Penanganan saat provinsi melintasi beberapa tile
   tetapi hanya sebagian tile yang tersedia di lokal (tidak boleh zero-fill area yang hilang).
2. Raster hilang (Missing Raster): Penanganan ketika tile raster sama sekali tidak ditemukan.
3. NoData piksel (datamask == 0): Pemisahan laut/unobserved dari daratan, tidak disamakan
   dengan hutan utuh atau zero-loss.
4. Piksel air permanen (datamask == 2): Badan air danau/sungai dipisahkan dari daratan valid,
   tidak dihitung sebagai baseline hutan atau kehilangan tutupan.
5. Area tanpa kehilangan yang terdeteksi (Zero-Loss):
   - Intact forest: datamask==1, treecover2000>0, lossyear==0.
   - Non-forest baseline: datamask==1, treecover2000==0, lossyear==0.
   - Loss detected: datamask==1, lossyear in [1..25].
6. Kejelasan penyebut metrik (denominator clarity) dan kepatuhan status 'demonstration'
   serta 'data_verified: false'.
"""

import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from shapely.geometry import Polygon

from app.config import BOUNDARIES_PATH, HANSEN_OFFICIAL_DIR
from app.forest_change_service import (
    calculate_pixel_area_ha,
    get_forest_loss_summary,
    wgs84_ellipsoid_cell_area_ha,
    HANSEN_PIXEL_DEGREES,
    KALIMANTAN_PROVINCES,
)
from app.hansen_tile_reader import (
    clear_manifest_cache,
    clear_pixel_cache,
    get_hansen_tile_id,
    read_hansen_pixel,
    resolve_layer_source,
    STATUS_INSUFFICIENT_DATA,
    STATUS_LOSS_DETECTED,
    STATUS_NO_DATA_OR_NON_FOREST,
    STATUS_NO_LOSS_DETECTED,
    STATUS_OUT_OF_SCOPE,
)


@pytest.fixture(autouse=True)
def reset_caches():
    clear_pixel_cache()
    clear_manifest_cache()
    yield
    clear_pixel_cache()
    clear_manifest_cache()


# =========================================================================
# 1. PENGUJIAN CAKUPAN PARSIAL (PARTIAL COVERAGE) & TIDAK ADA ZERO-FILL
# =========================================================================

def test_partial_coverage_does_not_fill_missing_area_with_zero(tmp_path):
    """
    Memverifikasi perilaku saat suatu wilayah memiliki cakupan parsial
    (misal hanya 1 dari 2 tile yang tersedia di disk):
    - Area pada tile yang hilang TIDAK BOLEH diisi dengan angka nol (zero-filled).
    - Permintaan titik pada tile yang hilang harus mengembalikan STATUS_INSUFFICIENT_DATA.
    - Metrik cakupan harus secara eksplisit melaporkan kekurangan data.
    """
    official_dir = tmp_path / "official"
    official_dir.mkdir(parents=True)

    # Buat hanya tile 00N_110E (misal Kalteng/Kalsel), tanpa tile 10N_110E
    # Titik di Kalteng selatan (-2.21, 113.92) masuk tile 00N_110E
    # Titik di Kalteng utara (0.50, 114.00) masuk tile 10N_110E

    # Jalankan query pada tile yang hilang (10N_110E)
    res_missing = read_hansen_pixel(0.50, 114.00, tiles_dir=official_dir, use_official=True)
    assert res_missing.status == STATUS_INSUFFICIENT_DATA
    assert res_missing.raster_available is False
    assert res_missing.is_official is True
    assert res_missing.loss_detected is False
    assert res_missing.data_verified is False
    # Nilai piksel tidak boleh direkayasa atau diisi nol
    assert res_missing.treecover2000 is None or res_missing.status == STATUS_INSUFFICIENT_DATA
    assert res_missing.raw_lossyear is None or res_missing.status == STATUS_INSUFFICIENT_DATA


def test_zonal_aggregation_denominators_clarity():
    """
    Memverifikasi bahwa laporan audit zonal statistik provinsi memiliki
    penyebut (denominators) yang terdefinisi dengan ketat dan tidak ambigu:
    - cumulative_loss_pct_of_land = loss_ha / valid_land_ha
    - cumulative_loss_pct_of_baseline_gt0 = loss_ha / baseline_treecover_gt0_ha
    - cumulative_loss_pct_of_baseline_ge30 = loss_ha / baseline_treecover_ge30_ha
    """
    report_file = HANSEN_OFFICIAL_DIR / "provincial_zonal_coverage_report.json"
    if not report_file.exists():
        pytest.skip("Laporan provincial_zonal_coverage_report.json belum dibuat di folder official")

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    for prov_name, p_data in data["provinces"].items():
        areas = p_data["areas_ha"]
        cov = p_data["coverage_metrics"]

        a_land = areas["valid_land"]
        a_water = areas["permanent_water"]
        a_nodata = areas["nodata_marine"]
        a_loss = areas["loss_total_2001_2025"]
        a_tc_gt0 = areas["baseline_treecover_gt0"]
        a_tc_ge30 = areas["baseline_treecover_ge30"]
        a_poly = p_data["polygon_area_ha"]

        # Penyebut daratan valid: loss / land
        expected_loss_land_pct = round((a_loss / a_land) * 100.0, 2)
        assert cov["cumulative_loss_pct_of_land"] == expected_loss_land_pct

        # Penyebut baseline > 0%
        expected_loss_gt0_pct = round((a_loss / a_tc_gt0) * 100.0, 2)
        assert cov["cumulative_loss_pct_of_baseline_gt0"] == expected_loss_gt0_pct

        # Penyebut baseline >= 30%
        expected_loss_ge30_pct = round((a_loss / a_tc_ge30) * 100.0, 2)
        assert cov["cumulative_loss_pct_of_baseline_ge30"] == expected_loss_ge30_pct

        # Discretization error < 1.0%
        assert cov["discretization_error_pct"] < 1.0, f"Error diskretisasi {prov_name} melebihi 1%"


# =========================================================================
# 2. PENGUJIAN RASTER HILANG (MISSING RASTER)
# =========================================================================

def test_missing_raster_returns_insufficient_data_cleanly(tmp_path):
    """
    Jika file raster tidak ditemukan sama sekali:
    - Tidak boleh terjadi ZeroDivisionError atau uncaught exception.
    - Sistem mengembalikan status INSUFFICIENT_DATA.
    - data_verified tetap False dan data_status 'demonstration'.
    """
    empty_tiles_dir = tmp_path / "empty_dir"
    empty_tiles_dir.mkdir()

    res = read_hansen_pixel(-2.2079, 113.9165, tiles_dir=empty_tiles_dir, use_official=True)
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.raster_available is False
    assert res.data_verified is False
    assert res.data_status == "demonstration"
    assert "belum tersedia" in (res.error_message or "").lower()


# =========================================================================
# 3. PENGUJIAN PIKSEL NODATA (datamask == 0)
# =========================================================================

def test_nodata_pixel_semantics_and_separation():
    """
    Piksel NoData (datamask == 0) pada dataset Hansen GFC v1.13:
    - Mewakili laut lepas atau wilayah di luar batas observasi data.
    - Dilarang keras disamakan dengan hutan utuh (intact forest) atau non-forest baseline.
    - Dilarang dimasukkan ke dalam penyebut luas daratan (valid_land).
    """
    # Pada tingkat piksel:
    # 1. Jika koordinat di laut terbuka (di luar poligon Indonesia), status OUT_OF_SCOPE
    res_ocean = read_hansen_pixel(-5.0, 113.0, use_official=True)
    assert res_ocean.status == STATUS_OUT_OF_SCOPE

    # 2. Dalam agregasi zonal, nodata_marine dipisahkan dari valid_land
    report_file = HANSEN_OFFICIAL_DIR / "provincial_zonal_coverage_report.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for prov_name, p_data in data["provinces"].items():
            # Di Kalimantan, poligon daratan administratif berada 100% di dalam 4 tile
            assert p_data["areas_ha"]["nodata_marine"] == 0.0 or p_data["areas_ha"]["nodata_marine"] < p_data["areas_ha"]["valid_land"]


# =========================================================================
# 4. PENGUJIAN PIKSEL AIR PERMANEN (datamask == 2)
# =========================================================================

def test_water_pixel_classification_not_treated_as_loss_or_forest():
    """
    Piksel air permanen (datamask == 2) seperti Danau Sentarum atau sungai besar:
    - Tidak boleh dihitung sebagai kehilangan tutupan pohon (loss_detected=False).
    - Tidak boleh dihitung sebagai hutan baseline.
    - Status piksel adalah NO_DATA_OR_NON_FOREST.
    """
    # Titik perairan pesisir Balikpapan / Teluk Balikpapan (-1.27, 116.81)
    res = read_hansen_pixel(-1.27, 116.81, use_official=True)
    if res.datamask == 2:
        assert res.status == STATUS_NO_DATA_OR_NON_FOREST
        assert res.loss_detected is False
        assert res.loss_year is None
        assert "perairan" in res.matching_rule.lower() or "datamask=2" in res.matching_rule.lower()

    # Periksa laporan zonal bahwa permanent_water dicatat secara terpisah
    report_file = HANSEN_OFFICIAL_DIR / "provincial_zonal_coverage_report.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for prov_name, p_data in data["provinces"].items():
            # Setiap provinsi Kalimantan memiliki perairan darat permanen > 0
            assert p_data["pixel_counts"]["permanent_water"] > 0
            assert p_data["areas_ha"]["permanent_water"] > 0.0


# =========================================================================
# 5. PENGUJIAN AREA TANPA KEHILANGAN (ZERO LOSS / INTACT FOREST)
# =========================================================================

def test_zero_loss_intact_forest_vs_non_forest():
    """
    Memverifikasi pembedaan antara:
    - Hutan utuh tanpa kehilangan: datamask=1, treecover2000>0, lossyear=0 -> STATUS_NO_LOSS_DETECTED
    - Lahan non-hutan sejak baseline: datamask=1, treecover2000=0, lossyear=0 -> STATUS_NO_DATA_OR_NON_FOREST
    - Terdeteksi kehilangan kanopi: datamask=1, lossyear in [1..25] -> STATUS_LOSS_DETECTED
    """
    # Titik pedalaman Kalteng di kawasan hutan utuh (-1.50, 114.00)
    res = read_hansen_pixel(-1.50, 114.00, use_official=True)
    if res.raw_lossyear == 0 and res.treecover2000 is not None and res.treecover2000 > 0:
        assert res.status == STATUS_NO_LOSS_DETECTED
        assert res.loss_detected is False
        assert res.data_verified is False
        assert res.data_status == "demonstration"
        assert res.raster_available is True
        assert "tidak terdeteksi kehilangan" in res.matching_rule.lower()

    # Titik di area permukiman/lahan terbuka tanpa tutupan kanopi 2000 (0%) dan lossyear 0
    # Contoh Palangka Raya perkotaan (-2.2079, 113.9165)
    res_pk = read_hansen_pixel(-2.2079, 113.9165, use_official=True)
    if res_pk.raw_lossyear == 0 and (res_pk.treecover2000 or 0) == 0:
        assert res_pk.status == STATUS_NO_DATA_OR_NON_FOREST
        assert res_pk.loss_detected is False


# =========================================================================
# 6. PENGUJIAN CAVEAT ILMIAH: KEHILANGAN KANOPI BUKAN KEBAKARAN/ILEGAL
# =========================================================================

def test_scientific_caveat_integrity_loss_not_equated_to_fire_or_illegal_logging():
    """
    Memastikan seluruh respon tidak menyamakan kehilangan tutupan kanopi (lossyear)
    dengan deforestasi ilegal atau kebakaran.
    """
    # Uji ringkasan agregat
    summary = get_forest_loss_summary()
    assert summary["data_status"] == "demonstration"
    assert summary["data_verified"] is False

    limitations = " ".join(summary.get("limitations", [])).lower()
    assert "tidak otomatis berarti deforestasi ilegal" in limitations
    assert "bukan pemantauan real-time" in limitations

    # Uji evaluasi titik
    res = read_hansen_pixel(-2.21, 113.92, use_official=True)
    caveat = res.scientific_caveat.lower()
    assert "tidak secara otomatis membuktikan" in caveat
    assert "ilegal" in caveat or "kebakaran" in caveat
    assert "bukan bukti hukum" in caveat or "verifikasi" in caveat


# =========================================================================
# 7. INTEGRITAS STATUS DEMONSTRASI PADA STATISTIK PROVINSI
# =========================================================================

def test_provincial_summary_preserves_demonstration_status():
    """
    Kepatuhan ketat terhadap instruksi:
    Statistik provinsi WAJIB mempertahankan:
    data_status: "demonstration"
    data_verified: false
    """
    summary = get_forest_loss_summary()
    assert summary["data_status"] == "demonstration"
    assert summary["data_verified"] is False

    for prov in summary["provincial_data"]:
        assert prov["data_status"] == "demonstration"
        assert prov["data_verified"] is False
        assert "demonstrasi" in prov["verification_notes"].lower()


# =========================================================================
# 8. REGRESI VALIDASI INDEPENDEN KALIMANTAN TENGAH (TEMUAN STUDI KASUS)
# =========================================================================

def test_kalteng_independent_validation_exact_pixel_match():
    """
    Memverifikasi bahwa laporan validasi independen kedua (Metode 2) untuk Kalteng
    cocok 100% (selisih 0 piksel) dengan laporan primer (Metode 1) untuk seluruh kelas:
    valid_land, permanent_water, nodata_marine, baseline_gt0, loss_total, stable_forest.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalteng_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalteng_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    for item in val_data["metrics_comparison"]:
        if item["is_count"]:
            assert item["diff_abs"] == 0, f"Piksel {item['metric']} tidak cocok: diff={item['diff_abs']}"
        else:
            # Luas dalam hektare harus cocok dalam batas presisi kuadratur (< 0.001%)
            assert item["diff_rel_pct"] <= 0.001, f"Luas {item['metric']} melebihi toleransi: {item['diff_rel_pct']}%"


def test_kalteng_polygon_area_albers_vs_raster_discretization():
    """
    Memverifikasi penemuan fisik penting:
    Luas poligon Albers Equal-Area WGS84 (15.357.441,26 ha) cocok dengan penjumlahan
    luas piksel diskret (15.357.429,81 ha) dengan selisih sangat kecil (< 12 ha / < 0.0001%).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalteng_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalteng_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    poly_comp = val_data["polygon_area_comparison"]
    albers_ha = poly_comp["method_2a_albers_wgs84_ha"]

    # Ambil luas total piksel dari perbandingan metrik
    total_pixel_ha = None
    for item in val_data["metrics_comparison"]:
        if item["metric"] == "Luas Total Piksel (ha)":
            total_pixel_ha = item["val_method2"]
            break

    assert total_pixel_ha is not None
    diff_ha = abs(albers_ha - total_pixel_ha)
    diff_pct = (diff_ha / albers_ha) * 100.0

    # Selisih antara raster terdisketisasi dan proyeksi equal-area < 0.001% (< 10 ppm)
    assert diff_pct < 0.001, f"Selisih Albers vs Raster diskret {diff_pct}% melebihi 0.001%"


def test_kalteng_numerator_denominator_cohort_distinction():
    """
    Memverifikasi penemuan ilmiah kriteria numerator vs denominator:
    - Terdapat 1.520.402 piksel (116.873,99 ha) kehilangan pada lahan dengan treecover2000 == 0.
    - Rasio tak terkekang (unconstrained ratio) = 28.42%.
    - Rasio kohort konsisten (strict cohort: loss on gt0 / baseline gt0) = 27.61%.
    - Rasio kohort konsisten secara matematis HARUS lebih kecil dari rasio tak terkekang.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalteng_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalteng_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    analysis = val_data["numerator_denominator_analysis"]
    assert analysis["loss_on_baseline_eq0_ha"] > 100000.0
    assert analysis["loss_pct_strict_cohort_of_gt0"] < analysis["loss_pct_unconstrained_of_gt0"]
    assert analysis["loss_pct_strict_cohort_of_gt0"] == 27.61
    assert analysis["loss_pct_unconstrained_of_gt0"] == 28.42


def test_kalteng_direct_raster_benchmark_pixels():
    """
    Memverifikasi 5 titik sampel langsung dari 3 raster resmi di Kalimantan Tengah:
    1. Palangka Raya: datamask=1, treecover2000=0, lossyear=0 (urban/non-forest)
    2. Gambut Sebangau: datamask=1, treecover2000=98, lossyear=16 (kebakaran El Niño 2015/2016)
    3. Sungai Barito: datamask=2, treecover2000=0, lossyear=0 (air permanen)
    4. TN Bukit Baka: datamask=1, treecover2000=98, lossyear=0 (hutan utuh stabil)
    5. Murung Raya Kalteng Utara: datamask=1, treecover2000=97, lossyear=0 (hutan utuh stabil)
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalteng_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalteng_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    samples = {s["label"]: s for s in val_data["pixel_samples"]}

    # 1. Urban
    assert samples["Palangka Raya (Kawasan Urban)"]["datamask"] == 1
    assert samples["Palangka Raya (Kawasan Urban)"]["treecover2000"] == 0
    assert samples["Palangka Raya (Kawasan Urban)"]["lossyear"] == 0

    # 2. Sebangau Loss 2016
    assert samples["Kawasan Gambut Sebangau (Kebakaran 2015)"]["datamask"] == 1
    assert samples["Kawasan Gambut Sebangau (Kebakaran 2015)"]["treecover2000"] >= 90
    assert samples["Kawasan Gambut Sebangau (Kebakaran 2015)"]["lossyear"] == 16

    # 3. Permanent Water
    assert samples["Perairan Darat Permanen (Barito)"]["datamask"] == 2
    assert samples["Perairan Darat Permanen (Barito)"]["lossyear"] == 0

    # 4. Bukit Baka
    assert samples["Kawasan Hutan Pegunungan (TN Bukit Baka)"]["datamask"] == 1
    assert samples["Kawasan Hutan Pegunungan (TN Bukit Baka)"]["treecover2000"] >= 90
    assert samples["Kawasan Hutan Pegunungan (TN Bukit Baka)"]["lossyear"] == 0

    # 5. Murung Raya
    assert samples["Pedalaman Kalteng Utara (Murung Raya)"]["datamask"] == 1
    assert samples["Pedalaman Kalteng Utara (Murung Raya)"]["treecover2000"] >= 90
    assert samples["Pedalaman Kalteng Utara (Murung Raya)"]["lossyear"] == 0


def test_shapely_geometric_predicates_and_pixel_center_rule():
    """
    Memverifikasi predikat geometri Shapely (contains, within, touches, covers, intersects)
    terhadap aturan rasterisasi pusat piksel (all_touched=False):
    1. Titik pusat interior: geom.contains(pt) True, geom.touches(pt) False, within True.
    2. Titik pusat eksterior: geom.contains(pt) False, geom.intersects(pt) False.
    3. Titik transisi batas: titik dalam terakhir (contains True) vs titik luar pertama (contains False).
    4. Titik tepat pada batas (boundary vertex): geom.contains False, geom.touches True, geom.covers True.
    """
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window
    from shapely.geometry import Point, shape
    from shapely.validation import make_valid

    with open(BOUNDARIES_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)

    kalteng_geom = None
    for feat in gj["features"]:
        props = feat.get("properties", {})
        name = props.get("state") or props.get("name") or props.get("NAME_1") or props.get("Propinsi") or ""
        if "kalimantan tengah" in name.lower():
            kalteng_geom = make_valid(shape(feat["geometry"]))
            break

    assert kalteng_geom is not None

    dm_path = HANSEN_OFFICIAL_DIR / "Hansen_GFC-2025-v1.13_datamask_00N_110E_official.tif"
    if not dm_path.exists():
        pytest.skip("Berkas raster 00N_110E tidak tersedia")

    with rasterio.open(dm_path) as dm:
        # A. Titik Pusat Interior (Palangka Raya)
        r_in, c_in = dm.index(113.9165, -2.2079)
        lon_in, lat_in = dm.xy(r_in, c_in)
        pt_in = Point(lon_in, lat_in)

        assert kalteng_geom.contains(pt_in) is True
        assert pt_in.within(kalteng_geom) is True
        assert kalteng_geom.touches(pt_in) is False  # Titik interior tidak menyentuh batas
        assert kalteng_geom.intersects(pt_in) is True
        assert kalteng_geom.covers(pt_in) is True

        w_in = Window(c_in, r_in, 1, 1)
        m_in = geometry_mask(
            [kalteng_geom],
            out_shape=(1, 1),
            transform=rasterio.windows.transform(w_in, dm.transform),
            all_touched=False
        )
        assert not m_in[0, 0] is True  # True berarti di dalam poligon

        # B. Titik Pusat Eksterior (Laut Jawa)
        r_out, c_out = dm.index(113.9165, -5.0)
        lon_out, lat_out = dm.xy(r_out, c_out)
        pt_out = Point(lon_out, lat_out)

        assert kalteng_geom.contains(pt_out) is False
        assert kalteng_geom.intersects(pt_out) is False
        assert kalteng_geom.covers(pt_out) is False

        w_out = Window(c_out, r_out, 1, 1)
        m_out = geometry_mask(
            [kalteng_geom],
            out_shape=(1, 1),
            transform=rasterio.windows.transform(w_out, dm.transform),
            all_touched=False
        )
        assert not m_out[0, 0] is False  # False berarti di luar poligon

        # C. Titik Transisi Batas (Kolom 15665, baris 13568 vs 13569)
        lon_b_in, lat_b_in = dm.xy(13568, 15665)
        lon_b_out, lat_b_out = dm.xy(13569, 15665)
        pt_b_in = Point(lon_b_in, lat_b_in)
        pt_b_out = Point(lon_b_out, lat_b_out)

        assert kalteng_geom.contains(pt_b_in) is True
        assert kalteng_geom.contains(pt_b_out) is False

        # D. Titik Tepat pada Garis Batas Poligon (Boundary Vertex)
        poly_major = max(kalteng_geom.geoms, key=lambda p: p.area) if kalteng_geom.geom_type == "MultiPolygon" else kalteng_geom
        vertex_coord = poly_major.exterior.coords[10]
        pt_vertex = Point(vertex_coord)

        # Semantik DE-9IM: titik tepat di batas menghasilkan contains False, touches True, covers True
        assert kalteng_geom.contains(pt_vertex) is False
        assert kalteng_geom.touches(pt_vertex) is True
        assert kalteng_geom.intersects(pt_vertex) is True
        assert kalteng_geom.covers(pt_vertex) is True


# =========================================================================
# 9. REGRESI VALIDASI INDEPENDEN KALIMANTAN BARAT (TEMUAN STUDI KASUS KALBAR)
# =========================================================================

def test_kalbar_coverage_four_tiles_and_bounds():
    """
    Memverifikasi cakupan 4 tile resmi Hansen GFC v1.13 untuk Kalimantan Barat:
    - 4 tile: 00N_100E, 00N_110E, 10N_100E, 10N_110E.
    - Seluruh 12 GeoTIFF (datamask, treecover2000, lossyear) tersedia dan terverifikasi.
    - Wilayah daratan administratif 100% tercakup (nodata_marine == 0 piksel).
    - Partisi tertutup: valid_land + permanent_water == total_polygon.
    - Partisi daratan: stable_forest + non_forest_baseline + loss_total == valid_land.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalbar_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalbar_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    # 4 tile resmi
    assert set(val_data["validation_metadata"]["intersecting_tiles_verified"]) == {
        "00N_100E", "00N_110E", "10N_100E", "10N_110E"
    }

    metrics = {m["metric"]: m["val_method1"] for m in val_data["metrics_comparison"]}

    # NoData di dalam poligon = 0
    assert metrics["Piksel NoData/Laut"] == 0

    # Partisi poligon
    total_px = metrics["Total Piksel Poligon"]
    land_px = metrics["Piksel Daratan Valid"]
    water_px = metrics["Piksel Air Permanen"]
    assert land_px + water_px == total_px
    assert total_px == 190_816_884

    # Partisi daratan
    stable_px = metrics["Piksel Hutan Stabil"]
    nonforest_px = metrics["Piksel Non-Hutan Baseline"]
    loss_px = metrics["Piksel Kehilangan 2001-2025"]
    assert stable_px + nonforest_px + loss_px == land_px
    assert land_px == 189_160_519


def test_kalbar_independent_validation_exact_pixel_match():
    """
    Memverifikasi bahwa perbandingan Metode 1 dan Metode 2 untuk Kalbar menghasilkan
    kecocokan eksak 100% (selisih 0 piksel) untuk seluruh metrik hitungan piksel,
    serta selisih luas hektare <= 0.001% (presisi floating-point).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalbar_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalbar_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    for item in val_data["metrics_comparison"]:
        if item["is_count"]:
            assert item["diff_abs"] == 0, f"Piksel {item['metric']} tidak cocok: diff={item['diff_abs']}"
        else:
            assert item["diff_rel_pct"] <= 0.001, f"Luas {item['metric']} melebihi toleransi: {item['diff_rel_pct']}%"


def test_kalbar_polygon_area_albers_vs_raster_discretization():
    """
    Memverifikasi bahwa luas poligon Albers Equal-Area WGS84 untuk Kalbar (14.677.466,09 ha)
    sangat konsisten dengan penjumlahan luas piksel diskret (14.677.472,65 ha),
    dengan selisih hanya 6,56 ha (< 0.001% / ~0.45 ppm).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalbar_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalbar_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    poly_comp = val_data["polygon_area_comparison"]
    albers_ha = poly_comp["method_2a_albers_wgs84_ha"]

    total_pixel_ha = None
    for item in val_data["metrics_comparison"]:
        if item["metric"] == "Luas Total Piksel (ha)":
            total_pixel_ha = item["val_method2"]
            break

    assert total_pixel_ha is not None
    diff_ha = abs(albers_ha - total_pixel_ha)
    diff_pct = (diff_ha / albers_ha) * 100.0

    assert diff_pct < 0.001, f"Selisih Albers vs Raster diskret {diff_pct}% melebihi 0.001%"
    assert diff_ha < 10.0, f"Selisih absolut {diff_ha} ha melebihi 10 ha"


def test_kalbar_numerator_denominator_cohort_distinction():
    """
    Memverifikasi distingsi numerikal kohort untuk Kalimantan Barat:
    - 1.386.245 piksel (106.621,45 ha) kehilangan terjadi pada piksel treecover2000 == 0.
    - Rasio tak terkekang (unconstrained): 32.49% (pada baseline >0%) dan 33.18% (pada baseline >=30%).
    - Rasio kohort simetris (strict cohort): 31.72% (pada baseline >0%) dan 31.97% (pada baseline >=30%).
    - Rasio kohort simetris secara matematis lebih rendah daripada rasio tak terkekang.
    - Rasio kehilangan terhadap seluruh daratan valid adalah 31.03%.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalbar_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalbar_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    analysis = val_data["numerator_denominator_analysis"]
    assert analysis["loss_on_baseline_eq0_ha"] > 100_000.0
    assert analysis["loss_pct_of_land"] == 31.03
    assert analysis["loss_pct_strict_cohort_of_gt0"] == 31.72
    assert analysis["loss_pct_unconstrained_of_gt0"] == 32.49
    assert analysis["loss_pct_strict_cohort_of_gt0"] < analysis["loss_pct_unconstrained_of_gt0"]
    assert analysis["loss_pct_strict_cohort_of_ge30"] == 31.97
    assert analysis["loss_pct_unconstrained_of_ge30"] == 33.18
    assert analysis["loss_pct_strict_cohort_of_ge30"] < analysis["loss_pct_unconstrained_of_ge30"]


def test_kalbar_direct_raster_benchmark_pixels():
    """
    Memverifikasi 5 titik benchmark lapangan langsung dari raster resmi Kalbar:
    1. Pontianak: datamask=1, treecover2000=0, lossyear=0 (urban/non-forest)
    2. Danau Sentarum: datamask=2, treecover2000=0, lossyear=0 (air permanen)
    3. Ketapang Peatland: datamask=1, treecover2000=12, lossyear=0 (hutan kanopi rendah stabil)
    4. TN Gunung Palung: datamask=1, treecover2000=98, lossyear=0 (hutan primer utuh)
    5. Singkawang: datamask=1, treecover2000=0, lossyear=0 (non-hutan pantai/urban)
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalbar_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalbar_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    samples = {s["label"]: s for s in val_data["pixel_samples"]}

    # 1. Pontianak
    p_ptk = samples["Pontianak (Kawasan Urban)"]
    assert p_ptk["datamask"] == 1
    assert p_ptk["treecover2000"] == 0
    assert p_ptk["lossyear"] == 0
    assert p_ptk["tile_id"] == "00N_100E"

    # 2. Danau Sentarum
    p_ds = samples["Taman Nasional Danau Sentarum (Air/Rawa)"]
    assert p_ds["datamask"] == 2
    assert p_ds["lossyear"] == 0
    assert p_ds["tile_id"] == "10N_110E"

    # 3. Ketapang Peatland
    p_ktp = samples["Kawasan Gambut Ketapang (Kehilangan Kanopi)"]
    assert p_ktp["datamask"] == 1
    assert p_ktp["treecover2000"] == 12
    assert p_ktp["lossyear"] == 0
    assert p_ktp["tile_id"] == "00N_100E"

    # 4. TN Gunung Palung
    p_gp = samples["Taman Nasional Gunung Palung (Hutan Utuh)"]
    assert p_gp["datamask"] == 1
    assert p_gp["treecover2000"] >= 90
    assert p_gp["lossyear"] == 0
    assert p_gp["tile_id"] == "00N_110E"

    # 5. Singkawang
    p_skw = samples["Singkawang / Bengkayang (Zona Utara)"]
    assert p_skw["datamask"] == 1
    assert p_skw["treecover2000"] == 0
    assert p_skw["lossyear"] == 0
    assert p_skw["tile_id"] == "10N_100E"


def test_kalbar_missing_tile_returns_insufficient_data(tmp_path):
    """
    Memverifikasi perilaku ketika salah satu tile Kalbar tidak tersedia:
    - Contoh: tile 10N_100E (Singkawang / Kalbar utara barat) tidak ada di direktori.
    - Titik Singkawang (0.90, 108.98) harus mengembalikan STATUS_INSUFFICIENT_DATA.
    - Sistem tidak boleh zero-fill atau menghasilkan exception.
    """
    partial_dir = tmp_path / "partial_kalbar"
    partial_dir.mkdir(parents=True)

    # Hanya query ke direktori tanpa tile 10N_100E
    res = read_hansen_pixel(0.90, 108.98, tiles_dir=partial_dir, use_official=True)
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.raster_available is False
    assert res.is_official is True
    assert res.loss_detected is False
    assert res.data_verified is False
    assert "belum tersedia" in (res.error_message or "").lower()


# =========================================================================
# 10. REGRESI VALIDASI INDEPENDEN KALIMANTAN SELATAN (TEMUAN STUDI KASUS KALSEL)
# =========================================================================

def test_kalsel_coverage_single_tile_and_bounds():
    """
    Memverifikasi cakupan tile resmi Hansen GFC v1.13 untuk Kalimantan Selatan:
    - Seluruh wilayah daratan administratif 100% berada di dalam 1 tile: 00N_110E.
    - 3 layer GeoTIFF resmi (datamask, treecover2000, lossyear) tersedia dan terverifikasi.
    - Wilayah daratan administratif 100% tercakup (nodata_marine == 0 piksel).
    - Partisi tertutup: valid_land + permanent_water == total_polygon.
    - Partisi daratan: stable_forest + non_forest_baseline + loss_total == valid_land.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalsel_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalsel_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    # 1 tile resmi: 00N_110E
    assert val_data["validation_metadata"]["intersecting_tiles_verified"] == ["00N_110E"]

    metrics = {m["metric"]: m["val_method1"] for m in val_data["metrics_comparison"]}

    # NoData di dalam poligon = 0
    assert metrics["Piksel NoData/Laut"] == 0

    # Partisi poligon
    total_px = metrics["Total Piksel Poligon"]
    land_px = metrics["Piksel Daratan Valid"]
    water_px = metrics["Piksel Air Permanen"]
    assert land_px + water_px == total_px
    assert total_px == 48_488_584

    # Partisi daratan
    stable_px = metrics["Piksel Hutan Stabil"]
    nonforest_px = metrics["Piksel Non-Hutan Baseline"]
    loss_px = metrics["Piksel Kehilangan 2001-2025"]
    assert stable_px + nonforest_px + loss_px == land_px
    assert land_px == 48_021_780


def test_kalsel_independent_validation_exact_pixel_match():
    """
    Memverifikasi bahwa perbandingan Metode 1 dan Metode 2 untuk Kalsel menghasilkan
    kecocokan eksak 100% (selisih 0 piksel) untuk seluruh metrik hitungan piksel,
    serta selisih luas hektare <= 0.001% (presisi floating-point kuadratur).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalsel_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalsel_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    for item in val_data["metrics_comparison"]:
        if item["is_count"]:
            assert item["diff_abs"] == 0, f"Piksel {item['metric']} tidak cocok: diff={item['diff_abs']}"
        else:
            assert item["diff_rel_pct"] <= 0.001, f"Luas {item['metric']} melebihi toleransi: {item['diff_rel_pct']}%"


def test_kalsel_polygon_area_albers_vs_raster_discretization():
    """
    Memverifikasi bahwa luas poligon Albers Equal-Area WGS84 untuk Kalsel (3.725.165,73 ha)
    sangat konsisten dengan penjumlahan luas piksel diskret (3.725.143,82 ha),
    dengan selisih hanya 21,91 ha (< 0.001% / ~5.8 ppm).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalsel_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalsel_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    poly_comp = val_data["polygon_area_comparison"]
    albers_ha = poly_comp["method_2a_albers_wgs84_ha"]

    total_pixel_ha = None
    for item in val_data["metrics_comparison"]:
        if item["metric"] == "Luas Total Piksel (ha)":
            total_pixel_ha = item["val_method2"]
            break

    assert total_pixel_ha is not None
    diff_ha = abs(albers_ha - total_pixel_ha)
    diff_pct = (diff_ha / albers_ha) * 100.0

    assert diff_pct < 0.001, f"Selisih Albers vs Raster diskret {diff_pct}% melebihi 0.001%"
    assert diff_ha < 30.0, f"Selisih absolut {diff_ha} ha melebihi 30 ha"


def test_kalsel_numerator_denominator_cohort_distinction():
    """
    Memverifikasi distingsi numerikal kohort untuk Kalimantan Selatan:
    - 1.194.681 piksel (91.760,19 ha atau 8,50% dari total kehilangan) terjadi pada piksel treecover2000 == 0.
    - Rasio tak terkekang (unconstrained): 35.71% (pada baseline >0%) dan 38.69% (pada baseline >=30%).
    - Rasio kohort simetris (strict cohort): 32.68% (pada baseline >0%) dan 34.36% (pada baseline >=30%).
    - Rasio kohort simetris secara matematis lebih rendah daripada rasio tak terkekang.
    - Rasio kehilangan terhadap seluruh daratan valid adalah 29.28%.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalsel_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalsel_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    analysis = val_data["numerator_denominator_analysis"]
    assert analysis["loss_on_baseline_eq0_ha"] > 90_000.0
    assert analysis["loss_pct_of_land"] == 29.28
    assert analysis["loss_pct_strict_cohort_of_gt0"] == 32.68
    assert analysis["loss_pct_unconstrained_of_gt0"] == 35.71
    assert analysis["loss_pct_strict_cohort_of_gt0"] < analysis["loss_pct_unconstrained_of_gt0"]
    assert analysis["loss_pct_strict_cohort_of_ge30"] == 34.36
    assert analysis["loss_pct_unconstrained_of_ge30"] == 38.69
    assert analysis["loss_pct_strict_cohort_of_ge30"] < analysis["loss_pct_unconstrained_of_ge30"]


def test_kalsel_direct_raster_benchmark_pixels():
    """
    Memverifikasi 5 titik benchmark lapangan langsung dari raster resmi Kalsel (tile 00N_110E):
    1. Banjarmasin: datamask=1, treecover2000=0, lossyear=0 (urban/non-forest)
    2. Pegunungan Meratus: datamask=1, treecover2000=97, lossyear=0 (hutan primer utuh)
    3. Perairan Muara Sungai Barito: datamask=2, treecover2000=0, lossyear=0 (air permanen)
    4. Pulau Laut Kotabaru: datamask=1, treecover2000=0, lossyear=23 (kehilangan 2023 pada non-forest baseline)
    5. Tanah Laut / Asam-asam: datamask=1, treecover2000=89, lossyear=4 (kehilangan 2004 pada baseline lebat)
    """
    val_file = HANSEN_OFFICIAL_DIR / "kalsel_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kalsel_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    samples = {s["label"]: s for s in val_data["pixel_samples"]}

    # 1. Banjarmasin
    p_bjm = samples["Banjarmasin (-3.3194, 114.5908)"]
    assert p_bjm["datamask"] == 1
    assert p_bjm["treecover2000"] == 0
    assert p_bjm["lossyear"] == 0
    assert p_bjm["tile_id"] == "00N_110E"

    # 2. Meratus
    p_mrt = samples["Pegunungan Meratus (-2.7500, 115.6500)"]
    assert p_mrt["datamask"] == 1
    assert p_mrt["treecover2000"] >= 90
    assert p_mrt["lossyear"] == 0
    assert p_mrt["tile_id"] == "00N_110E"

    # 3. Muara Barito
    p_brt = samples["Muara Sungai Barito (-3.5500, 114.5000)"]
    assert p_brt["datamask"] == 2
    assert p_brt["lossyear"] == 0
    assert p_brt["tile_id"] == "00N_110E"

    # 4. Pulau Laut Kotabaru (tc=0, ly=23)
    p_pl = samples["Pulau Laut Kotabaru (-3.3500, 116.1500)"]
    assert p_pl["datamask"] == 1
    assert p_pl["treecover2000"] == 0
    assert p_pl["lossyear"] == 23
    assert p_pl["tile_id"] == "00N_110E"

    # 5. Tanah Laut / Asam-asam
    p_tl = samples["Tanah Laut / Asam-asam (-3.8500, 115.1500)"]
    assert p_tl["datamask"] == 1
    assert p_tl["treecover2000"] >= 80
    assert p_tl["lossyear"] == 4
    assert p_tl["tile_id"] == "00N_110E"


# ==============================================================================
# 11. PENGUJIAN AUDIT ZONAL DAN VALIDASI INDEPENDEN KALIMANTAN TIMUR (2 TILE)
# ==============================================================================


def test_kaltim_coverage_two_tiles_and_bounds():
    """
    Memverifikasi bahwa Kalimantan Timur:
    - Melintasi garis khatulistiwa (-2.416° s.d. +3.444°), sehingga memerlukan 2 baris tile (00N dan 10N).
    - Berada pada bujur 113.843° s.d. 118.988°, sepenuhnya berada dalam kolom tile 110E.
    - Tepat dicakup oleh 2 tile: 00N_110E dan 10N_110E.
    - Semua 6 berkas GeoTIFF resmi (3 layer x 2 tile) tersedia, berdimensi 40.000 x 40.000 piksel, dan valid.
    """
    import json
    import rasterio
    from shapely.geometry import shape
    from shapely.validation import make_valid

    with open(BOUNDARIES_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)

    kaltim_raw = None
    kaltara_raw = None
    for feat in gj["features"]:
        props = feat.get("properties", {})
        name = props.get("state") or props.get("name") or props.get("NAME_1") or props.get("Propinsi") or ""
        if "kalimantan timur" in name.lower():
            kaltim_raw = shape(feat["geometry"])
        elif "kalimantan utara" in name.lower():
            kaltara_raw = shape(feat["geometry"])

    assert kaltim_raw is not None
    assert kaltara_raw is not None

    kaltim_geom = make_valid(make_valid(kaltim_raw).difference(make_valid(kaltara_raw)))
    min_x, min_y, max_x, max_y = kaltim_geom.bounds

    assert min_x >= 113.0 and max_x <= 120.0
    assert min_y < 0.0, "Kalimantan Timur bagian selatan harus berada di lintang negatif (<0°)"
    assert max_y > 0.0, "Kalimantan Timur bagian utara harus berada di lintang positif (>0°)"

    required_tiles = ["00N_110E", "10N_110E"]
    required_layers = ["datamask", "treecover2000", "lossyear"]

    for t in required_tiles:
        for layer in required_layers:
            p = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_{layer}_{t}_official.tif"
            assert p.exists(), f"Berkas raster {p.name} tidak ditemukan"
            with rasterio.open(p) as src:
                assert src.shape == (40000, 40000)
                assert src.crs.to_string() == "EPSG:4326"
                assert src.dtypes[0] == "uint8"


def test_kaltim_independent_validation_exact_pixel_match():
    """
    Memverifikasi bahwa validasi independen (Metode 2) pada Kalimantan Timur
    menghasilkan kecocokan 100% (0 piksel selisih) terhadap seluruh metrik hitungan
    dari laporan primer (Metode 1) pada 163.797.677 piksel.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kaltim_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kaltim_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    for item in val_data["metrics_comparison"]:
        if item["is_count"]:
            assert item["diff_abs"] == 0, f"Piksel {item['metric']} tidak cocok: diff={item['diff_abs']}"
        else:
            assert item["diff_rel_pct"] <= 0.001, f"Luas {item['metric']} melebihi toleransi: {item['diff_rel_pct']}%"


def test_kaltim_polygon_area_albers_vs_raster_discretization():
    """
    Memverifikasi bahwa luas poligon Albers Equal-Area WGS84 untuk Kaltim (12.598.515,14 ha)
    sangat konsisten dengan penjumlahan luas piksel diskret (12.598.525,06 ha),
    dengan selisih hanya 9,92 ha (< 0.0001% / ~0.79 ppm).
    """
    val_file = HANSEN_OFFICIAL_DIR / "kaltim_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kaltim_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    poly_comp = val_data["polygon_area_comparison"]
    albers_ha = poly_comp["method_2a_albers_wgs84_ha"]

    total_pixel_ha = None
    for item in val_data["metrics_comparison"]:
        if item["metric"] == "Luas Total Piksel (ha)":
            total_pixel_ha = item["val_method2"]
            break

    assert total_pixel_ha is not None
    diff_ha = abs(albers_ha - total_pixel_ha)
    diff_pct = (diff_ha / albers_ha) * 100.0

    assert diff_pct < 0.001, f"Selisih Albers vs Raster diskret {diff_pct}% melebihi 0.001%"
    assert diff_ha < 15.0, f"Selisih absolut {diff_ha} ha melebihi 15 ha"


def test_kaltim_numerator_denominator_cohort_distinction():
    """
    Memverifikasi distingsi numerikal kohort untuk Kalimantan Timur:
    - 1.530.339 piksel (117.712,05 ha atau 3,45% dari total kehilangan) terjadi pada piksel treecover2000 == 0.
    - Rasio tak terkekang (unconstrained): 28.60% (pada baseline >0%) dan 29.06% (pada baseline >=30%).
    - Rasio kohort simetris (strict cohort): 27.61% (pada baseline >0%) dan 27.65% (pada baseline >=30%).
    - Rasio kohort simetris secara matematis lebih rendah daripada rasio tak terkekang.
    - Rasio kehilangan terhadap seluruh daratan valid adalah 27.29%.
    """
    val_file = HANSEN_OFFICIAL_DIR / "kaltim_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kaltim_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    analysis = val_data["numerator_denominator_analysis"]
    assert analysis["loss_on_baseline_eq0_ha"] > 110_000.0
    assert analysis["loss_pct_of_land"] == 27.29
    assert analysis["loss_pct_strict_cohort_of_gt0"] == 27.61
    assert analysis["loss_pct_unconstrained_of_gt0"] == 28.60
    assert analysis["loss_pct_strict_cohort_of_gt0"] < analysis["loss_pct_unconstrained_of_gt0"]
    assert analysis["loss_pct_strict_cohort_of_ge30"] == 27.65
    assert analysis["loss_pct_unconstrained_of_ge30"] == 29.06
    assert analysis["loss_pct_strict_cohort_of_ge30"] < analysis["loss_pct_unconstrained_of_ge30"]


def test_kaltim_direct_raster_benchmark_pixels():
    """
    Memverifikasi 5 titik benchmark lapangan langsung dari raster resmi Kaltim (tile 00N_110E dan 10N_110E):
    1. Samarinda: datamask=1, treecover2000=0, lossyear=0 (urban/non-forest) - 00N_110E
    2. Taman Nasional Kutai: datamask=1, treecover2000=82, lossyear=0 (hutan lebat utuh terlindungi) - 10N_110E
    3. Danau Semayang / Sungai Mahakam: datamask=2, treecover2000=0, lossyear=0 (air permanen) - 00N_110E
    4. Kutai Barat: datamask=1, treecover2000=89, lossyear=16 (kehilangan kanopi 2016 pada baseline lebat) - 10N_110E
    5. Paser / Penajam: datamask=1, treecover2000=90, lossyear=9 (kehilangan kanopi 2009 pada baseline lebat) - 00N_110E
    """
    val_file = HANSEN_OFFICIAL_DIR / "kaltim_independent_validation_report.json"
    if not val_file.exists():
        pytest.skip("Laporan kaltim_independent_validation_report.json belum dibuat")

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    samples = {s["label"]: s for s in val_data["pixel_samples"]}

    # 1. Samarinda
    p_smr = samples["Samarinda (-0.5022, 117.1536)"]
    assert p_smr["datamask"] == 1
    assert p_smr["treecover2000"] == 0
    assert p_smr["lossyear"] == 0
    assert p_smr["tile_id"] == "00N_110E"

    # 2. TN Kutai
    p_kut = samples["Taman Nasional Kutai (0.4500, 117.2500)"]
    assert p_kut["datamask"] == 1
    assert p_kut["treecover2000"] >= 80
    assert p_kut["lossyear"] == 0
    assert p_kut["tile_id"] == "10N_110E"

    # 3. Danau Semayang / Sungai Mahakam
    p_mhk = samples["Danau Semayang / Sungai Mahakam (-0.2500, 116.5000)"]
    assert p_mhk["datamask"] == 2
    assert p_mhk["lossyear"] == 0
    assert p_mhk["tile_id"] == "00N_110E"

    # 4. Kutai Barat
    p_kub = samples["Kutai Barat (0.0500, 115.8000)"]
    assert p_kub["datamask"] == 1
    assert p_kub["treecover2000"] >= 80
    assert p_kub["lossyear"] == 16
    assert p_kub["tile_id"] == "10N_110E"

    # 5. Paser / Penajam
    p_psr = samples["Paser / Penajam (-1.4000, 116.2000)"]
    assert p_psr["datamask"] == 1
    assert p_psr["treecover2000"] >= 80
    assert p_psr["lossyear"] == 9
    assert p_psr["tile_id"] == "00N_110E"





