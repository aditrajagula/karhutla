"""
Pengujian Analisis Perubahan Tutupan Pohon (Hansen Global Forest Change 2025 v1.13).
Memverifikasi:
1. Perhitungan luas piksel geodesik berbasis rumus WGS84 dan koreksi kosinus lintang.
2. Agregasi tahunan (2001-2025) dan baseline tutupan pohon 5 provinsi Kalimantan.
3. Endpoint /api/v1/forest-loss/summary menyajikan data lengkap, metodologi, dan keterbatasan ilmiah.
4. Endpoint /api/v1/forest-loss/point mengevaluasi titik secara akurat.
5. Penegasan bahwa tree cover loss != deforestasi ilegal.
"""

import math
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.forest_change_service import (
    calculate_pixel_area_ha,
    get_forest_loss_summary,
    evaluate_forest_change_point,
    KALIMANTAN_PROVINCES,
)

@pytest.fixture
def client():
    return TestClient(app)


def test_pixel_area_wgs84_ellipsoid_math():
    """
    Memverifikasi perhitungan luas sel raster dengan integrasi elipsoid WGS84 analitik (authalic):
    1. Lintang 0° (ekuator) sel 0.00025° x 0.00025°: ~0.0769317 ha (~769.32 m²).
    2. Lintang -2.25° (koridor Kalteng): ~0.0768740 ha (~768.74 m²).
    3. Resolusi kustom (1 arc-sec): ~0.0949774 ha.
    4. Resolusi asimetris (dX != dY).
    5. Batas lintang valid dan batas eksplisit lat_south / lat_north.
    """
    # 1. Nilai ekuator 0° Hansen GFC (0.00025°)
    area_equator = calculate_pixel_area_ha(0.0)
    assert abs(area_equator - 0.0769317) < 1e-6, f"Luas ekuator {area_equator} berbeda dari ekspektasi 0.0769317 ha"
    assert round(area_equator, 4) == 0.0769

    # 2. Lintang -2.25° (Koridor Palangka Raya - Pulang Pisau)
    area_kalteng = calculate_pixel_area_ha(-2.25)
    assert abs(area_kalteng - 0.0768740) < 1e-6, f"Luas -2.25° {area_kalteng} berbeda dari ekspektasi 0.0768740 ha"
    assert round(area_kalteng, 4) == 0.0769
    assert area_kalteng < area_equator

    # 3. Validasi independen terhadap rumus diferensial M(phi) * N(phi) * cos(phi) * dphi * dlambda
    wgs84_a = 6378137.0
    wgs84_f = 1.0 / 298.257223563
    wgs84_e2 = 2.0 * wgs84_f - wgs84_f**2
    rad_phi = math.radians(-2.25)
    sin_p = math.sin(rad_phi)
    m = wgs84_a * (1.0 - wgs84_e2) / ((1.0 - wgs84_e2 * sin_p**2) ** 1.5)
    n = wgs84_a / math.sqrt(1.0 - wgs84_e2 * sin_p**2)
    d_rad = math.radians(0.00025)
    diff_area_ha = (m * d_rad) * (n * math.cos(rad_phi) * d_rad) / 10000.0
    # Integrasi analitik dan diferensial untuk sel kecil 0.00025° harus bersesuaian sangat tinggi (< 1e-9 ha)
    assert abs(area_kalteng - diff_area_ha) < 1e-8

    # 4. Resolusi kustom (misal 1 arc-second ~ 1/3600°)
    area_1arcsec = calculate_pixel_area_ha(0.0, degrees_per_pixel=1.0 / 3600.0)
    assert abs(area_1arcsec - 0.0949774) < 1e-6, f"Luas 1 arc-sec {area_1arcsec} harus ~0.0949774 ha"

    # 5. Resolusi asimetris X dan Y (dX=0.00025, dY=0.0005)
    area_asym = calculate_pixel_area_ha(0.0, degrees_per_pixel=0.00025, degrees_per_pixel_y=0.0005)
    assert abs(area_asym - 2.0 * area_equator) < 1e-6, "Resolusi dY ganda harus menghasilkan luas 2x"

    # 6. Batas eksplisit lat_south dan lat_north
    half_dy = 0.00025 / 2.0
    area_from_bounds = calculate_pixel_area_ha(
        0.0,
        degrees_per_pixel=0.00025,
        lat_south_deg=-2.25 - half_dy,
        lat_north_deg=-2.25 + half_dy,
    )
    assert abs(area_from_bounds - area_kalteng) < 1e-9

    # 7. Penanganan batas kutub dan swap terbalik
    area_swapped = calculate_pixel_area_ha(
        0.0,
        degrees_per_pixel=0.00025,
        lat_south_deg=2.0,
        lat_north_deg=1.9,
    )
    assert area_swapped > 0.0


