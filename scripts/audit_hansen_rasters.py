"""
Audit Komprehensif 12 Raster Resmi Hansen GFC v1.13 (Tahap 2A & Tahap 2B).

Pemeriksaan:
1. Validasi Metadata Rasterio/GDAL: CRS, Transform, Bounds, Dimensi, Dtype, Nodata,
   Kompresi, Block Shapes, Tiling, Overviews.
2. Konsistensi Grid Hansen GFC (0.00025°, 40000x40000, Affine north-up).
3. Windowed Pixel Value Audit (tanpa memuat 1.6 miliar piksel sekaligus ke RAM):
   - lossyear: validasi domain 0..25
   - treecover2000: validasi domain 0..100
   - datamask: validasi domain 0..2
4. Benchmark Latensi Pembacaan Titik (1x1) dan Jendela Kecil (100x100) pada format strip-compressed.
5. Verifikasi Komparatif terhadap Sumber Remote UMD GCS (via vsicurl HTTP Range):
   - Perbandingan piksel terdekompresi lokal vs remote windowed.
6. Audit Manifest Provenance dan Keselamatan Data (demo rasters & backup).
7. Evaluasi Status Per Berkas:
   - download_complete
   - metadata_valid
   - pixel_values_valid
   - source_content_verified
   - overall_status (hanya VERIFIED jika semua 4 lolos).
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_DIR = PROJECT_ROOT / "data" / "raster" / "hansen" / "official"
BACKUP_DIR = OFFICIAL_DIR / "backup_subset_palangka_raya"
DEMO_DIR = PROJECT_ROOT / "data" / "raster" / "hansen"

VERSION = "GFC-2025-v1.13"
BASE_URL = f"https://storage.googleapis.com/earthenginepartners-hansen/{VERSION}/"

TILES = ["00N_100E", "00N_110E", "10N_100E", "10N_110E"]
LAYERS = ["lossyear", "treecover2000", "datamask"]

# Batas legal nilai piksel per layer
LAYER_VALID_DOMAINS = {
    "lossyear": (0, 25),       # 0 = no loss, 1..25 = loss year 2001..2025
    "treecover2000": (0, 100), # 0..100% canopy cover
    "datamask": (0, 2),        # 0 = no data, 1 = land, 2 = water
}


def get_expected_tile_bounds(tile_id: str) -> Tuple[float, float, float, float]:
    """Menghitung batas matematis standar (left, bottom, right, top) dari ID tile."""
    lat_str, lon_str = tile_id.split("_")
    top_lat = float(lat_str[:2]) if "N" in lat_str else -float(lat_str[:2])
    left_lon = float(lon_str[:3]) if "E" in lon_str else -float(lon_str[:3])
    return (left_lon, top_lat - 10.0, left_lon + 10.0, top_lat)


def audit_single_raster(
    tile_id: str,
    layer_name: str,
    verify_remote: bool = True,
) -> Dict[str, Any]:
    """Melakukan audit mendalam terhadap satu file raster lokal."""
    local_filename = f"Hansen_{VERSION}_{layer_name}_{tile_id}_official.tif"
    local_path = OFFICIAL_DIR / local_filename
    remote_url = f"{BASE_URL}Hansen_{VERSION}_{layer_name}_{tile_id}.tif"

    report: Dict[str, Any] = {
        "tile_id": tile_id,
        "layer": layer_name,
        "filename": local_filename,
        "download_complete": False,
        "metadata_valid": False,
        "pixel_values_valid": False,
        "source_content_verified": False,
        "overall_status": "FAILED",
        "notes": [],
    }

    # 1. Periksa keberadaan berkas
    if not local_path.exists():
        report["notes"].append("Berkas tidak ditemukan di penyimpanan lokal.")
        return report

    part_path = Path(str(local_path) + ".part")
    if part_path.exists():
        report["notes"].append("Ditemukan berkas .part aktif; unduhan mungkin belum tuntas.")
        return report

    actual_size = local_path.stat().st_size
    report["size_bytes"] = actual_size
    report["download_complete"] = True

    expected_bounds = get_expected_tile_bounds(tile_id)
    min_val_allowed, max_val_allowed = LAYER_VALID_DOMAINS[layer_name]

    # 2. Buka dan audit struktur geospasial
    try:
        with rasterio.open(local_path) as src:
            bounds = src.bounds
            crs = src.crs.to_string() if src.crs else None
            transform = list(src.transform)
            width = src.width
            height = src.height
            count = src.count
            dtype = str(src.dtypes[0])
            nodata = src.nodata
            block_shapes = src.block_shapes
            is_tiled = src.is_tiled
            overviews = src.overviews(1)
            compress = src.compression.name if src.compression else "NONE"

            report["structure"] = {
                "crs": crs,
                "width": width,
                "height": height,
                "bands": count,
                "dtype": dtype,
                "nodata": nodata,
                "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "expected_bounds": list(expected_bounds),
                "transform": transform,
                "is_tiled": is_tiled,
                "block_shapes": block_shapes,
                "overviews": overviews,
                "compression": compress,
            }

            # Validasi aturan grid
            meta_ok = True
            if crs != "EPSG:4326":
                meta_ok = False
                report["notes"].append(f"CRS '{crs}' tidak sesuai EPSG:4326.")

            if width != 40000 or height != 40000:
                meta_ok = False
                report["notes"].append(f"Dimensi {width}x{height} != 40000x40000.")

            if count != 1 or dtype != "uint8":
                meta_ok = False
                report["notes"].append(f"Band/Dtype {count}/{dtype} != 1/uint8.")

            # Toleransi batas spasial
            if (
                abs(bounds.left - expected_bounds[0]) > 1e-6
                or abs(bounds.bottom - expected_bounds[1]) > 1e-6
                or abs(bounds.right - expected_bounds[2]) > 1e-6
                or abs(bounds.top - expected_bounds[3]) > 1e-6
            ):
                meta_ok = False
                report["notes"].append(f"Bounds {bounds} != {expected_bounds}.")

            # Transform matriks (res = 0.00025, north-up)
            if abs(transform[0] - 0.00025) > 1e-9 or abs(transform[4] - (-0.00025)) > 1e-9:
                meta_ok = False
                report["notes"].append(f"Resolusi spasial transform {transform[0]}, {transform[4]} != 0.00025.")

            report["metadata_valid"] = meta_ok

            # 3. Windowed Pixel Value Audit (Sampling 5 jendela spasial: NW, NE, Center, SW, SE)
            # Setiap jendela berukuran 1000x1000 piksel = 1,000,000 piksel x 5 = 5,000,000 piksel
            sample_windows = [
                ("NW", Window(col_off=1000, row_off=1000, width=1000, height=1000)),
                ("NE", Window(col_off=38000, row_off=1000, width=1000, height=1000)),
                ("Center", Window(col_off=19500, row_off=19500, width=1000, height=1000)),
                ("SW", Window(col_off=1000, row_off=38000, width=1000, height=1000)),
                ("SE", Window(col_off=38000, row_off=38000, width=1000, height=1000)),
            ]

            all_sample_values = []
            pixel_ok = True
            invalid_values_found = []

            for w_label, win in sample_windows:
                arr = src.read(1, window=win)
                uvals, ucounts = np.unique(arr, return_counts=True)
                for v in uvals:
                    if v < min_val_allowed or v > max_val_allowed:
                        pixel_ok = False
                        invalid_values_found.append((int(v), w_label))
                    if v not in all_sample_values:
                        all_sample_values.append(int(v))

            report["pixel_audit"] = {
                "valid_domain": f"[{min_val_allowed}..{max_val_allowed}]",
                "sample_unique_values": sorted(all_sample_values),
                "invalid_values_found": invalid_values_found,
            }

            if pixel_ok:
                report["pixel_values_valid"] = True
            else:
                report["notes"].append(f"Ditemukan nilai di luar domain legal: {invalid_values_found}.")

            # 4. Benchmark Latensi Pembacaan pada Format Strip-Compressed
            # Point read (1x1)
            t_p0 = time.perf_counter()
            _ = src.read(1, window=Window(col_off=20000, row_off=20000, width=1, height=1))
            latency_point_ms = (time.perf_counter() - t_p0) * 1000.0

            # Small window read (100x100 ~ 2.8 km x 2.8 km)
            t_w0 = time.perf_counter()
            local_bench_data = src.read(1, window=Window(col_off=20000, row_off=20000, width=100, height=100))
            latency_win_ms = (time.perf_counter() - t_w0) * 1000.0

            report["read_performance"] = {
                "point_read_1x1_ms": round(latency_point_ms, 2),
                "window_read_100x100_ms": round(latency_win_ms, 2),
                "strip_format_impact": "Pembacaan 1 piksel memerlukan dekompresi 1 strip scanline (40,000 piksel).",
            }

        # 5. Verifikasi Sampel Blok terhadap Sumber Remote UMD GCS
        if verify_remote:
            t_rem0 = time.perf_counter()
            vsicurl_url = f"/vsicurl/{remote_url}"
            try:
                with rasterio.open(vsicurl_url) as remote_src:
                    remote_bench_data = remote_src.read(
                        1, window=Window(col_off=20000, row_off=20000, width=100, height=100)
                    )
                    rem_elapsed = (time.perf_counter() - t_rem0) * 1000.0

                    # Bandingkan piksel per piksel
                    if np.array_equal(local_bench_data, remote_bench_data):
                        report["source_content_verified"] = True
                        report["remote_verification"] = {
                            "method": "VSICURL_HTTP_RANGE_WINDOWED_PIXEL_COMPARE",
                            "window": "100x100 at center (20000, 20000)",
                            "pixels_compared": 10000,
                            "identical_match": True,
                            "remote_fetch_latency_ms": round(rem_elapsed, 2),
                        }
                    else:
                        mismatch_count = int(np.sum(local_bench_data != remote_bench_data))
                        report["notes"].append(f"Ketidakcocokan nilai piksel remote vs lokal: {mismatch_count} piksel.")
                        report["remote_verification"] = {
                            "method": "VSICURL_HTTP_RANGE_WINDOWED_PIXEL_COMPARE",
                            "window": "100x100 at center (20000, 20000)",
                            "pixels_compared": 10000,
                            "identical_match": False,
                            "mismatches": mismatch_count,
                        }
            except Exception as e:
                report["notes"].append(f"Gagal verifikasi remote vsicurl: {e}")
                report["remote_verification"] = {"error": str(e)}

        # Tentukan Overall Status
        if (
            report["download_complete"]
            and report["metadata_valid"]
            and report["pixel_values_valid"]
            and report["source_content_verified"]
        ):
            report["overall_status"] = "VERIFIED"
        else:
            report["overall_status"] = "PARTIAL_OR_FAILED"

    except Exception as e:
        report["notes"].append(f"Error saat membaca rasterio: {e}")

    return report


def audit_manifests_and_safety() -> Dict[str, Any]:
    """Tahap 2B: Memvalidasi integritas manifest, data demo, dan cadangan."""
    audit_res: Dict[str, Any] = {
        "manifests": {},
        "demo_raster_safety": False,
        "backup_subset_safety": False,
        "manifest_overall_valid": True,
        "notes": [],
    }

    # 1. Audit 4 manifest resmi
    for tile in TILES:
        mpath = OFFICIAL_DIR / f"manifest_{tile}_official.json"
        if not mpath.exists():
            audit_res["manifests"][tile] = {"exists": False}
            audit_res["manifest_overall_valid"] = False
            audit_res["notes"].append(f"Manifest {mpath.name} tidak ditemukan.")
            continue

        try:
            with open(mpath, "r", encoding="utf-8") as f:
                mdata = json.load(f)

            layers_meta = mdata.get("layers", {})
            has_all_layers = all(l in layers_meta for l in LAYERS)
            files_exist = all((OFFICIAL_DIR / layers_meta[l]["filename"]).exists() for l in LAYERS if l in layers_meta)

            audit_res["manifests"][tile] = {
                "exists": True,
                "version": mdata.get("manifest_version"),
                "is_full_tile": mdata.get("is_full_tile"),
                "provinces": mdata.get("provinces_covered"),
                "total_size_mb": mdata.get("total_size_mb"),
                "has_all_layers": has_all_layers,
                "files_exist_on_disk": files_exist,
                "checksum_policy_stated": bool(mdata.get("integrity_policy", {}).get("source_checksum_note")),
            }

            if not has_all_layers or not files_exist:
                audit_res["manifest_overall_valid"] = False

        except Exception as e:
            audit_res["manifests"][tile] = {"exists": True, "error": str(e)}
            audit_res["manifest_overall_valid"] = False

    # 2. Audit keamanan raster demonstrasi sintetis di data/raster/hansen/
    demo_files = [
        "Hansen_GFC-2025-v1.13_lossyear_00N_110E.tif",
        "Hansen_GFC-2025-v1.13_treecover2000_00N_110E.tif",
        "Hansen_GFC-2025-v1.13_datamask_00N_110E.tif",
    ]
    all_demo_exist = True
    demo_sizes = {}
    for df in demo_files:
        dfpath = DEMO_DIR / df
        if dfpath.exists():
            demo_sizes[df] = dfpath.stat().st_size
        else:
            all_demo_exist = False

    audit_res["demo_raster_safety"] = all_demo_exist
    audit_res["demo_file_sizes"] = demo_sizes

    # 3. Audit keamanan backup subset lama
    backup_files = [
        "Hansen_GFC-2025-v1.13_lossyear_00N_110E_official.tif",
        "Hansen_GFC-2025-v1.13_treecover2000_00N_110E_official.tif",
        "Hansen_GFC-2025-v1.13_datamask_00N_110E_official.tif",
        "manifest_00N_110E_official.json",
    ]
    all_backup_exist = True
    backup_sizes = {}
    for bf in backup_files:
        bfpath = BACKUP_DIR / bf
        if bfpath.exists():
            backup_sizes[bf] = bfpath.stat().st_size
        else:
            all_backup_exist = False

    audit_res["backup_subset_safety"] = all_backup_exist
    audit_res["backup_file_sizes"] = backup_sizes

    return audit_res


def main():
    print("=" * 80)
    print("   FIREGUARD — AUDIT RASTER HANSEN GFC v1.13 (TAHAP 2A & TAHAP 2B)")
    print("=" * 80)

    # Jalankan audit untuk ke-12 berkas
    all_raster_reports = []
    print("\n[AUDIT 2A] Memeriksa 12 GeoTIFF secara mendalam...")

    for tile in TILES:
        print(f"\n>> Tile: {tile}")
        for layer in LAYERS:
            print(f"   Memeriksa Layer '{layer}'...", end="", flush=True)
            rep = audit_single_raster(tile, layer, verify_remote=True)
            all_raster_reports.append(rep)
            status_str = f"[{rep['overall_status']}]"
            print(f" {status_str}")
            print(f"     Download Complete:  {rep['download_complete']}")
            print(f"     Metadata Valid:     {rep['metadata_valid']}")
            print(f"     Pixel Values Valid: {rep['pixel_values_valid']} (Domain {rep.get('pixel_audit', {}).get('valid_domain')})")
            print(f"     Source Content Verified: {rep['source_content_verified']}")
            if "read_performance" in rep:
                perf = rep["read_performance"]
                print(f"     Latency: 1x1={perf['point_read_1x1_ms']}ms, 100x100={perf['window_read_100x100_ms']}ms")
            if rep["notes"]:
                print(f"     Catatan: {rep['notes']}")

    # Jalankan audit manifest dan keselamatan data
    print("\n[AUDIT 2B] Memeriksa Manifest Provenance dan Keselamatan Data...")
    safety_rep = audit_manifests_and_safety()
    print(f"   Manifest Overall Valid:     {safety_rep['manifest_overall_valid']}")
    print(f"   Demo Raster Safety:         {safety_rep['demo_raster_safety']}")
    print(f"   Backup Subset Safety:       {safety_rep['backup_subset_safety']}")

    # Simpan hasil audit lengkap ke file JSON
    out_json = PROJECT_ROOT / "data" / "raster" / "hansen" / "official" / "audit_tahap2_report.json"
    full_output = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage_2a_rasters": all_raster_reports,
        "stage_2b_safety": safety_rep,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)

    print(f"\n>> Laporan audit lengkap tersimpan di: {out_json}")


if __name__ == "__main__":
    main()
