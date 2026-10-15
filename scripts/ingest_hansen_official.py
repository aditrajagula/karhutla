"""
Script Ingestion Data Resmi Hansen Global Forest Change v1.13.
Mengunduh subset resmi dari Google Cloud Storage UMD untuk area target prioritas,
memvalidasi integritas geospasial, memotong sesuai bounding box,
menyimpan dalam format Tiled GeoTIFF LZW, dan menghasilkan manifest provenance.

Penggunaan:
    python scripts/ingest_hansen_official.py
    python scripts/ingest_hansen_official.py --min-lon 113.60 --min-lat -2.50 --max-lon 114.20 --max-lat -2.00
"""

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raster" / "hansen" / "official"

VERSION = "GFC-2025-v1.13"
TILE_ID = "00N_110E"
BASE_URL = f"https://storage.googleapis.com/earthenginepartners-hansen/{VERSION}/"
PIXEL_SIZE = 0.00025  # 0.00025° = 0.9 arc-second (~27.83m pada khatulistiwa)

# Bounding box default: Koridor Palangka Raya - Pulang Pisau - Sebangau
# Pusat anomali termal dan kebakaran gambut Kalimantan Tengah
DEFAULT_MIN_LON = 113.60
DEFAULT_MAX_LON = 114.20
DEFAULT_MIN_LAT = -2.50
DEFAULT_MAX_LAT = -2.00

LAYERS = ["lossyear", "treecover2000", "datamask"]


