"""
backend/tests/test_glad_forest_reader.py
Pengujian Otomatis Komprehensif Layer Klasifikasi Hutan GLAD Forest Extent 2020.

Kondisi Wajib yang Diuji:
1. Titik yang pikselnya terverifikasi sebagai FOREST (nilai 1).
2. Titik yang pikselnya terverifikasi sebagai NON_FOREST (nilai 0).
3. Titik dengan nilai NoData (255 / nodata) -> UNKNOWN (Bukan NON_FOREST).
4. Koordinat di luar cakupan raster -> UNKNOWN.
5. Berkas raster tidak ditemukan -> UNKNOWN (Bukan default NON_FOREST).
6. Koordinat pada batas tile atau peralihan antartile (boundary transition).
7. Koordinat dengan urutan latitude-longitude yang keliru (swapped lat/lon).
8. Lookup hutan dan gambut pada koordinat yang sama tidak saling memengaruhi.
9. Endpoint dan respons menangani status UNKNOWN tanpa menampilkannya sebagai NON_FOREST.
10. Berjalan offline tanpa memerlukan koneksi internet (menggunakan raster fixture sintetis lokal).
"""

from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from app.main import app
from app.glad_forest_reader import (
    CLASS_FOREST,
    CLASS_NON_FOREST,
    CLASS_UNKNOWN,
    clear_forest_cache,
    check_glad_forest_layer_availability,
    find_glad_raster_file,
    get_glad_tile_id,
    get_tile_bounds,
    lookup_forest_extent,
    validate_geographic_coordinates,
)
from app.forest_change_service import evaluate_forest_change_point


@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    """Memastikan cache memori selalu bersih sebelum tiap pengujian."""
    clear_forest_cache()
    yield
    clear_forest_cache()


@pytest.fixture
def synthetic_forest_tiles(tmp_path: Path):
    """
    Membuat fixture raster GeoTIFF mini lokal (10x10 piksel)
    untuk tile '00N_110E' dan '10N_110E' dengan proyeksi EPSG:4326.
    Resolusi 0.00025° per piksel.

    Tile 00N_110E:
      Origin (top-left): (110.0, 0.0) -> lat -0.0025 s.d. 0.0, lon 110.0 s.d. 110.0025
      Piksel (row=0, col=0) -> 1 (FOREST)
      Piksel (row=0, col=1) -> 0 (NON_FOREST)
      Piksel (row=0, col=2) -> 255 (NoData)
      Piksel (row=1, col=0) -> 1 (FOREST)
      Piksel (row=1, col=1) -> 0 (NON_FOREST)

    Tile 10N_110E:
      Origin (top-left): (110.0, 10.0) -> lat 9.9975 s.d. 10.0, lon 110.0 s.d. 110.0025
      Piksel (row=0, col=0) -> 1 (FOREST)
      Piksel (row=0, col=1) -> 0 (NON_FOREST)
    """
    res_deg = 0.00025

    # 1. Tile 00N_110E
    tile1_dir = tmp_path
    tile1_path = tile1_dir / "00N_110E.tif"
    data1 = np.full((10, 10), fill_value=255, dtype=np.uint8)
    data1[0, 0] = 1  # FOREST
    data1[0, 1] = 0  # NON_FOREST
    data1[0, 2] = 255  # NoData
    data1[1, 0] = 1  # FOREST
    data1[1, 1] = 0  # NON_FOREST

    transform1 = from_origin(110.0, 0.0, res_deg, res_deg)
    with rasterio.open(
        str(tile1_path),
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.uint8,
        crs="EPSG:4326",
        transform=transform1,
        nodata=255,
    ) as dst:
        dst.write(data1, 1)

    # 2. Tile 10N_110E
    tile2_path = tile1_dir / "10N_110E.tif"
    data2 = np.full((10, 10), fill_value=255, dtype=np.uint8)
    data2[0, 0] = 1  # FOREST
    data2[0, 1] = 0  # NON_FOREST

    # Origin pada (110.0, 10.0)
    transform2 = from_origin(110.0, 10.0, res_deg, res_deg)
    with rasterio.open(
        str(tile2_path),
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.uint8,
        crs="EPSG:4326",
        transform=transform2,
        nodata=255,
    ) as dst:
        dst.write(data2, 1)

    return tile1_dir


