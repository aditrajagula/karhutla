"""
Modul Pembaca Raster Hansen Global Forest Change (Hansen GFC Tile Reader).
Mendukung pembacaan raster GeoTIFF tingkat piksel (resolusi 1 arc-second ~ 30m)
untuk dataset Hansen GFC (versi GFC-2025-v1.13 / GFC-2024-v1.12).

Tanggung Jawab:
1. Menentukan tile 10°x10° yang melingkupi koordinat (lat, lon).
2. Memvalidasi apakah koordinat berada di dalam wilayah 5 provinsi Kalimantan Indonesia.
3. Membaca nilai piksel pada layer:
   - treecover2000: Tutupan kanopi pohon >5m pada tahun 2000 (0–100%).
   - lossyear: Tahun kehilangan tutupan kanopi (0 = tidak ada, 1..25 = tahun 2001..2025).
   - datamask: 0 = No Data (laut/luar batas), 1 = Daratan, 2 = Badan air permanen.
4. Menerapkan taksonomi ilmiah status piksel:
   - OUT_OF_SCOPE: Di luar 5 provinsi Kalimantan atau di luar cakupan tile.
   - INSUFFICIENT_DATA: File tidak ditemukan, gagal dibaca, corrupt, atau timeout.
   - NO_DATA_OR_NON_FOREST: datamask=0 (no data), datamask=2 (air), atau treecover2000=0 dan lossyear=0.
   - NO_LOSS_DETECTED: Piksel valid, datamask=1, treecover2000 > 0, dan lossyear=0.
   - LOSS_DETECTED: Piksel valid, lossyear > 0 (1..25).
5. Memisahkan kegagalan infrastruktur dari hasil ilmiah valid (TIDAK mengubah error jadi loss=0).
6. Mendukung pembacaan lokal (primary) dan remote via HTTP Range / vsicurl jika diaktifkan.
7. Cache memori thread-safe untuk performa evaluasi cepat.
"""

import concurrent.futures
import math
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.errors import RasterioError, RasterioIOError
from rasterio.windows import Window

from .config import (
    BOUNDARIES_PATH,
    HANSEN_CACHE_MAX_ENTRIES,
    HANSEN_DATASET_VERSION,
    HANSEN_ENABLE_REMOTE_ACCESS,
    HANSEN_MAX_PARALLEL_WORKERS,
    HANSEN_REMOTE_BASE_URL,
    HANSEN_REMOTE_TIMEOUT_SECONDS,
    HANSEN_TILES_DIR,
)

# 4 Tile Hansen 10°x10° yang melingkupi seluruh 5 provinsi Kalimantan Indonesia
# Format penamaan UMD: Koordinat sudut kiri-atas (top-left) tile
KALIMANTAN_HANSEN_TILES = {
    "00N_100E",  # Kalimantan Barat bagian Selatan
    "00N_110E",  # Kalimantan Tengah, Kalimantan Selatan, Kalimantan Timur bagian Selatan
    "10N_100E",  # Kalimantan Barat bagian Utara
    "10N_110E",  # Kalimantan Utara, Kalimantan Timur bagian Utara
}

# 5 Provinsi Kalimantan Indonesia
KALIMANTAN_PROVINCES = [
    "Kalimantan Barat",
    "Kalimantan Tengah",
    "Kalimantan Selatan",
    "Kalimantan Timur",
    "Kalimantan Utara",
]

# Taksonomi status evaluasi
STATUS_OUT_OF_SCOPE = "OUT_OF_SCOPE"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_NO_DATA_OR_NON_FOREST = "NO_DATA_OR_NON_FOREST"
STATUS_NO_LOSS_DETECTED = "NO_LOSS_DETECTED"
STATUS_LOSS_DETECTED = "LOSS_DETECTED"

# Keterbatasan ilmiah wajib disertakan pada respons
SCIENTIFIC_CAVEAT_DEFAULT = (
    "Perubahan tutupan pohon adalah indikator biofisik hilangnya kanopi pohon > 5 meter dan "
    "tidak secara otomatis membuktikan pembukaan lahan ilegal atau kebakaran tanpa verifikasi hak atas tanah dan pemeriksaan lapangan."
)

# Lock untuk sinkronisasi unduhan lokal dan cache
_DOWNLOAD_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_PIXEL_CACHE: Dict[str, "HansenPixelResult"] = {}
_GRID_CACHE: Dict[str, "HansenPixelResult"] = {}

# Spatial filter lazily loaded
_SPATIAL_FILTER = None
_SPATIAL_FILTER_LOADED = False


