"""
backend/app/glad_forest_reader.py
Modul Pembaca Raster GLAD Forest Extent 2020 (GLCLUC2020).

Mendukung pembacaan raster GeoTIFF tingkat piksel (resolusi 30 meter / 0.9 arc-second)
berdasarkan dataset resmi GLAD Global Land Cover and Land Use Change 2000–2020
(University of Maryland, Potapov et al., 2022).

Taksonomi Hasil Eksplisit:
- FOREST: Nilai piksel = 1 (tutupan pohon dengan kanopi >= 5 meter pada tahun 2020 menurut FAO FRA baseline).
- NON_FOREST: Nilai piksel = 0 (bukan tutupan hutan berkanopi >= 5 meter).
- UNKNOWN: NoData (255 / nodata), koordinat di luar cakupan raster, berkas tidak ditemukan,
  atau nilai tidak dapat diinterpretasikan.

Keterbatasan Ilmiah Wajib:
- Dataset ini merepresentasikan kondisi biofisik tutupan pohon tahun 2020, BUKAN kondisi real-time terkini.
- Nilai NoData TIDAK PERNAH dianggap sebagai non-hutan.
- Klasifikasi FOREST atau NON_FOREST tidak menyimpulkan status legalitas lahan atau jaminan bebas kebakaran.
"""

import math
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import rasterio
    from rasterio.errors import RasterioError, RasterioIOError
    from rasterio.windows import Window
    HAS_RASTERIO = True
except (ImportError, Exception):
    rasterio = None
    HAS_RASTERIO = False
    class RasterioError(Exception):
        pass
    class RasterioIOError(Exception):
        pass
    Window = None

from .config import GLAD_FOREST_DIR

# 4 Tile 10°x10° yang melingkupi seluruh 5 provinsi Kalimantan
KALIMANTAN_GLAD_TILES = {
    "00N_100E",  # Kalimantan Barat bagian Selatan (-10 s.d. 0, 100 s.d. 110)
    "00N_110E",  # Kalimantan Tengah, Kalimantan Selatan, Kalimantan Timur bagian Selatan (-10 s.d. 0, 110 s.d. 120)
    "10N_100E",  # Kalimantan Barat bagian Utara (0 s.d. 10, 100 s.d. 110)
    "10N_110E",  # Kalimantan Utara, Kalimantan Timur bagian Utara (0 s.d. 10, 110 s.d. 120)
}

# Taksonomi status dan klasifikasi eksplisit
CLASS_FOREST = "FOREST"
CLASS_NON_FOREST = "NON_FOREST"
CLASS_UNKNOWN = "UNKNOWN"

VALID_CLASSES = {CLASS_FOREST, CLASS_NON_FOREST, CLASS_UNKNOWN}

# Nilai piksel resmi
PIXEL_FOREST_VALUE = 1
PIXEL_NON_FOREST_VALUE = 0
PIXEL_NODATA_DEFAULT = 255

# Resolusi spasial
GLAD_PIXEL_DEGREES = 0.00025  # ~30 meter pada ekuator
GLAD_DATASET_NAME = "GLAD Global Land Cover and Land Use Change 2000–2020"
GLAD_LAYER_NAME = "Forest extent 2020"
GLAD_DATA_PERIOD = "2020"
GLAD_RESOLUTION_M = 30.0

SCIENTIFIC_CAVEAT_FOREST = (
    "Klasifikasi tutupan pohon GLAD 2020 merepresentasikan kondisi biofisik kanopi tahun 2020 "
    "(tinggi >= 5m) dan tidak secara otomatis menyimpulkan legalitas lahan atau ketiadaan risiko kebakaran."
)

_CACHE_LOCK = threading.Lock()
_PIXEL_CACHE: Dict[str, "GladForestPixelResult"] = {}
_MAX_CACHE_ENTRIES = 10000