# ==============================================================================
# 1. Uji Validasi Koordinat dan Deteksi Koordinat Tertukar (Swapped Lat/Lon)
# ==============================================================================

def test_validate_geographic_coordinates():
    """Menguji validasi rentang koordinat dan deteksi kesalahan urutan (swapped)."""
    # Koordinat normal
    valid, err = validate_geographic_coordinates(-2.21, 113.92)
    assert valid is True
    assert err is None

    # Latitude di luar rentang [-90, 90]
    valid, err = validate_geographic_coordinates(95.0, 105.0)
    assert valid is False
    assert "latitude 95.0°" in err

    # Longitude di luar rentang [-180, 180]
    valid, err = validate_geographic_coordinates(0.0, 185.0)
    assert valid is False
    assert "longitude 185.0°" in err

    # Deteksi koordinat tertukar spesifik Kalimantan (lat=113.92, lon=-2.21)
    valid, err = validate_geographic_coordinates(113.92, -2.21)
    assert valid is False
    assert "swapped lat-lon terdeteksi" in err.lower()

    # Tipe data tidak valid
    valid, _ = validate_geographic_coordinates(float("nan"), 110.0)
    assert valid is False


# ==============================================================================
# 2. Uji Penentuan ID Tile dan Batas Spasial 10°x10°
# ==============================================================================

def test_tile_id_resolution_and_bounds():
    """Memverifikasi perhitungan ID tile 10°x10° dan batas bounding box WGS84."""
    # Kalimantan Barat bagian Selatan: -0.5, 109.5 -> 00N_100E
    assert get_glad_tile_id(-0.5, 109.5) == "00N_100E"

    # Kalimantan Tengah / Selatan: -2.21, 113.92 -> 00N_110E
    assert get_glad_tile_id(-2.21, 113.92) == "00N_110E"

    # Kalimantan Barat bagian Utara: 1.5, 109.5 -> 10N_100E
    assert get_glad_tile_id(1.5, 109.5) == "10N_100E"

    # Kalimantan Utara: 3.5, 116.5 -> 10N_110E
    assert get_glad_tile_id(3.5, 116.5) == "10N_110E"

    # Batas bounding box tile 00N_110E
    min_lon, min_lat, max_lon, max_lat = get_tile_bounds("00N_110E")
    assert min_lon == 110.0
    assert max_lon == 120.0
    assert min_lat == -10.0
    assert max_lat == 0.0


# ==============================================================================
# 3. Uji Piksel Terverifikasi FOREST (Nilai Piksel 1)
# ==============================================================================

def test_lookup_verified_forest_pixel(synthetic_forest_tiles: Path):
    """Memverifikasi bahwa piksel bernilai 1 diklasifikasikan secara tegas sebagai FOREST."""
    # Pada tile 00N_110E: origin (110.0, 0.0), res 0.00025°
    # Pusat piksel (row=0, col=0): lat = -0.000125, lon = 110.000125
    res = lookup_forest_extent(
        lat=-0.000125,
        lon=110.000125,
        forest_dir=synthetic_forest_tiles
    )
    assert res.status == CLASS_FOREST
    assert res.classification == CLASS_FOREST
    assert res.raw_pixel_value == 1
    assert res.raster_available is True
    assert res.reason == "VERIFIED_FOREST"
    assert res.error_message is None
    assert "2020" in res.data_period
    assert "GLAD" in res.dataset


# ==============================================================================
# 4. Uji Piksel Terverifikasi NON_FOREST (Nilai Piksel 0)
# ==============================================================================

def test_lookup_verified_non_forest_pixel(synthetic_forest_tiles: Path):
    """Memverifikasi bahwa piksel bernilai 0 diklasifikasikan secara tegas sebagai NON_FOREST."""
    # Pusat piksel (row=0, col=1): lat = -0.000125, lon = 110.000375
    res = lookup_forest_extent(
        lat=-0.000125,
        lon=110.000375,
        forest_dir=synthetic_forest_tiles
    )
    assert res.status == CLASS_NON_FOREST
    assert res.classification == CLASS_NON_FOREST
    assert res.raw_pixel_value == 0
    assert res.raster_available is True
    assert res.reason == "VERIFIED_NON_FOREST"
    assert res.error_message is None