def test_forest_loss_summary_completeness():
    """Memverifikasi bahwa ringkasan mencakup seluruh 5 provinsi, baseline, dan tahun 2001-2025."""
    summary = get_forest_loss_summary()
    assert summary["dataset"] == "Hansen Global Forest Change v1.13 (2000–2025)"
    assert summary["coverage"] == "5 Provinsi Kalimantan Bagian Indonesia (Eksklusif)"
    assert "Sarawak (Malaysia)" in summary["excluded_territories"]
    assert "Brunei Darussalam" in summary["excluded_territories"]

    # Pastikan 5 provinsi ada
    prov_data = summary["provincial_data"]
    assert len(prov_data) == 5
    prov_names = [p["province"] for p in prov_data]
    for p in KALIMANTAN_PROVINCES:
        assert p in prov_names

    # Pastikan setiap provinsi memiliki riwayat dari 2001 sampai 2025
    for item in prov_data:
        annual = item["annual_loss_ha"]
        assert len(annual) == 25, f"{item['province']} harus memiliki 25 tahun data (2001-2025)"
        assert "2001" in annual
        assert "2025" in annual
        assert item["cumulative_loss_2001_2025_ha"] == round(sum(annual.values()), 2)
        assert item["baseline_treecover_2000_ha"] > item["cumulative_loss_2001_2025_ha"]

    # Metadata demonstrasi wajib ada
    assert summary["data_status"] == "demonstration"
    assert summary["data_verified"] is False
    assert "verification_notes" in summary
    assert len(summary["verification_notes"]) > 0

    # Pastikan setiap provinsi juga memiliki metadata demonstrasi
    for item in prov_data:
        assert item["data_status"] == "demonstration"
        assert item["data_verified"] is False
        assert "verification_notes" in item

    # Keterbatasan ilmiah wajib ada
    assert len(summary["limitations"]) >= 3
    assert any("deforestasi ilegal" in lim.lower() for lim in summary["limitations"])


def test_evaluate_forest_change_point_inside_and_outside():
    """
    Menguji evaluasi titik tutupan pohon untuk lokasi di dalam dan luar Kalimantan.
    Membuktikan:
    1. Titik di dalam Kalimantan tidak otomatis mendapat SUPPORTING_INDICATION saat raster tidak tersedia.
    2. Status internal INSUFFICIENT_DATA dan label publik 'Belum dapat dinilai' dikembalikan secara jujur.
    3. Status tidak berubah menjadi NO_MATCH_FOUND.
    4. Metadata demonstrasi disertakan.
    """
    # Titik di Palangka Raya (Kalteng)
    res_kalteng = evaluate_forest_change_point(lat=-2.21, lon=113.92, province="Kalimantan Tengah")
    assert res_kalteng["status"] == "INSUFFICIENT_DATA"
    assert res_kalteng["category_result"] == "Belum dapat dinilai"
    assert res_kalteng["status"] != "SUPPORTING_INDICATION"
    assert res_kalteng["status"] != "NO_MATCH_FOUND"
    assert res_kalteng["province"] == "Kalimantan Tengah"
    assert res_kalteng["pixel_area_ha"] > 0
    assert res_kalteng["data_status"] == "demonstration"
    assert res_kalteng["data_verified"] is False
    assert res_kalteng["raster_available"] is False
    assert "scientific_caveat" in res_kalteng
    assert "tidak secara otomatis membuktikan" in res_kalteng["scientific_caveat"].lower()

    # Titik di luar Kalimantan (misal Kuching, Sarawak)
    res_kuching = evaluate_forest_change_point(lat=1.55, lon=110.35, province="Sarawak")
    assert res_kuching["status"] == "INSUFFICIENT_DATA"
    assert res_kuching["category_result"] == "Belum dapat dinilai"
    assert res_kuching["raster_available"] is False


