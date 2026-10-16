"""
backend/app/extract_kalteng_subset.py
Skrip ekstraksi subset wilayah demo Kalimantan Tengah (Palangka Raya)
dari dataset resmi UMD GLAD Forest Extent 2020 via GDAL /vsicurl/.

Tidak mengunduh seluruh berkas 1.6 GB, melainkan hanya blok spasial
di sekitar Palangka Raya (lat: -2.60 s.d. -1.80, lon: 113.50 s.d. 114.40).
Menyimpan ke data/raster/forest/kalimantan/GLAD_Forest_extent_2020_00N_110E_kalteng_demo.tif
dengan kompresi LZW (~1-2 MB).
"""

import time
from pathlib import Path
import numpy as np
try:
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.windows import Window
except (ImportError, Exception):
    rasterio = None

REMOTE_TILE_URL = "/vsicurl/https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/00N_110E.tif"
OUTPUT_DIR = Path("data/raster/forest/kalimantan")
OUTPUT_FILE = OUTPUT_DIR / "GLAD_Forest_extent_2020_00N_110E_kalteng_demo.tif"

# Bounding box demo Palangka Raya & Kalteng:
# Lat: -2.60 s.d. -1.80 (0.80 derajat = 3200 piksel)
# Lon: 113.50 s.d. 114.40 (0.90 derajat = 3600 piksel)
SUBSET_LEFT_LON = 113.50
SUBSET_TOP_LAT = -1.80
SUBSET_WIDTH = 3600
SUBSET_HEIGHT = 3200
PIXEL_SIZE = 0.00025

# Indeks pada tile 00N_110E (origin: lon 110.0, lat 0.0)
COL_OFFSET = int(round((SUBSET_LEFT_LON - 110.0) / PIXEL_SIZE))  # 14000
ROW_OFFSET = int(round((0.0 - SUBSET_TOP_LAT) / PIXEL_SIZE))     # 7200


def extract_subset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"1. Membuka berkas resmi remote: {REMOTE_TILE_URL}")
    t0 = time.time()

    with rasterio.open(REMOTE_TILE_URL) as src:
        print(f"   Terhubung dalam {round(time.time() - t0, 2)} detik.")
        print(f"   Dimensi sumber: {src.width}x{src.height}, CRS: {src.crs}, Bounds: {src.bounds}")

        window = Window(col_off=COL_OFFSET, row_off=ROW_OFFSET, width=SUBSET_WIDTH, height=SUBSET_HEIGHT)
        print(f"2. Membaca jendela spasial Palangka Raya (row: {ROW_OFFSET}..{ROW_OFFSET+SUBSET_HEIGHT}, col: {COL_OFFSET}..{COL_OFFSET+SUBSET_WIDTH})...")
        t_read = time.time()
        data = src.read(1, window=window)
        print(f"   Pembacaan window selesai dalam {round(time.time() - t_read, 2)} detik.")

        vals, counts = np.unique(data, return_counts=True)
        stats = dict(zip(vals.tolist(), counts.tolist()))
        print(f"   Nilai piksel unik: {vals}, Distribusi: {stats}")

        # Tulis ke GeoTIFF lokal terkompresi
        transform = from_origin(SUBSET_LEFT_LON, SUBSET_TOP_LAT, PIXEL_SIZE, PIXEL_SIZE)
        profile = {
            "driver": "GTiff",
            "dtype": "uint8",
            "nodata": 255,
            "width": SUBSET_WIDTH,
            "height": SUBSET_HEIGHT,
            "count": 1,
            "crs": "EPSG:4326",
            "transform": transform,
            "compress": "lzw",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        }

        print(f"3. Menyimpan raster subset lokal ke: {OUTPUT_FILE}")
        with rasterio.open(OUTPUT_FILE, "w", **profile) as dst:
            dst.write(data, 1)

        file_size_kb = round(OUTPUT_FILE.stat().st_size / 1024, 2)
        print(f"   Berhasil disimpan! Ukuran berkas lokal: {file_size_kb} KB (~{round(file_size_kb / 1024, 2)} MB).")
        print("   Ekstraksi selesai secara hemat tanpa mengunduh 1.6 GB penuh.")


if __name__ == "__main__":
    extract_subset()