def _get_spatial_filter():
    """Memuat filter spasial Indonesia secara lazy singleton."""
    global _SPATIAL_FILTER, _SPATIAL_FILTER_LOADED
    if not _SPATIAL_FILTER_LOADED:
        try:
            from .spatial_filter import IndonesiaSpatialFilter
            if BOUNDARIES_PATH.exists():
                _SPATIAL_FILTER = IndonesiaSpatialFilter(BOUNDARIES_PATH)
        except Exception:
            _SPATIAL_FILTER = None
        _SPATIAL_FILTER_LOADED = True
    return _SPATIAL_FILTER


@dataclass
class HansenPixelResult:
    """Struktur data hasil pembacaan piksel raster Hansen GFC."""
    status: str
    category_result: str
    loss_detected: bool
    loss_year: Optional[int]
    treecover2000: Optional[int]
    datamask: Optional[int]
    raw_lossyear: Optional[int]
    tile_id: Optional[str]
    pixel_row: Optional[int]
    pixel_col: Optional[int]
    province: Optional[str] = None
    pixel_resolution_approx_m: float = 30.87
    dataset_version: str = HANSEN_DATASET_VERSION
    data_period: str = "2000–2025"
    access_method: Optional[str] = None
    raster_available: bool = False
    data_status: str = "demonstration"
    data_verified: bool = False
    matching_rule: Optional[str] = None
    scientific_caveat: str = SCIENTIFIC_CAVEAT_DEFAULT
    error_message: Optional[str] = None
    verification_notes: Optional[str] = None
    pixel_center_lat: Optional[float] = None
    pixel_center_lon: Optional[float] = None
    georef_crs: Optional[str] = None
    transform_verified: bool = False
    coordinate_audit: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    cache_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Konversi ke kamus (dictionary) yang ramah serialisasi JSON."""
        return asdict(self)


def get_hansen_tile_id(lat: float, lon: float) -> str:
    """
    Menentukan ID tile Hansen 10°x10° berdasarkan koordinat (lat, lon).
    UMD Hansen GFC menggunakan sudut kiri-atas (top-left / NW corner) dari tile 10°x10°.
    
    Contoh:
    - lat: -2.21, lon: 110.09 -> top lat: 00N, left lon: 110E -> '00N_110E'
    - lat:  1.55, lon: 110.35 -> top lat: 10N, left lon: 110E -> '10N_110E'
    - lat: -0.05, lon: 109.34 -> top lat: 00N, left lon: 100E -> '00N_100E'
    """
    # Lintang atas (top latitude): pembulatan ke atas kelipatan 10
    top_lat = int(math.ceil(lat / 10.0) * 10)
    # Garis bujur kiri (left longitude): pembulatan ke bawah kelipatan 10
    left_lon = int(math.floor(lon / 10.0) * 10)

    # Format penamaan Hansen: misal 00N, 10N, 10S, 100E, 110E, 050W
    lat_prefix = f"{abs(top_lat):02d}N" if top_lat >= 0 else f"{abs(top_lat):02d}S"
    lon_prefix = f"{abs(left_lon):03d}E" if left_lon >= 0 else f"{abs(left_lon):03d}W"

    return f"{lat_prefix}_{lon_prefix}"


def get_tile_bounds(tile_id: str) -> Tuple[float, float, float, float]:
    """
    Menghitung batas geografis (min_lon, min_lat, max_lon, max_lat) untuk ID tile Hansen.
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