def test_evaluate_forest_change_point_future_raster_support():
    """
    Menguji bahwa jika pada masa mendatang raster aktual tingkat piksel tersedia,
    evaluasi titik didasarkan pada nilai piksel aktual yang diperiksa.
    """
    # Kasus ada kehilangan piksel aktual
    pixel_loss = {
        "loss_detected": True,
        "loss_year": 2023,
        "treecover2000": 80
    }
    res_loss = evaluate_forest_change_point(
        lat=-2.21,
        lon=113.92,
        province="Kalimantan Tengah",
        pixel_raster_available=True,
        raster_pixel_value=pixel_loss
    )
    assert res_loss["status"] == "SUPPORTING_INDICATION"
    assert res_loss["category_result"] == "Ada indikasi pendukung"
    assert res_loss["raster_available"] is True
    assert res_loss["data_verified"] is False
    assert res_loss["data_status"] == "demonstration"
    assert "tidak secara otomatis membuktikan" in res_loss["scientific_caveat"].lower()

    # Kasus tidak ada kehilangan kanopi pada piksel
    pixel_intact = {
        "loss_detected": False,
        "loss_year": None,
        "treecover2000": 85
    }
    res_intact = evaluate_forest_change_point(
        lat=-2.21,
        lon=113.92,
        province="Kalimantan Tengah",
        pixel_raster_available=True,
        raster_pixel_value=pixel_intact
    )
    assert res_intact["status"] == "NO_MATCH_FOUND"
    assert res_intact["category_result"] == "Belum ditemukan kecocokan"


def test_forest_loss_endpoints_api(client: TestClient):
    """
    Menguji endpoint REST API /api/v1/forest-loss/summary dan /api/v1/forest-loss/point.
    Memastikan kompatibilitas key lama dan kehadiran metadata demonstrasi baru.
    """
    # Summary endpoint
    res_summary = client.get("/api/v1/forest-loss/summary")
    assert res_summary.status_code == 200
    s_data = res_summary.json()
    assert s_data["data_period"] == "2000–2025"
    assert len(s_data["provincial_data"]) == 5
    # Key lama tetap lengkap untuk frontend
    for key in [
        "dataset", "source", "documentation_url", "coverage", "excluded_territories",
        "data_period", "last_updated", "methodology", "limitations",
        "total_baseline_treecover_2000_ha", "total_cumulative_loss_2001_2025_ha",
        "total_percentage_lost", "annual_kalimantan_ha", "provincial_data"
    ]:
        assert key in s_data, f"Key '{key}' harus ada untuk kompatibilitas frontend"

    # Metadata transparansi demonstrasi
    assert s_data["data_status"] == "demonstration"
    assert s_data["data_verified"] is False
    assert "verification_notes" in s_data

    # Point endpoint
    res_pt = client.get("/api/v1/forest-loss/point?latitude=-0.026&longitude=109.342&province=Kalimantan%20Barat")
    assert res_pt.status_code == 200
    pt_data = res_pt.json()
    assert pt_data["status"] == "INSUFFICIENT_DATA"
    assert pt_data["category_result"] == "Belum dapat dinilai"
    assert pt_data["status"] != "SUPPORTING_INDICATION"
    assert pt_data["status"] != "NO_MATCH_FOUND"
    assert pt_data["province"] == "Kalimantan Barat"
    assert pt_data["pixel_area_ha"] > 0
    assert pt_data["data_status"] == "demonstration"
    assert pt_data["data_verified"] is False
    assert pt_data["raster_available"] is False


def test_boundaries_kalimantan_endpoint_demonstration_metadata(client: TestClient):
    """Menguji endpoint /api/v1/boundaries/kalimantan menyertakan metadata demonstrasi."""
    res = client.get("/api/v1/boundaries/kalimantan")
    assert res.status_code == 200
    geojson = res.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 5
    for feat in geojson["features"]:
        props = feat["properties"]
        assert props["data_status"] == "demonstration"
        assert props["data_verified"] is False
        assert "verification_notes" in props
        # Key lama tetap ada
        assert "baseline_treecover_2000_ha" in props
        assert "cumulative_loss_2001_2025_ha" in props
        assert "percentage_lost" in props
        assert "source" in props