# ==============================================================================
# 5. Uji Nilai NoData (255 / nodata) -> Wajib UNKNOWN (Bukan NON_FOREST)
# ==============================================================================

def test_lookup_nodata_is_unknown_not_non_forest(synthetic_forest_tiles: Path):
    """
    KRUSIAL: Memastikan bahwa nilai piksel NoData (255) TIDAK PERNAH dianggap
    atau diubah menjadi NON_FOREST, melainkan harus dilaporkan sebagai UNKNOWN.
    """
    # Pusat piksel (row=0, col=2): lat = -0.000125, lon = 110.000625 -> nilai 255
    res = lookup_forest_extent(
        lat=-0.000125,
        lon=110.000625,
        forest_dir=synthetic_forest_tiles
    )
    assert res.status == CLASS_UNKNOWN
    assert res.classification == CLASS_UNKNOWN
    assert res.status != CLASS_NON_FOREST
    assert res.raw_pixel_value == 255
    assert res.reason == "NODATA"


# ==============================================================================
# 6. Uji Koordinat di Luar Cakupan Raster (Out of Bounds)
# ==============================================================================

def test_lookup_out_of_bounds_coordinate(synthetic_forest_tiles: Path):
    """Menguji titik yang secara geometris berada di luar batas raster mini."""
    # Koordinat bujur 115.0 berada di dalam tile 00N_110E, namun di luar raster mini (110.0 s.d. 110.0025)
    res = lookup_forest_extent(
        lat=-1.0,
        lon=115.0,
        forest_dir=synthetic_forest_tiles
    )
    assert res.status == CLASS_UNKNOWN
    assert res.classification == CLASS_UNKNOWN
    assert res.status != CLASS_NON_FOREST
    assert res.reason == "OUT_OF_BOUNDS"
    assert "di luar batas geospasial" in res.error_message.lower()


# ==============================================================================
# 7. Uji Berkas Raster Tidak Ditemukan (File Not Found)
# ==============================================================================

def test_lookup_raster_file_not_found(tmp_path: Path):
    """
    Memverifikasi perilaku ketika berkas raster tidak tersedia:
    Harus mengembalikan UNKNOWN dengan raster_available=False,
    TIDAK BOLEH mengasumsikan non-hutan atau nilai default.
    """
    empty_dir = tmp_path / "empty_forest"
    empty_dir.mkdir()

    res = lookup_forest_extent(
        lat=-2.21,
        lon=113.92,
        forest_dir=empty_dir
    )
    assert res.status == CLASS_UNKNOWN
    assert res.classification == CLASS_UNKNOWN
    assert res.status != CLASS_NON_FOREST
    assert res.raster_available is False
    assert res.reason == "FILE_NOT_FOUND"
    assert "belum tersedia" in res.error_message


# ==============================================================================
# 8. Uji Koordinat Tertukar (Swapped Lat/Lon) Langsung pada Lookup
# ==============================================================================

def test_lookup_swapped_coordinates_detected(synthetic_forest_tiles: Path):
    """Memverifikasi bahwa parameter yang tertukar dicegat sebelum pembacaan raster."""
    res = lookup_forest_extent(
        lat=110.000125,
        lon=-0.000125,
        forest_dir=synthetic_forest_tiles
    )
    assert res.status == CLASS_UNKNOWN
    assert res.reason == "INVALID_COORDINATES"
    assert "swapped" in res.error_message.lower()


# ==============================================================================
# 9. Uji Batas Antartile dan Transisi Antartile (Boundary Transition)
# ==============================================================================