@dataclass
class GladForestPixelResult:
    """Struktur data hasil pembacaan piksel raster GLAD Forest Extent 2020."""
    status: str  # FOREST, NON_FOREST, UNKNOWN
    classification: str  # FOREST, NON_FOREST, UNKNOWN
    raw_pixel_value: Optional[int]
    latitude: float
    longitude: float
    tile_id: Optional[str] = None
    pixel_row: Optional[int] = None
    pixel_col: Optional[int] = None
    raster_available: bool = False
    raster_file: Optional[str] = None
    crs: Optional[str] = None
    dataset: str = GLAD_DATASET_NAME
    layer: str = GLAD_LAYER_NAME
    data_period: str = GLAD_DATA_PERIOD
    resolution_m: float = GLAD_RESOLUTION_M
    definition: str = "Tutupan pohon tinggi >= 5m (FAO FRA baseline, UMD GLCLUC2020)"
    scientific_caveat: str = SCIENTIFIC_CAVEAT_FOREST
    error_message: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konversi ke dictionary yang ramah serialisasi JSON."""
        return asdict(self)


def validate_geographic_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """
    Memvalidasi batas koordinat geografis WGS84:
    - Latitude harus berada di antara -90.0 dan +90.0.
    - Longitude harus berada di antara -180.0 dan +180.0.
    - Mendeteksi apakah koordinat tertukar (swapped lat/lon).
    """
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False, "Koordinat latitude dan longitude harus berupa angka numerik."

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False, "Koordinat tidak boleh bernilai NaN atau tak hingga."

    # Deteksi terbalik: jika lat > 90 atau lat < -90, namun lon di rentang [-90, 90]
    if (lat < -90.0 or lat > 90.0) and (-90.0 <= lon <= 90.0):
        return (
            False,
            f"Koordinat terbalik (swapped lat-lon terdeteksi): Latitude {lat}° berada di luar [-90, 90], "
            f"sementara Longitude {lon}° berada di rentang latitude valid."
        )

    # Deteksi spesifik Kalimantan jika tertukar: lat ~ 110, lon ~ -2
    if 95.0 <= lat <= 141.0 and -11.0 <= lon <= 6.0:
        return (
            False,
            f"Koordinat terbalik (swapped lat-lon terdeteksi untuk wilayah Indonesia): "
            f"Latitude {lat}° terindikasi sebagai Longitude, dan Longitude {lon}° terindikasi sebagai Latitude."
        )

    if lat < -90.0 or lat > 90.0:
        return False, f"Nilai latitude {lat}° berada di luar rentang valid [-90.0, 90.0]."

    if lon < -180.0 or lon > 180.0:
        return False, f"Nilai longitude {lon}° berada di luar rentang valid [-180.0, 180.0]."

    return True, None


def get_glad_tile_id(lat: float, lon: float) -> str:
    """
    Menentukan ID tile 10°x10° GLAD/Hansen berdasarkan koordinat (lat, lon).
    Menggunakan koordinat sudut kiri-atas (north-west corner) dari tile 10°x10°.

    Contoh:
    - lat: -2.21, lon: 110.09 -> top lat: 00N, left lon: 110E -> '00N_110E'
    - lat:  1.55, lon: 110.35 -> top lat: 10N, left lon: 110E -> '10N_110E'
    - lat: -0.05, lon: 109.34 -> top lat: 00N, left lon: 100E -> '00N_100E'
    - lat:  0.00, lon: 110.00 (batas tepat): top lat: 00N jika lat <= 0, atau 10N jika lat > 0.
    """
    if lat == 0.0:
        top_lat = 0
    elif lat > 0:
        top_lat = int(math.ceil(lat / 10.0) * 10)
    else:
        top_lat = int(math.ceil(lat / 10.0) * 10)

    left_lon = int(math.floor(lon / 10.0) * 10)

    lat_prefix = f"{abs(top_lat):02d}N" if top_lat >= 0 else f"{abs(top_lat):02d}S"
    lon_prefix = f"{abs(left_lon):03d}E" if left_lon >= 0 else f"{abs(left_lon):03d}W"

    return f"{lat_prefix}_{lon_prefix}"


def get_tile_bounds(tile_id: str) -> Tuple[float, float, float, float]:
    """
    Menghitung batas geografis (min_lon, min_lat, max_lon, max_lat) untuk ID tile 10°x10°.
    """
    parts = tile_id.split("_")
    if len(parts) != 2:
        raise ValueError(f"Format tile_id tidak valid: {tile_id}")

    lat_str, lon_str = parts[0], parts[1]
    top_lat = int(lat_str[:2]) if "N" in lat_str else -int(lat_str[:2])
    left_lon = int(lon_str[:3]) if "E" in lon_str else -int(lon_str[:3])

    min_lat = top_lat - 10.0
    max_lat = float(top_lat)
    min_lon = float(left_lon)
    max_lon = left_lon + 10.0

    return (min_lon, min_lat, max_lon, max_lat)


def find_glad_raster_file(
    tile_id: str,
    forest_dir: Optional[Union[str, Path]] = None
) -> Optional[Path]:
    """
    Mencari berkas GeoTIFF raster GLAD Forest Extent 2020 lokal untuk tile_id.
    Memeriksa berbagai konvensi penamaan yang valid, baik pada direktori utama
    maupun subdirektori (seperti data/raster/forest/kalimantan/).
    """
    dir_path = Path(forest_dir) if forest_dir else GLAD_FOREST_DIR
    if not dir_path.exists() or not dir_path.is_dir():
        return None

    # Folder pencarian: subfolder tiles_full (prioritas utama), direktori utama, dan subfolder kalimantan
    search_dirs = []
    tiles_full_sub = dir_path / "tiles_full"
    if tiles_full_sub.exists() and tiles_full_sub.is_dir():
        search_dirs.append(tiles_full_sub)
    search_dirs.append(dir_path)
    kalimantan_sub = dir_path / "kalimantan"
    if kalimantan_sub.exists() and kalimantan_sub.is_dir():
        search_dirs.append(kalimantan_sub)

    # Nama kandidat berurutan (prioritaskan full tile sebelum demo/subset)
    candidate_names = [
        f"{tile_id}.tif",
        f"{tile_id}.tiff",
        f"Forest_extent_2020_{tile_id}.tif",
        f"Forest_extent_2020_{tile_id}.tiff",
        f"GLCLUC2020_Forest_extent_2020_{tile_id}.tif",
        f"GLAD_Forest_extent_2020_{tile_id}.tif",
        f"GLAD_Forest_extent_2020_{tile_id}_kalteng_demo.tif",
        f"Forest_extent_2020_{tile_id}_kalteng_demo.tif",
        f"{tile_id}_kalteng_demo.tif",
        f"{tile_id}_subset.tif",
    ]

    for s_dir in search_dirs:
        for name in candidate_names:
            cand = s_dir / name
            if cand.is_file():
                part_file = Path(str(cand) + ".part")
                if not part_file.exists():
                    return cand

    # Pencarian pola dinamis jika belum ditemukan
    for s_dir in search_dirs:
        for cand in sorted(s_dir.glob(f"*{tile_id}*.tif*")):
            if not cand.name.endswith(".part") and cand.is_file():
                return cand

    return None


def is_coordinate_within_kalimantan_bbox(lat: float, lon: float) -> bool:
    """
    Memeriksa apakah koordinat berada dalam batas kasar wilayah Kalimantan
    (lat: -5.5 s.d. 5.5, lon: 108.0 s.d. 120.0).
    """
    return (-5.5 <= lat <= 5.5) and (108.0 <= lon <= 120.0)


def lookup_forest_extent(
    lat: float,
    lon: float,
    forest_dir: Optional[Union[str, Path]] = None,
    use_cache: bool = True
) -> GladForestPixelResult:
    """
    Melakukan pencarian (lookup) klasifikasi tutupan hutan GLAD Forest Extent 2020
    berdasarkan koordinat geografis (lat, lon).

    Alur Verifikasi:
    1. Validasi keabsahan koordinat (range dan deteksi swapped lat/lon).
    2. Periksa cache memori thread-safe jika use_cache=True.
    3. Tentukan tile 10°x10° yang mencakup koordinat.
    4. Cari berkas raster GeoTIFF lokal. Jika tidak ada, kembalikan status UNKNOWN
       dengan data_available=False (tidak boleh default ke non-hutan).
    5. Buka berkas raster dengan rasterio dan verifikasi batas bounding box spasial.
    6. Lakukan windowed reading (1 piksel) pada koordinat terkait.
    7. Periksa nilai piksel terhadap NoData (255 / nodata) -> UNKNOWN.
    8. Petakan nilai piksel 1 -> FOREST, 0 -> NON_FOREST.
    """
    # 1. Validasi koordinat
    is_valid, err_msg = validate_geographic_coordinates(lat, lon)
    if not is_valid:
        return GladForestPixelResult(
            status=CLASS_UNKNOWN,
            classification=CLASS_UNKNOWN,
            raw_pixel_value=None,
            latitude=lat,
            longitude=lon,
            error_message=err_msg,
            reason="INVALID_COORDINATES",
            raster_available=False
        )

    # 2. Cek cache
    dir_key = str(Path(forest_dir).resolve()) if forest_dir else str(GLAD_FOREST_DIR.resolve())
    cache_key = f"{lat:.6f}_{lon:.6f}_{dir_key}"
    if use_cache:
        with _CACHE_LOCK:
            if cache_key in _PIXEL_CACHE:
                return _PIXEL_CACHE[cache_key]

    # 3. Tentukan tile_id
    tile_id = get_glad_tile_id(lat, lon)

    # 4. Cari berkas raster
    raster_path = find_glad_raster_file(tile_id, forest_dir=forest_dir)
    if raster_path is None:
        result = GladForestPixelResult(
            status=CLASS_UNKNOWN,
            classification=CLASS_UNKNOWN,
            raw_pixel_value=None,
            latitude=lat,
            longitude=lon,
            tile_id=tile_id,
            raster_available=False,
            error_message=f"Berkas raster GLAD Forest Extent 2020 untuk tile '{tile_id}' belum tersedia di direktori lokal.",
            reason="FILE_NOT_FOUND"
        )
        if use_cache:
            with _CACHE_LOCK:
                if len(_PIXEL_CACHE) < _MAX_CACHE_ENTRIES:
                    _PIXEL_CACHE[cache_key] = result
        return result

    if not HAS_RASTERIO or rasterio is None:
        result = GladForestPixelResult(
            status=CLASS_UNKNOWN,
            classification=CLASS_UNKNOWN,
            raw_pixel_value=None,
            latitude=lat,
            longitude=lon,
            tile_id=tile_id,
            raster_available=False,
            error_message="Library rasterio tidak tersedia di environment server.",
            reason="RASTERIO_UNAVAILABLE"
        )
        if use_cache:
            with _CACHE_LOCK:
                if len(_PIXEL_CACHE) < _MAX_CACHE_ENTRIES:
                    _PIXEL_CACHE[cache_key] = result
        return result

    # 5 & 6. Buka GeoTIFF dan baca piksel melalui windowed reading
    try:
        with rasterio.open(str(raster_path)) as src:
            bounds = src.bounds
            crs_str = src.crs.to_string() if src.crs else "EPSG:4326"

            # Periksa apakah titik berada di dalam batas raster bounding box
            if not (
                (bounds.left - 1e-9) <= lon <= (bounds.right + 1e-9)
                and (bounds.bottom - 1e-9) <= lat <= (bounds.top + 1e-9)
            ):
                result = GladForestPixelResult(
                    status=CLASS_UNKNOWN,
                    classification=CLASS_UNKNOWN,
                    raw_pixel_value=None,
                    latitude=lat,
                    longitude=lon,
                    tile_id=tile_id,
                    raster_available=True,
                    raster_file=raster_path.name,
                    crs=crs_str,
                    error_message=f"Koordinat ({lat}, {lon}) berada di luar batas geospasial raster {raster_path.name}.",
                    reason="OUT_OF_BOUNDS"
                )
                return result

            # Konversi koordinat geografis ke indeks baris/kolom piksel
            row, col = src.index(lon, lat)

            row = max(0, min(row, src.height - 1))
            col = max(0, min(col, src.width - 1))

            window = Window(col_off=col, row_off=row, width=1, height=1)
            pixel_block = src.read(1, window=window)

            if pixel_block.size == 0:
                raw_val = None
            else:
                raw_val = int(pixel_block[0, 0])

            # Periksa NoData
            nodata_val = src.nodata
            is_nodata = (
                raw_val is None
                or (nodata_val is not None and raw_val == nodata_val)
                or raw_val == PIXEL_NODATA_DEFAULT
                or raw_val not in (PIXEL_FOREST_VALUE, PIXEL_NON_FOREST_VALUE)
            )

            if is_nodata:
                result = GladForestPixelResult(
                    status=CLASS_UNKNOWN,
                    classification=CLASS_UNKNOWN,
                    raw_pixel_value=raw_val,
                    latitude=lat,
                    longitude=lon,
                    tile_id=tile_id,
                    pixel_row=row,
                    pixel_col=col,
                    raster_available=True,
                    raster_file=raster_path.name,
                    crs=crs_str,
                    error_message="Nilai piksel raster adalah NoData atau tidak terdefinisi.",
                    reason="NODATA"
                )
            elif raw_val == PIXEL_FOREST_VALUE:
                result = GladForestPixelResult(
                    status=CLASS_FOREST,
                    classification=CLASS_FOREST,
                    raw_pixel_value=PIXEL_FOREST_VALUE,
                    latitude=lat,
                    longitude=lon,
                    tile_id=tile_id,
                    pixel_row=row,
                    pixel_col=col,
                    raster_available=True,
                    raster_file=raster_path.name,
                    crs=crs_str,
                    reason="VERIFIED_FOREST"
                )
            elif raw_val == PIXEL_NON_FOREST_VALUE:
                result = GladForestPixelResult(
                    status=CLASS_NON_FOREST,
                    classification=CLASS_NON_FOREST,
                    raw_pixel_value=PIXEL_NON_FOREST_VALUE,
                    latitude=lat,
                    longitude=lon,
                    tile_id=tile_id,
                    pixel_row=row,
                    pixel_col=col,
                    raster_available=True,
                    raster_file=raster_path.name,
                    crs=crs_str,
                    reason="VERIFIED_NON_FOREST"
                )
            else:
                result = GladForestPixelResult(
                    status=CLASS_UNKNOWN,
                    classification=CLASS_UNKNOWN,
                    raw_pixel_value=raw_val,
                    latitude=lat,
                    longitude=lon,
                    tile_id=tile_id,
                    pixel_row=row,
                    pixel_col=col,
                    raster_available=True,
                    raster_file=raster_path.name,
                    crs=crs_str,
                    error_message=f"Nilai piksel '{raw_val}' tidak dapat diinterpretasikan menurut skema biner 0/1.",
                    reason="UNINTERPRETED_VALUE"
                )

    except (RasterioError, RasterioIOError, Exception) as exc:
        result = GladForestPixelResult(
            status=CLASS_UNKNOWN,
            classification=CLASS_UNKNOWN,
            raw_pixel_value=None,
            latitude=lat,
            longitude=lon,
            tile_id=tile_id,
            raster_available=True,
            raster_file=raster_path.name if raster_path else None,
            error_message=f"Kegagalan pembacaan raster: {str(exc)}",
            reason="READ_ERROR"
        )

    if use_cache:
        with _CACHE_LOCK:
            if len(_PIXEL_CACHE) < _MAX_CACHE_ENTRIES:
                _PIXEL_CACHE[cache_key] = result

    return result


def clear_forest_cache() -> None:
    """Membersihkan cache memori piksel raster hutan."""
    with _CACHE_LOCK:
        _PIXEL_CACHE.clear()


def check_glad_forest_layer_availability(
    forest_dir: Optional[Union[str, Path]] = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Memeriksa ketersediaan berkas raster GLAD Forest Extent 2020.
    Mengembalikan:
    - available: True jika minimal satu tile Kalimantan ditemukan.
    - installed_tiles: daftar nama tile yang berhasil ditemukan di direktori lokal.
    - details: informasi detail per tile (path, ukuran berkas, cakupan, status subset).
    """
    dir_path = Path(forest_dir) if forest_dir else GLAD_FOREST_DIR
    installed_tiles = []
    details = {}

    search_dirs = []
    tiles_full_sub = dir_path / "tiles_full"
    if tiles_full_sub.exists() and tiles_full_sub.is_dir():
        search_dirs.append(tiles_full_sub)
    search_dirs.append(dir_path)
    kalimantan_sub = dir_path / "kalimantan"
    if kalimantan_sub.exists() and kalimantan_sub.is_dir():
        search_dirs.append(kalimantan_sub)

    # 1. Pindai berkas .tif di direktori raster
    for s_dir in search_dirs:
        if not s_dir.exists() or not s_dir.is_dir():
            continue
        for file in sorted(s_dir.glob("*.tif*")):
            if file.name.endswith(".part"):
                continue
            m = re.search(r"(\d{2}[NS]_\d{3}[EW])", file.name)
            if not m:
                continue
            tile_id = m.group(1)
            is_subset = "_demo" in file.name or "_subset" in file.name

            # Jika tile_id sudah ada dan yang baru adalah full tile (bukan subset), timpa
            if tile_id not in details or (details[tile_id].get("is_subset", False) and not is_subset):
                if tile_id not in installed_tiles:
                    installed_tiles.append(tile_id)
                details[tile_id] = {
                    "installed": True,
                    "file_name": file.name,
                    "file_size_bytes": file.stat().st_size,
                    "path": str(file),
                    "is_kalimantan_core": tile_id in KALIMANTAN_GLAD_TILES,
                    "is_subset": is_subset,
                }

    # 2. Catat status 4 tile Kalimantan jika belum terpasang
    for tile_id in sorted(KALIMANTAN_GLAD_TILES):
        if tile_id not in details:
            details[tile_id] = {
                "installed": False,
                "file_name": f"{tile_id}.tif",
                "download_url": f"https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/{tile_id}.tif",
                "is_kalimantan_core": True,
                "is_subset": False,
            }

    kalimantan_installed = [t for t in installed_tiles if t in KALIMANTAN_GLAD_TILES]
    available = len(kalimantan_installed) > 0
    return available, installed_tiles, details