def is_coordinate_in_kalimantan(
    lat: float, lon: float, province: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Memeriksa apakah koordinat (lat, lon) berada di dalam 5 provinsi Kalimantan Indonesia.
    Menggunakan filter poligon batas wilayah resmi (Point-in-Polygon) jika tersedia,
    atau pencocokan nama provinsi dan batas bounding box Kalimantan.
    """
    # 1. Jika nama provinsi eksplisit diberikan, periksa kecocokan nama
    matched_prov = None
    if province:
        for p in KALIMANTAN_PROVINCES:
            if p.lower() in province.lower() or province.lower() in p.lower():
                matched_prov = p
                break
        if not matched_prov:
            # Dinyatakan eksplisit berada di provinsi lain (misal Sarawak, Jawa Barat)
            return False, None

    # 2. Periksa bounding box kasar Kalimantan (-4.5 s.d. 4.5, 108.5 s.d. 119.5)
    if not (-5.0 <= lat <= 5.0 and 108.0 <= lon <= 120.0):
        return False, None

    # 3. Gunakan filter spasial batas administratif resmi (Point-in-Polygon)
    sf = _get_spatial_filter()
    if sf is not None:
        inside, prov_from_poly = sf.is_inside_kalimantan(lon, lat)
        if not inside:
            # Titik secara fisik berada di luar wilayah 5 provinsi Kalimantan (laut, Sarawak, Sabah, Brunei, dll).
            # Parameter nama provinsi dari pemanggil TIDAK BOLEH membuat titik di luar wilayah menjadi valid.
            return False, None
        return True, prov_from_poly

    # Fallback hanya jika file poligon batas wilayah belum dimuat
    if matched_prov:
        return True, matched_prov

    return False, None


def resolve_layer_source(
    layer: str,
    tile_id: str,
    version: str = HANSEN_DATASET_VERSION,
    tiles_dir: Optional[Union[str, Path]] = None,
    enable_remote: bool = False,
) -> Tuple[Optional[str], str]:
    """
    Menentukan sumber file GeoTIFF untuk layer tertentu (lossyear, treecover2000, datamask).
    Prioritas:
    1. File lokal di tiles_dir (nama lengkap UMD atau nama layer singkat).
    2. URL remote HTTP Range jika enable_remote=True.
    3. None jika tidak tersedia.
    
    Mengembalikan (source_path_or_url, access_method).
    """
    dir_path = Path(tiles_dir) if tiles_dir else HANSEN_TILES_DIR

    # Pola penamaan file lokal yang didukung
    candidates = [
        dir_path / f"Hansen_{version}_{layer}_{tile_id}.tif",
        dir_path / f"Hansen_{version}_{layer}_{tile_id}.tiff",
        dir_path / f"{layer}_{tile_id}.tif",
        dir_path / f"{layer}_{tile_id}.tiff",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate), "local_file"

    if enable_remote:
        base_url = HANSEN_REMOTE_BASE_URL.format(version=version)
        remote_url = f"{base_url}Hansen_{version}_{layer}_{tile_id}.tif"
        return remote_url, "remote_range"

    return None, "unavailable"


def verify_geotiff_metadata_and_transform(
    src: rasterio.DatasetReader,
    lat: float,
    lon: float,
) -> Dict[str, Any]:
    """
    Memvalidasi metadata GeoTIFF dan memverifikasi transformasi koordinat secara analitis:
    1. Verifikasi CRS WGS84 (EPSG:4326 / OGC:CRS84).
    2. Verifikasi batas bounding box spasial (src.bounds).
    3. Verifikasi konsistensi matematis rumus Affine:
       col = floor((lon - c) / a)
       row = floor((lat - f) / e)
       terhadap indeks yang dihasilkan rasterio.
    4. Round-trip coordinate reconstruction (memastikan presisi sub-piksel < resolusi piksel).
    """
    # 1. Verifikasi CRS WGS84
    crs_str = ""
    if src.crs:
        crs_str = src.crs.to_string()
    is_wgs84 = (
        crs_str in ("EPSG:4326", "OGC:CRS84")
        or "+proj=longlat" in crs_str.lower()
        or "4326" in crs_str
        or not src.crs
    )
    if src.crs and not is_wgs84:
        raise ValueError(
            f"Ketidakcocokan CRS GeoTIFF: Raster memiliki CRS '{crs_str}', "
            f"namun dataset Hansen GFC mewajibkan koordinat geografis WGS84 (EPSG:4326)."
        )

    # 2. Verifikasi batas bounding box spasial
    bounds = src.bounds
    if not (bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top):
        raise ValueError(
            f"Koordinat ({lat}, {lon}) berada di luar batas geospasial raster GeoTIFF "
            f"[Bujur: {bounds.left} s.d. {bounds.right}, Lintang: {bounds.bottom} s.d. {bounds.top}]."
        )

    # 3. Hitung indeks piksel via rumus analitik Affine langsung:
    # x = a * col + b * row + c
    # y = d * col + e * row + f
    # Untuk raster north-up (b = 0, d = 0):
    a = src.transform.a
    e = src.transform.e
    c = src.transform.c
    f = src.transform.f

    if a == 0 or e == 0:
        raise ValueError(f"Matriks transform raster tidak valid (skala 0): a={a}, e={e}.")

    calc_col = min(int(math.floor((lon - c) / a)), src.width - 1)
    calc_row = min(int(math.floor((lat - f) / e)), src.height - 1)

    # Hitung via rasterio src.index()
    index_row, index_col = src.index(lon, lat)

    if index_row < 0 or index_row >= src.height or index_col < 0 or index_col >= src.width:
        raise ValueError(
            f"Koordinat ({lat}, {lon}) menghasilkan piksel ({index_row}, {index_col}) di luar batas raster ({src.height}, {src.width})."
        )

    # Bandingkan apakah konsisten (toleransi batas <= 1 piksel karena pembulatan floating point)
    if abs(calc_row - index_row) > 1 or abs(calc_col - index_col) > 1:
        raise ValueError(
            f"Inkonsistensi transformasi spasial: rumus analitik ({calc_row}, {calc_col}) "
            f"berbeda dengan rasterio index ({index_row}, {index_col})."
        )

    row = index_row
    col = index_col

    # 4. Round-trip verification: rekonsiliasi koordinat tengah piksel
    center_lon, center_lat = src.xy(row, col)
    error_lon_deg = abs(center_lon - lon)
    error_lat_deg = abs(center_lat - lat)
    max_tol_lon = abs(a)
    max_tol_lat = abs(e)

    if error_lon_deg > max_tol_lon or error_lat_deg > max_tol_lat:
        raise ValueError(
            f"Rekonstruksi koordinat piksel ({center_lat}, {center_lon}) melebihi toleransi "
            f"resolusi piksel ({max_tol_lat}, {max_tol_lon}) dari koordinat input ({lat}, {lon})."
        )

    return {
        "crs": crs_str or "EPSG:4326",
        "row": row,
        "col": col,
        "calc_row": calc_row,
        "calc_col": calc_col,
        "pixel_center_lat": round(center_lat, 6),
        "pixel_center_lon": round(center_lon, 6),
        "pixel_size_x_deg": round(a, 8),
        "pixel_size_y_deg": round(e, 8),
        "pixel_resolution_approx_m": round(abs(a) * 111320.0, 2),
        "transform_matrix": [round(val, 8) for val in [a, src.transform.b, c, src.transform.d, e, f]],
        "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
        "width": src.width,
        "height": src.height,
        "is_transform_verified": True,
    }


def read_pixel_from_raster(
    source: str,
    lat: float,
    lon: float,
    timeout_seconds: Optional[float] = None,
    return_audit: bool = False,
) -> Union[Tuple[int, int, int], Tuple[int, int, int, Dict[str, Any]]]:
    """
    Membaca 1 piksel dari file raster lokal atau URL remote menggunakan Rasterio.
    Menggunakan Window(col, row, 1, 1) agar hanya membaca rentang byte yang diperlukan.
    Melakukan validasi ketat CRS, bounding box, dan rumus Affine.
    
    Mengembalikan (pixel_value, row, col) atau (pixel_value, row, col, audit_dict).
    Memunculkan RasterioError, ValueError, atau FileNotFoundError jika gagal.
    """
    effective_timeout = timeout_seconds if timeout_seconds is not None else HANSEN_REMOTE_TIMEOUT_SECONDS

    # Atur opsi GDAL untuk optimasi HTTP Range
    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_TIMEOUT": str(max(1, int(effective_timeout))),
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    }

    with rasterio.Env(**env_options):
        with rasterio.open(source) as src:
            # Audit metadata & validasi transformasi spasial
            audit = verify_geotiff_metadata_and_transform(src, lat, lon)
            row = audit["row"]
            col = audit["col"]

            # Baca tepat 1 piksel
            window = Window(col, row, 1, 1)
            arr = src.read(1, window=window)

            if arr.size == 0:
                raise ValueError(f"Pembacaan piksel pada ({row}, {col}) menghasilkan array kosong.")

            val = int(arr[0, 0])
            if return_audit:
                return val, row, col, audit
            return val, row, col


def clear_pixel_cache() -> None:
    """Membersihkan cache pembacaan piksel raster (berguna untuk pengujian)."""
    with _CACHE_LOCK:
        _PIXEL_CACHE.clear()
        _GRID_CACHE.clear()


def get_cache_size() -> int:
    """Mengembalikan jumlah rekaman dalam cache piksel koordinat."""
    with _CACHE_LOCK:
        return len(_PIXEL_CACHE)


def _put_in_cache(coord_key: str, pixel_key: str, res: HansenPixelResult) -> None:
    """Menyimpan hasil ke cache dengan batas ukuran untuk mencegah kebocoran memori."""
    with _CACHE_LOCK:
        if len(_PIXEL_CACHE) >= HANSEN_CACHE_MAX_ENTRIES:
            remove_count = max(1, HANSEN_CACHE_MAX_ENTRIES // 10)
            for k in list(_PIXEL_CACHE.keys())[:remove_count]:
                _PIXEL_CACHE.pop(k, None)
            for k in list(_GRID_CACHE.keys())[:remove_count]:
                _GRID_CACHE.pop(k, None)
        _PIXEL_CACHE[coord_key] = res
        if pixel_key:
            _GRID_CACHE[pixel_key] = res


def read_hansen_pixel(
    lat: float,
    lon: float,
    province: Optional[str] = None,
    version: str = HANSEN_DATASET_VERSION,
    tiles_dir: Optional[Union[str, Path]] = None,
    enable_remote: Optional[bool] = None,
    use_cache: bool = True,
) -> HansenPixelResult:
    """
    Fungsi utama untuk mengevaluasi piksel Hansen GFC pada titik (lat, lon).
    Menghasilkan objek HansenPixelResult dengan taksonomi status yang konsisten.
    
    Optimasi Latensi (Poin C):
    1. Smart Dual-Tier Cache (koordinat presisi & grid piksel 30m).
    2. Pembacaan layer secara paralel menggunakan ThreadPoolExecutor.
    3. Batas waktu tunggu (timeout) ketat per layer dan penanganan kegagalan anggun.
    """
    start_time = time.perf_counter()
    effective_remote = (
        enable_remote if enable_remote is not None else HANSEN_ENABLE_REMOTE_ACCESS
    )

    # 1. Validasi cakupan wilayah Kalimantan
    in_kalimantan, prov_name = is_coordinate_in_kalimantan(lat, lon, province=province)
    if not in_kalimantan:
        return HansenPixelResult(
            status=STATUS_OUT_OF_SCOPE,
            category_result="Belum dapat dinilai",
            loss_detected=False,
            loss_year=None,
            treecover2000=None,
            datamask=None,
            raw_lossyear=None,
            tile_id=None,
            pixel_row=None,
            pixel_col=None,
            province=prov_name,
            raster_available=False,
            data_status="demonstration",
            data_verified=False,
            matching_rule="Koordinat berada di luar cakupan 5 provinsi Kalimantan Indonesia.",
            error_message="Lokasi di luar batas wilayah 5 provinsi Kalimantan.",
            verification_notes="Analisis tutupan pohon dibatasi secara ketat untuk wilayah 5 provinsi Kalimantan Indonesia.",
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    # 2. Tentukan ID tile Hansen
    tile_id = get_hansen_tile_id(lat, lon)
    if tile_id not in KALIMANTAN_HANSEN_TILES:
        return HansenPixelResult(
            status=STATUS_OUT_OF_SCOPE,
            category_result="Belum dapat dinilai",
            loss_detected=False,
            loss_year=None,
            treecover2000=None,
            datamask=None,
            raw_lossyear=None,
            tile_id=tile_id,
            pixel_row=None,
            pixel_col=None,
            province=prov_name,
            raster_available=False,
            data_status="demonstration",
            data_verified=False,
            matching_rule=f"Tile {tile_id} di luar 4 tile resmi Kalimantan (00N_100E, 00N_110E, 10N_100E, 10N_110E).",
            error_message=f"Tile {tile_id} tidak masuk daftar tile Kalimantan.",
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    # 3. Periksa cache jika diaktifkan (dual-tier: koordinat presisi & grid piksel 30m)
    tile_bounds = get_tile_bounds(tile_id)
    approx_col = int(math.floor((lon - tile_bounds[0]) / 0.00025))
    approx_row = int(math.floor((tile_bounds[3] - lat) / 0.00025))
    pixel_cache_key = f"{tile_id}_{approx_row}_{approx_col}_{version}"
    coord_cache_key = f"{round(lat, 6)}_{round(lon, 6)}_{version}_{effective_remote}"

    if use_cache:
        with _CACHE_LOCK:
            hit = _PIXEL_CACHE.get(coord_cache_key) or _GRID_CACHE.get(pixel_cache_key)
            if hit:
                cached_dict = asdict(hit)
                cached_dict["cache_hit"] = True
                cached_dict["access_method"] = "memory_cache"
                cached_dict["latency_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
                return HansenPixelResult(**cached_dict)

    # 4. Cari sumber untuk masing-masing layer
    lossyear_source, ly_method = resolve_layer_source(
        "lossyear", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
    )
    tc_source, tc_method = resolve_layer_source(
        "treecover2000", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
    )
    dm_source, dm_method = resolve_layer_source(
        "datamask", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
    )

    if not lossyear_source:
        res = HansenPixelResult(
            status=STATUS_INSUFFICIENT_DATA,
            category_result="Belum dapat dinilai",
            loss_detected=False,
            loss_year=None,
            treecover2000=None,
            datamask=None,
            raw_lossyear=None,
            tile_id=tile_id,
            pixel_row=None,
            pixel_col=None,
            province=prov_name,
            raster_available=False,
            data_status="demonstration",
            data_verified=False,
            matching_rule=f"Layer raster Hansen lossyear ({tile_id}) belum tersedia secara lokal.",
            error_message=f"File raster untuk tile {tile_id} belum tersedia di penyimpanan lokal. Disarankan menyiapkan tile lokal untuk demo.",
            verification_notes="Data raster tingkat piksel lokal belum tersedia. Evaluasi tutupan pohon belum dapat dinilai.",
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )
        if use_cache:
            _put_in_cache(coord_cache_key, pixel_cache_key, res)
        return res

    access_method = ly_method
    per_layer_timeout = HANSEN_REMOTE_TIMEOUT_SECONDS if "remote" in ly_method else 10.0

    # 5. Pembacaan Paralel / Konkruen untuk layer raster (Poin C)
    raw_lossyear = None
    row = None
    col = None
    audit = None
    treecover_val = None
    datamask_val = None

    def _fetch_lossyear():
        return read_pixel_from_raster(lossyear_source, lat, lon, timeout_seconds=per_layer_timeout, return_audit=True)

    def _fetch_treecover():
        if not tc_source:
            return None
        res_tc = read_pixel_from_raster(tc_source, lat, lon, timeout_seconds=per_layer_timeout)
        return res_tc[0] if isinstance(res_tc, (tuple, list)) else res_tc

    def _fetch_datamask():
        if not dm_source:
            return None
        res_dm = read_pixel_from_raster(dm_source, lat, lon, timeout_seconds=per_layer_timeout)
        return res_dm[0] if isinstance(res_dm, (tuple, list)) else res_dm

    task_list = [("lossyear", _fetch_lossyear)]
    if tc_source:
        task_list.append(("treecover2000", _fetch_treecover))
    if dm_source:
        task_list.append(("datamask", _fetch_datamask))

    # Eksekusi paralel dengan ThreadPoolExecutor
    overall_timeout = per_layer_timeout + 2.0
    with concurrent.futures.ThreadPoolExecutor(max_workers=HANSEN_MAX_PARALLEL_WORKERS) as executor:
        future_map = {executor.submit(fn): name for name, fn in task_list}
        done, not_done = concurrent.futures.wait(
            future_map.keys(),
            timeout=overall_timeout,
            return_when=concurrent.futures.ALL_COMPLETED,
        )

        for future in done:
            tname = future_map[future]
            try:
                out = future.result()
                if tname == "lossyear":
                    if isinstance(out, tuple) and len(out) == 4:
                        raw_lossyear, row, col, audit = out
                    elif isinstance(out, tuple) and len(out) >= 3:
                        raw_lossyear, row, col = out[:3]
                elif tname == "treecover2000":
                    treecover_val = out
                elif tname == "datamask":
                    datamask_val = out
            except Exception as e:
                if tname == "lossyear":
                    res = HansenPixelResult(
                        status=STATUS_INSUFFICIENT_DATA,
                        category_result="Belum dapat dinilai",
                        loss_detected=False,
                        loss_year=None,
                        treecover2000=None,
                        datamask=None,
                        raw_lossyear=None,
                        tile_id=tile_id,
                        pixel_row=None,
                        pixel_col=None,
                        province=prov_name,
                        raster_available=False,
                        data_status="demonstration",
                        data_verified=False,
                        matching_rule="Gagal membaca piksel raster lossyear.",
                        error_message=f"Kegagalan infrastruktur pembacaan raster: {str(e)}",
                        verification_notes="Pembacaan piksel raster gagal karena batas waktu (timeout) atau kendala berkas/jaringan.",
                        latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                    )
                    return res
                # Layer pendukung gagal: biarkan nilainya None (graceful degradation)

        if not_done:
            for future in not_done:
                future.cancel()
            if raw_lossyear is None:
                res = HansenPixelResult(
                    status=STATUS_INSUFFICIENT_DATA,
                    category_result="Belum dapat dinilai",
                    loss_detected=False,
                    loss_year=None,
                    treecover2000=None,
                    datamask=None,
                    raw_lossyear=None,
                    tile_id=tile_id,
                    pixel_row=None,
                    pixel_col=None,
                    province=prov_name,
                    raster_available=False,
                    data_status="demonstration",
                    data_verified=False,
                    matching_rule=f"Akses remote melebihi batas waktu {overall_timeout} detik.",
                    error_message=f"Timeout akses raster: melebihi {overall_timeout} detik. Disarankan menggunakan tile lokal.",
                    verification_notes="Pembacaan piksel raster remote mengalami timeout.",
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )
                return res

    # 6. Terapkan taksonomi ilmiah semantik piksel
    # A. Cek NoData / Perairan / Non-Hutan:
    is_nodata_or_water = datamask_val in (0, 2)
    is_non_forest_baseline = (treecover_val is not None and treecover_val == 0 and raw_lossyear == 0)

    center_lat = audit.get("pixel_center_lat") if audit else None
    center_lon = audit.get("pixel_center_lon") if audit else None
    georef_crs = audit.get("crs") if audit else None
    is_verified = audit.get("is_transform_verified", False) if audit else False

    if is_nodata_or_water or is_non_forest_baseline:
        if datamask_val == 2:
            detail_desc = "Badan air permanen"
            note_desc = "Piksel teridentifikasi sebagai badan air permanen (sungai/danau) sehingga tidak memiliki tutupan kanopi pohon."
        elif datamask_val == 0:
            detail_desc = "Area tanpa data (laut/luar batas)"
            note_desc = "Piksel berada di luar batas observasi daratan atau area laut tanpa data."
        else:
            detail_desc = "Bukan tutupan hutan pada baseline 2000"
            note_desc = (
                f"Piksel daratan terverifikasi (datamask=1) dengan tutupan kanopi 0% pada baseline tahun 2000 "
                f"(kawasan pemukiman/perkotaan/lahan non-hutan historis, seperti kawasan perkotaan Palangka Raya). "
                f"Secara metodologis, metrik kehilangan tutupan pohon tidak dapat diterapkan pada baseline non-hutan."
            )
        res = HansenPixelResult(
            status=STATUS_NO_DATA_OR_NON_FOREST,
            category_result="Belum dapat dinilai",
            loss_detected=False,
            loss_year=None,
            treecover2000=treecover_val,
            datamask=datamask_val,
            raw_lossyear=raw_lossyear,
            tile_id=tile_id,
            pixel_row=row,
            pixel_col=col,
            province=prov_name,
            access_method=access_method,
            raster_available=True,
            data_status="raster_verified",
            data_verified=True,
            matching_rule=f"Pemeriksaan piksel 30m: {detail_desc}.",
            verification_notes=note_desc,
            pixel_center_lat=center_lat,
            pixel_center_lon=center_lon,
            georef_crs=georef_crs,
            transform_verified=is_verified,
            coordinate_audit=audit,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )
    elif raw_lossyear is not None and raw_lossyear > 0:
        # B. Kehilangan tutupan pohon terdeteksi (1..25 -> 2001..2025)
        if 1 <= raw_lossyear <= 25:
            loss_year_cal = 2000 + raw_lossyear
            res = HansenPixelResult(
                status=STATUS_LOSS_DETECTED,
                category_result="Ada indikasi pendukung",
                loss_detected=True,
                loss_year=loss_year_cal,
                treecover2000=treecover_val,
                datamask=datamask_val,
                raw_lossyear=raw_lossyear,
                tile_id=tile_id,
                pixel_row=row,
                pixel_col=col,
                province=prov_name,
                access_method=access_method,
                raster_available=True,
                data_status="raster_verified",
                data_verified=True,
                matching_rule=f"Terdeteksi kehilangan tutupan kanopi pada tahun {loss_year_cal} (lossyear={raw_lossyear}) resolusi 30m di {prov_name}.",
                verification_notes=f"Piksel raster Hansen memverifikasi riwayat kehilangan tutupan kanopi >5m pada tahun {loss_year_cal}.",
                pixel_center_lat=center_lat,
                pixel_center_lon=center_lon,
                georef_crs=georef_crs,
                transform_verified=is_verified,
                coordinate_audit=audit,
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
        else:
            # Nilai lossyear di luar rentang valid
            res = HansenPixelResult(
                status=STATUS_INSUFFICIENT_DATA,
                category_result="Belum dapat dinilai",
                loss_detected=False,
                loss_year=None,
                treecover2000=treecover_val,
                datamask=datamask_val,
                raw_lossyear=raw_lossyear,
                tile_id=tile_id,
                pixel_row=row,
                pixel_col=col,
                province=prov_name,
                access_method=access_method,
                raster_available=True,
                data_status="raster_verified",
                data_verified=False,
                matching_rule=f"Nilai lossyear={raw_lossyear} berada di luar rentang valid 1..25.",
                error_message=f"Nilai piksel lossyear {raw_lossyear} tidak valid.",
                pixel_center_lat=center_lat,
                pixel_center_lon=center_lon,
                georef_crs=georef_crs,
                transform_verified=is_verified,
                coordinate_audit=audit,
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
    else:
        # C. Tidak ada kehilangan tutupan pohon yang terdeteksi (lossyear=0 pada data valid)
        res = HansenPixelResult(
            status=STATUS_NO_LOSS_DETECTED,
            category_result="Belum ditemukan kecocokan",
            loss_detected=False,
            loss_year=None,
            treecover2000=treecover_val,
            datamask=datamask_val,
            raw_lossyear=0,
            tile_id=tile_id,
            pixel_row=row,
            pixel_col=col,
            province=prov_name,
            access_method=access_method,
            raster_available=True,
            data_status="raster_verified",
            data_verified=True,
            matching_rule=f"Pemeriksaan piksel 30m di {prov_name}: tidak terdeteksi kehilangan tutupan pohon (2000–2025).",
            verification_notes="Data raster valid. Tidak terdeteksi kehilangan tutupan pohon kanopi >5m selama periode 2000–2025.",
            pixel_center_lat=center_lat,
            pixel_center_lon=center_lon,
            georef_crs=georef_crs,
            transform_verified=is_verified,
            coordinate_audit=audit,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        )

    if use_cache:
        _put_in_cache(coord_cache_key, pixel_cache_key, res)

    return res


def audit_hansen_coordinate_transform(
    lat: float,
    lon: float,
    tile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fungsi audit analitis untuk memverifikasi transformasi koordinat (lat, lon)
    terhadap spesifikasi resmi metadata GeoTIFF Hansen GFC UMD (EPSG:4326, resolusi 0.00025°).
    
    Digunakan untuk menguji dan memvalidasi keakuratan pemetaan tile dan indeks piksel
    secara deterministik matematis.
    """
    resolved_tile = tile_id or get_hansen_tile_id(lat, lon)
    bounds = get_tile_bounds(resolved_tile)
    min_lon, min_lat, max_lon, max_lat = bounds

    # Parameter Affine Transform standar Hansen GFC UMD
    # Origin top-left: (min_lon, max_lat), pixel_size = 0.00025 deg (40000 x 40000 pixels)
    dx = 0.00025
    dy = -0.00025
    a, b, c = dx, 0.0, min_lon
    d, e, f = 0.0, dy, max_lat

    # Hitung col dan row
    col = int(math.floor((lon - min_lon) / dx))
    row = int(math.floor((max_lat - lat) / abs(dy)))

    # Koordinat pusat piksel
    center_lon = min_lon + (col + 0.5) * dx
    center_lat = max_lat - (row + 0.5) * abs(dy)

    # Residual error
    residual_lon_deg = abs(center_lon - lon)
    residual_lat_deg = abs(center_lat - lat)
    residual_dist_m = math.sqrt(
        (residual_lon_deg * 111320.0 * math.cos(math.radians(lat))) ** 2
        + (residual_lat_deg * 110574.0) ** 2
    )

    is_within_bounds = (min_lon <= lon <= max_lon) and (min_lat <= lat <= max_lat)
    is_valid_index = (0 <= col < 40000) and (0 <= row < 40000)

    return {
        "lat": lat,
        "lon": lon,
        "tile_id": resolved_tile,
        "crs": "EPSG:4326",
        "tile_bounds": list(bounds),
        "is_within_bounds": is_within_bounds,
        "pixel_size_deg": dx,
        "nominal_resolution_m": round(dx * 111320.0, 2),
        "affine_matrix": [a, b, c, d, e, f],
        "pixel_row": row,
        "pixel_col": col,
        "is_valid_index": is_valid_index,
        "pixel_center_lat": round(center_lat, 6),
        "pixel_center_lon": round(center_lon, 6),
        "residual_distance_m": round(residual_dist_m, 2),
        "verification_status": "VERIFIED_ACCURATE" if (is_within_bounds and is_valid_index) else "OUT_OF_BOUNDS",
    }