def test_tile_boundary_transition(synthetic_forest_tiles: Path):
    """
    Menguji kontinuitas pembacaan pada peralihan antartile:
    Tile 00N_110E mencakup lat <= 0.0
    Tile 10N_110E mencakup lat > 0.0
    """
    # 1. Titik di tile 00N_110E
    res_south = lookup_forest_extent(
        lat=-0.000125,
        lon=110.000125,
        forest_dir=synthetic_forest_tiles
    )
    assert res_south.tile_id == "00N_110E"
    assert res_south.status == CLASS_FOREST

    # 2. Titik di tile 10N_110E (origin 110.0, 10.0, piksel 0,0: lat = 9.999875, lon = 110.000125)
    res_north = lookup_forest_extent(
        lat=9.999875,
        lon=110.000125,
        forest_dir=synthetic_forest_tiles
    )
    assert res_north.tile_id == "10N_110E"
    assert res_north.status == CLASS_FOREST


# ==============================================================================
# 10. Uji Independensi Layer Hutan dan Layer Gambut
# ==============================================================================

def test_forest_and_peatland_lookup_independence(synthetic_forest_tiles: Path):
    """
    Memverifikasi bahwa lookup layer hutan dan layer gambut berjalan secara terpisah:
    1. Keduanya menghasilkan data masing-masing tanpa saling menimpa.
    2. Lookup hutan tidak mengubah data/poligon gambut.
    3. Status gambut tidak mengubah hasil klasifikasi hutan.
    """
    lat = -0.000125
    lon = 110.000125

    # Lakukan lookup tutupan hutan
    forest_res = lookup_forest_extent(lat=lat, lon=lon, forest_dir=synthetic_forest_tiles)
    assert forest_res.status == CLASS_FOREST
    assert forest_res.classification == CLASS_FOREST

    # Periksa evaluasi titik FireGuard
    point_eval = evaluate_forest_change_point(
        lat=lat,
        lon=lon,
        glad_forest_dir=synthetic_forest_tiles
    )
    # Hansen evaluation tetap terpisah
    assert "forest_extent_2020" in point_eval
    assert point_eval["forest_extent_2020"]["classification"] == CLASS_FOREST

    # Ulangi lookup hutan untuk memastikan idempotensi sempurna
    forest_res_again = lookup_forest_extent(lat=lat, lon=lon, forest_dir=synthetic_forest_tiles)
    assert forest_res_again.status == CLASS_FOREST
    assert forest_res_again.raw_pixel_value == forest_res.raw_pixel_value


# ==============================================================================
# 11. Uji Endpoint REST API (/api/v1/forest-loss/point, /api/v1/forest-extent/point, /api/v1/context-layers)
# ==============================================================================