def compute_file_sha256(filepath: Path) -> str:
    """Menghitung hash SHA-256 dari berkas biner."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_storage_capacity(target_dir: Path, required_mb: float = 100.0) -> None:
    """Memeriksa ketersediaan ruang penyimpanan lokal."""
    target_dir.mkdir(parents=True, exist_ok=True)
    total, used, free = shutil.disk_usage(target_dir)
    free_mb = free / (1024 * 1024)
    print(f">> Pemeriksaan Kapasitas Disk ({target_dir}):")
    print(f"   Tersedia: {free_mb:.2f} MB | Dibutuhkan: ~{required_mb:.2f} MB")
    if free_mb < required_mb:
        raise RuntimeError(
            f"Ruang penyimpanan tidak mencukupi! Tersedia {free_mb:.2f} MB, dibutuhkan {required_mb:.2f} MB."
        )
    print("   [OK] Ruang penyimpanan aman.")


def verify_remote_url(client: httpx.Client, url: str) -> int:
    """Melakukan verifikasi HEAD request ke server resmi UMD GCS."""
    r = client.head(url)
    if r.status_code != 200:
        raise RuntimeError(f"Gagal mengakses URL resmi: {url} (HTTP {r.status_code})")
    content_len = int(r.headers.get("content-length", 0))
    accept_ranges = r.headers.get("accept-ranges", "")
    print(f"   [OK] Ditemukan: {url.split('/')[-1]} ({content_len / (1024*1024):.2f} MB, Range: {accept_ranges})")
    return content_len


def ingest_layer_subset(
    layer_name: str,
    tile_id: str,
    version: str,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    output_dir: Path,
) -> Dict[str, Any]:
    """Mengunduh dan menyimpan subset resmi 1 layer."""
    remote_filename = f"Hansen_{version}_{layer_name}_{tile_id}.tif"
    remote_url = f"{BASE_URL}{remote_filename}"
    local_filename = f"Hansen_{version}_{layer_name}_{tile_id}_official.tif"
    out_path = output_dir / local_filename

    print(f"\n>> Mengambil data resmi layer '{layer_name}' via windowed stream...")
    t0 = time.time()

    with rasterio.open(remote_url) as src:
        # Validasi CRS dan bounds
        if not src.crs or "4326" not in src.crs.to_string():
            raise ValueError(f"CRS raster remote bukan WGS84 EPSG:4326: {src.crs}")

        # Periksa transformasi affine dan resolusi grid sumber
        res_x = src.transform.a
        res_y = src.transform.e
        orig_x = src.transform.c
        orig_y = src.transform.f

        if res_x <= 0 or res_y >= 0:
            raise ValueError(f"Resolusi transformasi sumber tidak terduga: a={res_x}, e={res_y}")

        # Hitung baris dan kolom dengan pembulatan int(round(...)) untuk
        # mengeliminasi floating-point precision error (misal 3.5999999999999943 / 0.00025 = 14399.999999999978)
        left_col = int(round((min_lon - orig_x) / res_x))
        right_col = int(round((max_lon - orig_x) / res_x))
        top_row = int(round((max_lat - orig_y) / res_y))
        bottom_row = int(round((min_lat - orig_y) / res_y))

        width = right_col - left_col
        height = bottom_row - top_row

        if width <= 0 or height <= 0:
            raise ValueError(f"Dimensi window tidak valid: width={width}, height={height}")

        # Verifikasi konsistensi bounding box target dengan grid sumber UMD
        # Untuk [113.60, -2.50, 114.20, -2.00] dengan grid 0.00025 deg:
        # width = 0.60 / 0.00025 = 2400 piksel, height = 0.50 / 0.00025 = 2000 piksel.
        expected_width = int(round((max_lon - min_lon) / res_x))
        expected_height = int(round((max_lat - min_lat) / abs(res_y)))
        if width != expected_width or height != expected_height:
            raise ValueError(
                f"Inkonsistensi dimensi window: dihitung ({height}, {width}), "
                f"ekspektasi ({expected_height}, {expected_width})"
            )

        print(f"   Window Spasial: Kolom {left_col} s.d. {right_col} ({width} px), Baris {top_row} s.d. {bottom_row} ({height} px)")
        win = Window(left_col, top_row, width, height)

        data = src.read(1, window=win)
        t_read = time.time() - t0
        print(f"   Pembacaan remote selesai dalam {t_read:.2f}s. Array shape: {data.shape}")

    # Hitung affine transform origin sudut kiri atas untuk subset persis dari grid alignment sumber
    subset_origin_x = orig_x + (left_col * res_x)
    subset_origin_y = orig_y + (top_row * res_y)
    out_transform = from_origin(subset_origin_x, subset_origin_y, abs(res_x), abs(res_y))

    # Simpan sebagai Tiled GeoTIFF terkompresi LZW
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=out_transform,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dst:
        dst.write(data, 1)

    file_size_bytes = out_path.stat().st_size
    file_size_kb = file_size_bytes / 1024
    checksum_sha256 = compute_file_sha256(out_path)

    unique_vals = np.unique(data)
    print(f"   [SUKSES] Disimpan di: {out_path.name} ({file_size_kb:.1f} KB)")
    print(f"   Nilai piksel unik: {unique_vals[:15]}")
    print(f"   SHA-256: {checksum_sha256}")

    return {
        "layer": layer_name,
        "filename": local_filename,
        "file_path": str(out_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "remote_source_url": remote_url,
        "size_bytes": file_size_bytes,
        "size_kb": round(file_size_kb, 2),
        "checksum_sha256": checksum_sha256,
        "shape": [int(height), int(width)],
        "unique_values_count": int(len(unique_vals)),
        "unique_sample": [int(x) for x in unique_vals[:15]],
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest Resmi Hansen GFC v1.13")
    parser.add_argument("--tile", default=TILE_ID, help="ID Tile Hansen (default: 00N_110E)")
    parser.add_argument("--version", default=VERSION, help="Versi dataset (default: GFC-2025-v1.13)")
    parser.add_argument("--min-lon", type=float, default=DEFAULT_MIN_LON, help="Bujur minimum")
    parser.add_argument("--min-lat", type=float, default=DEFAULT_MIN_LAT, help="Lintang minimum")
    parser.add_argument("--max-lon", type=float, default=DEFAULT_MAX_LON, help="Bujur maksimum")
    parser.add_argument("--max-lat", type=float, default=DEFAULT_MAX_LAT, help="Lintang maksimum")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Direktori output")
    args = parser.parse_args()

    print("==================================================================")
    print("   INGESTION DATA RESMI HANSEN GLOBAL FOREST CHANGE (FIREGUARD)   ")
    print("==================================================================")
    print(f"Versi Dataset : {args.version}")
    print(f"Tile ID        : {args.tile}")
    print(f"Area Bounding  : Lon [{args.min_lon:.2f} s.d. {args.max_lon:.2f}], Lat [{args.min_lat:.2f} s.d. {args.max_lat:.2f}]")
    print(f"Direktori      : {args.output_dir}")

    # 1. Periksa ruang penyimpanan
    check_storage_capacity(args.output_dir, required_mb=50.0)

    # 2. Verifikasi ketersediaan remote URL
    print("\n>> Memeriksa ketersediaan remote URL resmi...")
    with httpx.Client(timeout=15.0) as client:
        for layer in LAYERS:
            url = f"{BASE_URL}Hansen_{args.version}_{layer}_{args.tile}.tif"
            verify_remote_url(client, url)

    # 3. Ekstraksi masing-masing layer resmi
    layer_manifests = {}
    start_all = time.time()

    for layer in LAYERS:
        info = ingest_layer_subset(
            layer_name=layer,
            tile_id=args.tile,
            version=args.version,
            min_lon=args.min_lon,
            min_lat=args.min_lat,
            max_lon=args.max_lon,
            max_lat=args.max_lat,
            output_dir=args.output_dir,
        )
        layer_manifests[layer] = info

    total_duration = time.time() - start_all
    total_size_bytes = sum(item["size_bytes"] for item in layer_manifests.values())

    # 4. Tulis Manifest Provenance Resmi
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "manifest_version": "1.0",
        "tile_id": args.tile,
        "dataset_version": args.version,
        "source": "UNIVERSITY_OF_MARYLAND_GOOGLE_EARTH_ENGINE",
        "source_base_url": BASE_URL,
        "source_type": "OFFICIAL_UMD_HANSEN_GFC",
        "is_synthetic": False,
        "is_clipped": True,
        "target_region_label": "Kalimantan Tengah - Koridor Palangka Raya & Pulang Pisau",
        "provinces_covered": ["Kalimantan Tengah", "Kalimantan Selatan"],
        "bounding_box": {
            "min_lon": args.min_lon,
            "min_lat": args.min_lat,
            "max_lon": args.max_lon,
            "max_lat": args.max_lat,
        },
        "spatial_resolution_deg": PIXEL_SIZE,
        "spatial_resolution_approx_m": 27.83,
        "total_size_bytes": total_size_bytes,
        "total_size_kb": round(total_size_bytes / 1024, 2),
        "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        "ingestion_duration_seconds": round(total_duration, 2),
        "ingested_at_utc": now_utc,
        "layers": layer_manifests,
        "scientific_integrity_notes": (
            "Data subset resmi diekstraksi langsung dari citra GeoTIFF University of Maryland (UMD) "
            "pada Google Cloud Storage melalui windowed spatial query. Berkas disimpan dalam format "
            "Cloud-Optimized Tiled GeoTIFF LZW untuk pembacaan sub-milidetik. Nilai tutupan dan "
            "kehilangan pohon adalah data satelit Landsat (USGS/NASA) historis 2000-2025."
        ),
    }

    manifest_path = args.output_dir / f"manifest_{args.tile}_official.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Buat juga salinan manifest di data/raster/hansen/ untuk kemudahan lookup
    root_manifest_path = PROJECT_ROOT / "data" / "raster" / "hansen" / f"manifest_{args.tile}_official.json"
    with open(root_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n==================================================================")
    print(f">> INGESTION SUKSES! Total waktu: {total_duration:.2f} detik")
    print(f">> Total ukuran data: {total_size_bytes / (1024*1024):.2f} MB")
    print(f">> Manifest tersimpan: {manifest_path.name}")
    print("==================================================================")


if __name__ == "__main__":
    main()
