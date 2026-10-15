"""
Pengujian Spasial 5 Provinsi Kalimantan Indonesia dan Pengecualian Wilayah Asing.
Memverifikasi:
1. Koordinat di 5 provinsi Kalimantan Indonesia (Kalbar, Kalteng, Kalsel, Kaltim, Kaltara) diterima.
2. Koordinat di Sarawak dan Sabah (Malaysia) secara tegas DITOLAK.
3. Koordinat di Brunei Darussalam secara tegas DITOLAK.
4. Titik perbatasan (Pulau Sebatik sisi Malaysia, Tebedu, Lubok Antu) terfilter dengan akurat.
5. Endpoint /api/v1/hotspots?region=kalimantan hanya menyajikan titik di 5 provinsi Kalimantan.
6. Endpoint /api/v1/boundaries/kalimantan mengembalikan poligon 5 provinsi.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app, pipeline_instance
from app.spatial_filter import IndonesiaSpatialFilter
from app.models import HotspotRecord
from app.config import BOUNDARIES_PATH


@pytest.fixture
def spatial_filter():
    return IndonesiaSpatialFilter(BOUNDARIES_PATH)


@pytest.fixture
def client():
    return TestClient(app)


def test_kalimantan_5_provinces_inside(spatial_filter: IndonesiaSpatialFilter):
    """Memverifikasi bahwa ibu kota dan pedalaman 5 provinsi Kalimantan Indonesia terdeteksi valid."""
    points = [
        (-0.0263, 109.3425, "Kalimantan Barat"),      # Pontianak
        (-2.2079, 113.9165, "Kalimantan Tengah"),     # Palangka Raya
        (-3.3194, 114.5908, "Kalimantan Selatan"),    # Banjarmasin
        (-0.5022, 117.1536, "Kalimantan Timur"),      # Samarinda
        (2.8375, 117.3653, "Kalimantan Utara"),       # Tanjung Selor
        (-0.4500, 111.5000, "Kalimantan Barat"),      # Sintang pedalaman
        (-1.5000, 114.0000, "Kalimantan Tengah"),     # Katingan pedalaman
        (1.5000, 116.0000, "Kalimantan Timur"),       # Kutai Barat pedalaman
        (3.5000, 116.5000, "Kalimantan Utara"),       # Malinau pedalaman
    ]

    for lat, lon, expected_prov in points:
        inside, prov = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat)
        assert inside is True, f"Koordinat ({lat}, {lon}) seharusnya berada di dalam {expected_prov}"
        assert prov == expected_prov, f"Provinsi terdeteksi '{prov}' tidak sesuai dengan '{expected_prov}'"


def test_malaysia_sarawak_sabah_excluded(spatial_filter: IndonesiaSpatialFilter):
    """
    Memverifikasi secara ketat bahwa wilayah Malaysia (Sarawak dan Sabah)
    TIDAK masuk dalam cakupan analisis Kalimantan Indonesia.
    """
    malaysia_points = [
        (1.5533, 110.3592, "Kuching, Sarawak"),
        (2.3000, 111.8300, "Sibu, Sarawak"),
        (3.1800, 113.0400, "Bintulu, Sarawak"),
        (4.3995, 113.9914, "Miri, Sarawak"),
        (1.0500, 111.8300, "Lubok Antu, Sarawak"),
        (1.0100, 110.3500, "Tebedu border, Sarawak"),
        (5.9804, 116.0735, "Kota Kinabalu, Sabah"),
        (5.8402, 118.1179, "Sandakan, Sabah"),
        (4.2447, 117.8912, "Tawau, Sabah"),
        (4.1800, 117.6500, "Sebatik Utara (Malaysia)"),
    ]

    for lat, lon, loc_name in malaysia_points:
        inside, prov = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat)
        assert inside is False, f"Wilayah Malaysia ({loc_name}) pada ({lat}, {lon}) tidak boleh masuk cakupan!"
        assert prov is None


def test_brunei_darussalam_excluded(spatial_filter: IndonesiaSpatialFilter):
    """Memverifikasi bahwa Brunei Darussalam tidak masuk dalam cakupan analisis."""
    brunei_points = [
        (4.9031, 114.9398, "Bandar Seri Begawan"),
        (4.5833, 114.2333, "Kuala Belait"),
        (4.7000, 115.1500, "Temburong"),
    ]

    for lat, lon, loc_name in brunei_points:
        inside, prov = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat)
        assert inside is False, f"Wilayah Brunei ({loc_name}) pada ({lat}, {lon}) tidak boleh masuk cakupan!"
        assert prov is None


def test_ocean_and_other_islands_excluded(spatial_filter: IndonesiaSpatialFilter):
    """Memverifikasi bahwa laut dan pulau lain (Jawa, Sumatra) tidak masuk filter Kalimantan."""
    other_points = [
        (-6.2088, 106.8456, "Jakarta (Jawa)"),
        (0.5333, 101.4500, "Pekanbaru (Sumatra)"),
        (-2.0000, 109.0000, "Laut Jawa"),
        (5.0000, 110.0000, "Laut Natuna Utara / Laut Cina Selatan"),
    ]

    for lat, lon, loc_name in other_points:
        inside, prov = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat)
        assert inside is False, f"Titik di luar Kalimantan ({loc_name}) harus bernilai False"


def test_filter_kalimantan_records(spatial_filter: IndonesiaSpatialFilter):
    """Menguji penyaringan batch HotspotRecord khusus untuk Kalimantan."""
    records = [
        HotspotRecord(latitude=-0.0263, longitude=109.3425, satellite="NOAA20", acq_date="2026-10-10", acq_time="0400", observation_time_utc="2026-10-10T04:00:00Z", confidence="high", frp=15.0), # Kalbar (Pontianak)
        HotspotRecord(latitude=1.55, longitude=110.35, satellite="NOAA20", acq_date="2026-10-10", acq_time="0400", observation_time_utc="2026-10-10T04:00:00Z", confidence="high", frp=20.0),  # Kuching (Malaysia)
        HotspotRecord(latitude=-2.21, longitude=113.92, satellite="NOAA21", acq_date="2026-10-10", acq_time="0500", observation_time_utc="2026-10-10T05:00:00Z", confidence="nominal", frp=10.0), # Kalteng
        HotspotRecord(latitude=4.90, longitude=114.94, satellite="NOAA20", acq_date="2026-10-10", acq_time="0430", observation_time_utc="2026-10-10T04:30:00Z", confidence="high", frp=12.0),  # Brunei
        HotspotRecord(latitude=-6.20, longitude=106.85, satellite="NOAA20", acq_date="2026-10-10", acq_time="0400", observation_time_utc="2026-10-10T04:00:00Z", confidence="high", frp=18.0), # Jakarta
    ]



    filtered, stats = spatial_filter.filter_kalimantan_records(records)
    assert len(filtered) == 2
    provinces = [r.province for r in filtered]
    assert "Kalimantan Barat" in provinces
    assert "Kalimantan Tengah" in provinces
    assert stats.total_rejected_records == 3


def test_get_kalimantan_boundaries_endpoint(client: TestClient):
    """Menguji endpoint /api/v1/boundaries/kalimantan mengembalikan poligon 5 provinsi."""
    res = client.get("/api/v1/boundaries/kalimantan")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 5
    prov_names = [f["properties"]["province"] for f in data["features"]]
    expected = [
        "Kalimantan Barat",
        "Kalimantan Tengah",
        "Kalimantan Selatan",
        "Kalimantan Timur",
        "Kalimantan Utara",
    ]
    for exp in expected:
        assert exp in prov_names
        # Setiap provinsi memiliki baseline dan cumulative loss
        feat = next(f for f in data["features"] if f["properties"]["province"] == exp)
        assert feat["properties"]["baseline_treecover_2000_ha"] > 0
        assert feat["properties"]["cumulative_loss_2001_2025_ha"] > 0


def test_spatial_filter_tarakan_kaltara_overlap_resolution(spatial_filter: IndonesiaSpatialFilter):
    """
    Memverifikasi bahwa Pulau Tarakan teresolusi secara akurat ke Kalimantan Utara,
    bukan Kalimantan Timur (mengatasi tumpang tindih poligon historis pemekaran 2012).
    """
    # Pulau Tarakan (3.32°N, 117.60°E)
    inside, prov = spatial_filter.is_inside_kalimantan(lon=117.60, lat=3.32)
    assert inside is True
    assert prov == "Kalimantan Utara"

    # Tanjung Selor (Ibu Kota Kaltara)
    inside_ts, prov_ts = spatial_filter.is_inside_kalimantan(lon=117.37, lat=2.84)
    assert inside_ts is True
    assert prov_ts == "Kalimantan Utara"


def test_spatial_filter_property_name_variations(tmp_path):
    """
    Memverifikasi toleransi pembacaan GeoJSON jika properti menggunakan variasi
    kunci nama ('state', 'NAME_1', 'name', 'Propinsi', 'PROVINSI').
    """
    import json
    from shapely.geometry import mapping, Polygon

    poly = Polygon([(113.0, -2.0), (114.0, -2.0), (114.0, -1.0), (113.0, -1.0), (113.0, -2.0)])

    variations = [
        {"state": "Kalimantan Tengah"},
        {"NAME_1": "Kalimantan Tengah"},
        {"name": "Kalimantan Tengah"},
        {"Propinsi": "Kalimantan Tengah"},
        {"PROVINSI": "Kalimantan Tengah"},
    ]

    for i, prop in enumerate(variations):
        gj_file = tmp_path / f"test_prop_{i}.geojson"
        gj_data = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": mapping(poly), "properties": prop}]
        }
        gj_file.write_text(json.dumps(gj_data), encoding="utf-8")

        sf_custom = IndonesiaSpatialFilter(gj_file)
        inside, prov_found = sf_custom.is_inside_kalimantan(lon=113.5, lat=-1.5)
        assert inside is True
        assert prov_found == "Kalimantan Tengah"


def test_strtree_query_compatibility_shapely2(spatial_filter: IndonesiaSpatialFilter):
    """
    Memverifikasi kompatibilitas STRtree.query() dengan Shapely 2.x:
    - Mengembalikan array indeks calon poligon (integer).
    - Query point tidak menghasilkan exception atau format tak terduga.
    """
    import numpy as np
    from shapely.geometry import Point

    pt = Point(113.92, -2.21)  # Palangka Raya
    assert spatial_filter.tree is not None
    candidates = spatial_filter.tree.query(pt)

    # Pada Shapely 2.x, query(geom) pada single geometry mengembalikan numpy ndarray 1D integer
    assert isinstance(candidates, np.ndarray)
    assert candidates.ndim == 1
    assert len(candidates) > 0
    assert np.issubdtype(candidates.dtype, np.integer)


def test_administrative_boundary_points_kalimantan(spatial_filter: IndonesiaSpatialFilter):
    """
    Memverifikasi titik tepat pada batas atau perbatasan antar-provinsi:
    - Perbatasan Kalbar-Kalteng (-0.65, 112.75): terdeteksi dalam salah satu provinsi Kalimantan.
    - Parameter preferred_province menghargai pilihan provinsi yang sah.
    """
    lat, lon = -0.65, 112.75

    # Tanpa preferred_province
    inside, prov = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat)
    assert inside is True
    assert prov in ("Kalimantan Barat", "Kalimantan Tengah")

    # Dengan preferred_province Kalimantan Tengah
    inside_kt, prov_kt = spatial_filter.is_inside_kalimantan(lon=lon, lat=lat, preferred_province="Kalimantan Tengah")
    assert inside_kt is True
    assert prov_kt == "Kalimantan Tengah"