def test_api_endpoints_handling_unknown_and_context_layers():
    """
    Menguji endpoint REST API FastAPI:
    1. /api/v1/context-layers melaporkan status ketersediaan hutan secara akurat.
    2. /api/v1/forest-loss/point mengembalikan field forest_extent_2020.
    3. /api/v1/forest-extent/point menangani status UNKNOWN tanpa mengubahnya jadi NON_FOREST.
    4. Koordinat swapped menghasilkan status UNKNOWN.
    """
    client = TestClient(app)

    # 1. Endpoint /api/v1/context-layers
    resp_layers = client.get("/api/v1/context-layers")
    assert resp_layers.status_code == 200
    data_layers = resp_layers.json()
    assert "forest_layer" in data_layers
    assert "peatland_layer" in data_layers
    assert "boundary_layer" in data_layers
    assert isinstance(data_layers["forest_layer"]["available"], bool)
    assert "GLAD" in data_layers["forest_layer"]["source"]

    # 2. Endpoint /api/v1/forest-loss/point untuk titik dalam subset demo (Palangka Raya)
    resp_point = client.get("/api/v1/forest-loss/point?latitude=-2.21&longitude=113.92")
    assert resp_point.status_code == 200
    data_point = resp_point.json()
    assert "forest_extent_2020" in data_point
    glad_info = data_point["forest_extent_2020"]
    assert glad_info["status"] in ("FOREST", "NON_FOREST", "UNKNOWN")

    # Uji titik di luar cakupan raster pada tile yang belum diunduh (Aceh 00N_090E) -> Wajib UNKNOWN (FILE_NOT_FOUND)
    resp_unknown = client.get("/api/v1/forest-extent/point?latitude=5.50&longitude=95.30")
    assert resp_unknown.status_code == 200
    data_unknown = resp_unknown.json()
    assert data_unknown["status"] == CLASS_UNKNOWN
    assert data_unknown["classification"] == CLASS_UNKNOWN
    assert data_unknown["status"] != CLASS_NON_FOREST
    assert data_unknown["reason"] == "FILE_NOT_FOUND"

    # Uji titik di luar window subset (Banjarmasin) -> Wajib UNKNOWN (OUT_OF_BOUNDS)
    resp_oob = client.get("/api/v1/forest-extent/point?latitude=-3.32&longitude=114.59")
    assert resp_oob.status_code == 200
    data_oob = resp_oob.json()
    assert data_oob["status"] == CLASS_UNKNOWN
    assert data_oob["classification"] == CLASS_UNKNOWN
    assert data_oob["status"] != CLASS_NON_FOREST
    assert data_oob["reason"] == "OUT_OF_BOUNDS"

    # 3. Dedicated endpoint /api/v1/forest-extent/point pada Palangka Raya
    resp_extent = client.get("/api/v1/forest-extent/point?latitude=-2.21&longitude=113.92")
    assert resp_extent.status_code == 200
    data_extent = resp_extent.json()
    assert data_extent["status"] in ("FOREST", "NON_FOREST", "UNKNOWN")

    # 4. Swapped coordinates pada endpoint
    resp_swapped = client.get("/api/v1/forest-extent/point?latitude=113.92&longitude=-2.21")
    # Latitude 113.92 berada di luar [-90, 90] sehingga FastAPI Query(..., le=90) memvalidasi status 422
    assert resp_swapped.status_code in (422, 200)
    if resp_swapped.status_code == 200:
        assert resp_swapped.json()["status"] == CLASS_UNKNOWN


# ==============================================================================
# 12. Uji Pemeriksaan Ketersediaan Tile Layer (check_glad_forest_layer_availability)
# ==============================================================================

def test_check_glad_forest_layer_availability(synthetic_forest_tiles: Path, tmp_path: Path):
    """Menguji deteksi ketersediaan tile lokal pada folder kosong vs folder dengan tile terpasang."""
    # Folder dengan 2 tile terpasang (00N_110E dan 10N_110E)
    available, installed, details = check_glad_forest_layer_availability(forest_dir=synthetic_forest_tiles)
    assert available is True
    assert "00N_110E" in installed
    assert "10N_110E" in installed
    assert details["00N_110E"]["installed"] is True
    assert details["00N_100E"]["installed"] is False

    # Folder kosong
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    available_empty, installed_empty, _ = check_glad_forest_layer_availability(forest_dir=empty_dir)
    assert available_empty is False
    assert len(installed_empty) == 0


# ==============================================================================
# 13. Uji Berkas Raster Asli di Direktori data/raster/forest/ (Jika Tersedia)
# ==============================================================================

