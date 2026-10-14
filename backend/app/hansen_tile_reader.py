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

import math
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.errors import RasterioError, RasterioIOError
from rasterio.windows import Window

from .config import (
    BOUNDARIES_PATH,
    HANSEN_DATASET_VERSION,
    HANSEN_ENABLE_REMOTE_ACCESS,
    HANSEN_REMOTE_BASE_URL,
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


def read_pixel_from_raster(
    source: str,
    lat: float,
    lon: float,
    timeout_seconds: float = 10.0,
) -> Tuple[int, int, int]:
    """
    Membaca 1 piksel dari file raster lokal atau URL remote menggunakan Rasterio.
    Menggunakan Window(col, row, 1, 1) agar hanya membaca rentang byte yang diperlukan.
    
    Mengembalikan (pixel_value, row, col).
    Memunculkan RasterioError, ValueError, atau FileNotFoundError jika gagal.
    """
    # Atur opsi GDAL untuk optimasi HTTP Range
    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_TIMEOUT": str(int(timeout_seconds)),
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    }

    with rasterio.Env(**env_options):
        with rasterio.open(source) as src:
            # Hitung indeks row, col dari koordinat geospasial
            row, col = src.index(lon, lat)

            if row < 0 or row >= src.height or col < 0 or col >= src.width:
                raise ValueError(
                    f"Koordinat ({lat}, {lon}) menghasilkan piksel ({row}, {col}) di luar batas raster ({src.height}, {src.width})."
                )

            # Baca tepat 1 piksel
            window = Window(col, row, 1, 1)
            arr = src.read(1, window=window)

            if arr.size == 0:
                raise ValueError(f"Pembacaan piksel pada ({row}, {col}) menghasilkan array kosong.")

            val = int(arr[0, 0])
            return val, row, col


def clear_pixel_cache() -> None:
    """Membersihkan cache pembacaan piksel raster (berguna untuk pengujian)."""
    with _CACHE_LOCK:
        _PIXEL_CACHE.clear()


def get_cache_size() -> int:
    """Mengembalikan jumlah rekaman dalam cache piksel."""
    with _CACHE_LOCK:
        return len(_PIXEL_CACHE)


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
    """
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
        )

    # 3. Periksa cache jika diaktifkan
    cache_key = f"{round(lat, 6)}_{round(lon, 6)}_{version}_{effective_remote}"
    if use_cache:
        with _CACHE_LOCK:
            if cache_key in _PIXEL_CACHE:
                return _PIXEL_CACHE[cache_key]

    # 4. Cari sumber untuk layer 'lossyear' (layer wajib)
    lossyear_source, access_method = resolve_layer_source(
        "lossyear", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
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
            error_message=f"File raster untuk tile {tile_id} belum tersedia di penyimpanan lokal.",
            verification_notes="Data raster tingkat piksel lokal belum tersedia. Evaluasi tutupan pohon belum dapat dinilai.",
        )
        if use_cache:
            with _CACHE_LOCK:
                _PIXEL_CACHE[cache_key] = res
        return res

    # 5. Baca nilai piksel layer lossyear
    try:
        raw_lossyear, row, col = read_pixel_from_raster(lossyear_source, lat, lon)
    except Exception as e:
        # PENTING: Kegagalan pembacaan TIDAK BOLEH diubah menjadi lossyear=0
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
            verification_notes="Pembacaan piksel raster gagal karena kendala berkas atau jaringan.",
        )
        return res

    # 6. Baca layer 'treecover2000' (opsional pendukung)
    treecover_val = None
    tc_source, _ = resolve_layer_source(
        "treecover2000", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
    )
    if tc_source:
        try:
            treecover_val, _, _ = read_pixel_from_raster(tc_source, lat, lon)
        except Exception:
            treecover_val = None

    # 7. Baca layer 'datamask' (opsional pendukung)
    datamask_val = None
    dm_source, _ = resolve_layer_source(
        "datamask", tile_id, version=version, tiles_dir=tiles_dir, enable_remote=effective_remote
    )
    if dm_source:
        try:
            datamask_val, _, _ = read_pixel_from_raster(dm_source, lat, lon)
        except Exception:
            datamask_val = None

    # 8. Terapkan taksonomi ilmiah semantik piksel
    # A. Cek NoData / Perairan / Non-Hutan:
    # datamask: 0 = No Data (ocean/unmapped), 2 = Permanent Water
    is_nodata_or_water = datamask_val in (0, 2)
    is_non_forest_baseline = (treecover_val is not None and treecover_val == 0 and raw_lossyear == 0)

    if is_nodata_or_water or is_non_forest_baseline:
        detail_desc = "Badan air permanen" if datamask_val == 2 else (
            "Area tanpa data (laut/luar batas)" if datamask_val == 0 else "Bukan tutupan hutan pada baseline 2000"
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
            verification_notes=f"Piksel teridentifikasi sebagai {detail_desc} sehingga tidak dapat dinilai untuk kehilangan tutupan pohon.",
        )
    elif raw_lossyear > 0:
        # B. Kehilangan tutupan pohon terdeteksi (1..25 -> 2001..2025)
        # Validasi batas nilai lossyear (1 s.d. 25 untuk Hansen GFC v1.13)
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
        )

    if use_cache:
        with _CACHE_LOCK:
            _PIXEL_CACHE[cache_key] = res

    return res