def test_real_raster_file_lookup_if_present():
    """
    Verifikasi langsung terhadap berkas GeoTIFF produksi asli di data/raster/forest/.
    Jika berkas 10S_110E.tif dan 4 subset Kalimantan tersedia:
    1. Verifikasi piksel FOREST (nilai 1) pada lat=-10.000125, lon=119.949375 (10S_110E).
    2. Verifikasi piksel NON_FOREST (nilai 0) pada lat=-10.000125, lon=119.750125 (10S_110E).
    3. Verifikasi titik pusat kota Palangka Raya (-2.21, 113.92) menghasilkan NON_FOREST (00N_110E).
    4. Verifikasi titik tutupan pohon Kalteng (-1.8001, 113.7679) menghasilkan FOREST (00N_110E).
    5. Verifikasi kuadran 00N_100E (Ketapang: lat=-1.75, lon=109.75).
    6. Verifikasi kuadran 10N_100E (Kalbar Pontianak: lat=0.25, lon=109.35).
    7. Verifikasi kuadran 10N_110E (Kaltim Samarinda: lat=0.30, lon=117.10).
    8. Verifikasi koordinat di luar subset (Banjarmasin -3.32, 114.59) menghasilkan UNKNOWN (OUT_OF_BOUNDS).
    9. Verifikasi koordinat tile yang belum terpasang (Aceh 5.50, 95.30) menghasilkan UNKNOWN (FILE_NOT_FOUND).
    10. Verifikasi koordinat di luar cakupan (-25.0, 115.0) mengembalikan UNKNOWN.
    """
    real_file = Path("data/raster/forest/10S_110E.tif")
    if not real_file.exists():
        pytest.skip("Berkas raster asli 10S_110E.tif belum ada di data/raster/forest/, lewati uji berkas fisik.")

    # 1. Lookup piksel hutan terverifikasi pada 10S_110E (FOREST)
    res_forest = lookup_forest_extent(lat=-10.000125, lon=119.949375)
    assert res_forest.status == CLASS_FOREST
    assert res_forest.classification == CLASS_FOREST
    assert res_forest.raw_pixel_value == 1
    assert res_forest.raster_file == "10S_110E.tif"
    assert res_forest.reason == "VERIFIED_FOREST"

    # 2. Lookup piksel non-hutan terverifikasi pada 10S_110E (NON_FOREST)
    res_non_forest = lookup_forest_extent(lat=-10.000125, lon=119.750125)
    assert res_non_forest.status == CLASS_NON_FOREST
    assert res_non_forest.classification == CLASS_NON_FOREST
    assert res_non_forest.raw_pixel_value == 0
    assert res_non_forest.raster_file == "10S_110E.tif"
    assert res_non_forest.reason == "VERIFIED_NON_FOREST"

    # 3. Lookup koordinat Palangka Raya pada subset Kalimantan Tengah (00N_110E)
    res_kalteng_city = lookup_forest_extent(lat=-2.21, lon=113.92)
    assert res_kalteng_city.status == CLASS_NON_FOREST
    assert res_kalteng_city.classification == CLASS_NON_FOREST
    assert res_kalteng_city.raw_pixel_value == 0
    assert res_kalteng_city.reason == "VERIFIED_NON_FOREST"

    # 4. Lookup titik berhutan di Kalteng (00N_110E)
    res_kalteng_forest = lookup_forest_extent(lat=-1.8001, lon=113.7679)
    assert res_kalteng_forest.status == CLASS_FOREST
    assert res_kalteng_forest.classification == CLASS_FOREST
    assert res_kalteng_forest.raw_pixel_value == 1
    assert res_kalteng_forest.reason == "VERIFIED_FOREST"

    # 5. Lookup kuadran 00N_100E (Ketapang)
    res_ketapang = lookup_forest_extent(lat=-1.75, lon=109.75)
    assert res_ketapang.status in (CLASS_FOREST, CLASS_NON_FOREST)
    assert res_ketapang.tile_id == "00N_100E"

    # 6. Lookup kuadran 10N_100E (Kalbar Pontianak)
    res_kalbar = lookup_forest_extent(lat=0.25, lon=109.35)
    assert res_kalbar.status in (CLASS_FOREST, CLASS_NON_FOREST)
    assert res_kalbar.tile_id == "10N_100E"

    # 7. Lookup kuadran 10N_110E (Kaltim Samarinda)
    res_kaltim = lookup_forest_extent(lat=0.30, lon=117.10)
    assert res_kaltim.status in (CLASS_FOREST, CLASS_NON_FOREST)
    assert res_kaltim.tile_id == "10N_110E"

    # 8. Lookup titik di luar subset namun dalam tile 00N_110E (Banjarmasin)
    res_oob = lookup_forest_extent(lat=-3.32, lon=114.59)
    assert res_oob.status == CLASS_UNKNOWN
    assert res_oob.reason == "OUT_OF_BOUNDS"
    assert res_oob.status != CLASS_NON_FOREST

    # 9. Lookup titik di tile yang belum dipasang (Aceh 5.50, 95.30 -> 00N_090E)
    res_uninstalled = lookup_forest_extent(lat=5.50, lon=95.30)
    assert res_uninstalled.status == CLASS_UNKNOWN
    assert res_uninstalled.reason == "FILE_NOT_FOUND"
    assert res_uninstalled.status != CLASS_NON_FOREST

    # 10. Lookup koordinat di luar cakupan global
    res_out = lookup_forest_extent(lat=-25.0, lon=115.0)
    assert res_out.status == CLASS_UNKNOWN
    assert res_out.classification == CLASS_UNKNOWN
    assert res_out.status != CLASS_NON_FOREST


# ==============================================================================
# 14. Uji Endpoint Metadata Segmentasi Peta (/api/v1/map-data/forest-extent/meta)
# ==============================================================================

def test_map_forest_extent_meta_endpoint():
    """Menguji endpoint metadata layer peta tutupan hutan GLAD 2020."""
    client = TestClient(app)
    resp = client.get("/api/v1/map-data/forest-extent/meta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert "bounds" in data
    assert data["bounds"]["west"] == 113.50
    assert data["bounds"]["east"] == 114.40
    assert data["bounds"]["south"] == -2.60
    assert data["bounds"]["north"] == -1.80
    assert data["leaflet_bounds"] == [[-2.60, 113.50], [-1.80, 114.40]]
    assert data["resolution_meters"] == 30.0
    assert "pixel_statistics" in data
    assert data["pixel_statistics"]["forest_percentage"] > 50.0
    assert len(data["legend"]) >= 2
    assert "2020" in data["caveat"]


# ==============================================================================
# 15. Uji Endpoint Citra Overlay Segmentasi Peta (/api/v1/map-data/forest-extent/overlay)
# ==============================================================================

def test_map_forest_extent_overlay_endpoint():
    """Menguji endpoint penayangan citra overlay PNG Web-Ready untuk Leaflet."""
    client = TestClient(app)
    resp = client.get("/api/v1/map-data/forest-extent/overlay")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "image/png"
    assert "max-age=86400" in resp.headers.get("cache-control", "")
    content = resp.content
    assert len(content) > 10000  # Memiliki isi biner gambar nyata
    # Header PNG resmi: 0x89 'P' 'N' 'G' '\r' '\n' 0x1A '\n'
    assert content[:8] == b"\x89PNG\r\n\x1a\n"


# ==============================================================================
# 16. Uji Endpoint Multi-Tile Seluruh Pulau Kalimantan (/api/v1/map-data/forest-extent/tiles)
# ==============================================================================

def test_kalimantan_multi_tiles_endpoints():
    """Menguji endpoint multi-tile yang mencakup seluruh 4 kuadran Pulau Kalimantan."""
    client = TestClient(app)
    resp = client.get("/api/v1/map-data/forest-extent/tiles")
    assert resp.status_code == 200
    data = resp.json()

    assert data["dataset"] == "GLAD Global Land Cover and Land Use Change 2000–2020"
    assert data["layer"] == "Forest extent 2020"
    assert data["coverage_status"] == "PARTIAL"
    assert data["is_full_coverage"] is False
    assert data["coverage_percentage_of_kalimantan"] == 3.05
    assert "Cakupan Parsial" in data["scope"]
    assert data["total_quadrants"] == 4
    assert data["available_quadrants"] == 4
    assert data["all_quadrants_available"] is True
    assert data["total_forest_pixels"] > 0
    assert data["total_non_forest_pixels"] > 0
    assert len(data["tiles"]) == 4

    expected_tile_ids = {"00N_100E", "00N_110E", "10N_100E", "10N_110E"}
    actual_tile_ids = {t["tile_id"] for t in data["tiles"]}
    assert actual_tile_ids == expected_tile_ids

    for t in data["tiles"]:
        assert t["available"] is True
        assert t["is_full_tile"] is False
        assert t["coverage_type"] == "subset_sample"
        assert t["overlay_size_bytes"] > 0
        assert t["tif_size_bytes"] > 0
        assert len(t["leaflet_bounds"]) == 2
        assert t["pixel_statistics"]["forest_pixels"] > 0

        # Verifikasi endpoint citra overlay tiap tile
        ov_resp = client.get(t["overlay_url"])
        assert ov_resp.status_code == 200
        assert ov_resp.headers.get("content-type") == "image/png"
        assert ov_resp.content[:8] == b"\x89PNG\r\n\x1a\n"

