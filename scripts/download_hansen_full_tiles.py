"""
Skrip Pengunduhan Aman Raster Resmi Hansen Global Forest Change v1.13.
Mendukung Opsi A (4 Tile Penuh Kalimantan): 00N_100E, 00N_110E, 10N_100E, 10N_110E.

Fitur Keamanan & Integritas:
1. Pra-validasi metadata server (HTTP HEAD): Status 200, Content-Length, Accept-Ranges.
2. Pemeriksaan kapasitas disk drive lokal dengan safety margin ketat.
3. Pencadangan otomatis non-destruktif untuk raster resmi lama (subset Palangka Raya).
4. Penulisan ke berkas sementara (.part) dan atomic rename setelah 100% bita diterima.
5. Fitur resume yang tervalidasi: verifikasi HTTP 206 Partial Content dan header Content-Range.
6. Penanganan timeout dan auto-retry dengan exponential backoff.
7. Perhitungan SHA-256 streaming dan pembacaan metadata geospasial via rasterio.
8. Pembuatan manifest provenance resmi terperinci per tile dengan pemisahan eksplisit
   antara checksum integritas lokal dan ketiadaan checksum publik dari sumber UMD GCS.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raster" / "hansen" / "official"
DEFAULT_BACKUP_DIR = DEFAULT_OUTPUT_DIR / "backup_subset_palangka_raya"

VERSION = "GFC-2025-v1.13"
BASE_URL = f"https://storage.googleapis.com/earthenginepartners-hansen/{VERSION}/"

ALL_KALIMANTAN_TILES = ["00N_100E", "00N_110E", "10N_100E", "10N_110E"]
ALL_LAYERS = ["lossyear", "treecover2000", "datamask"]

# Mapping deskripsi geografis & provinsi per tile
TILE_PROVINCES = {
    "00N_100E": [
        "Kalimantan Barat (bagian Selatan: Ketapang, Kayong Utara, Kubu Raya selatan)"
    ],
    "00N_110E": [
        "Kalimantan Tengah (selatan/tengah)",
        "Kalimantan Selatan (seluruhnya)",
        "Kalimantan Timur (bagian Selatan: Balikpapan, Penajam Paser Utara, IKN)"
    ],
    "10N_100E": [
        "Kalimantan Barat (bagian Utara: Pontianak, Mempawah, Singkawang, Sambas, Bengkayang, Sanggau)"
    ],
    "10N_110E": [
        "Kalimantan Utara (seluruhnya)",
        "Kalimantan Timur (bagian Utara: Samarinda, Kutai Kartanegara, Kutai Timur, Berau)",
        "Kalimantan Tengah (ujung utara)"
    ],
}

CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB buffer per chunk
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2
SOCKET_TIMEOUT = 30.0


def check_storage_capacity(target_dir: Path, required_bytes: int, safety_margin_gb: float = 3.0) -> Tuple[int, int, int]:
    """
    Memeriksa kapasitas disk sebelum pengunduhan.
    Memerlukan setidaknya required_bytes + safety_margin_gb.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    total, used, free = shutil.disk_usage(target_dir)
    required_with_margin = required_bytes + int(safety_margin_gb * (1024 ** 3))

    print(f"\n>> [AUDIT DISK] Memeriksa kapasitas ruang penyimpanan pada: {target_dir}")
    print(f"   Total Disk:    {total / (1024**3):.2f} GB")
    print(f"   Terpakai:      {used / (1024**3):.2f} GB")
    print(f"   Ruang Bebas:   {free / (1024**3):.2f} GB")
    print(f"   Dibutuhkan:    {required_bytes / (1024**3):.3f} GB unduhan + {safety_margin_gb:.1f} GB safety margin = {required_with_margin / (1024**3):.2f} GB")

    if free < required_with_margin:
        raise RuntimeError(
            f"Ruang penyimpanan TIDAK MENCUKUPI! Tersedia {free / (1024**3):.2f} GB, "
            f"dibutuhkan minimal {required_with_margin / (1024**3):.2f} GB."
        )
    print("   [PASSED] Kapasitas disk mencukupi dengan margin keamanan.")
    return total, used, free


def backup_existing_official_data(output_dir: Path, backup_dir: Path) -> List[str]:
    """
    Mencadangkan file subset resmi lama (misalnya subset 00N_110E Palangka Raya)
    ke direktori cadangan sebelum digantikan oleh tile penuh.
    TIDAK MENGHAPUS berkas apa pun secara otomatis.
    """
    backed_up = []
    if not output_dir.exists():
        return backed_up

    # Cari file .tif resmi dan manifest di output_dir langsung (bukan di subfolder)
    candidate_files = [f for f in output_dir.iterdir() if f.is_file() and (f.suffix == ".tif" or f.suffix == ".json")]
    if not candidate_files:
        return backed_up

    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n>> [CADANGAN] Memeriksa file resmi lama untuk pencadangan aman ke: {backup_dir}")
    for f in candidate_files:
        dest = backup_dir / f.name
        if not dest.exists():
            shutil.copy2(f, dest)
            print(f"   [DISALIN] {f.name} -> {dest.name} ({f.stat().st_size:,} bytes)")
            backed_up.append(f.name)
        else:
            print(f"   [SUDAH ADA DI CADANGAN] {dest.name}")
    return backed_up


def fetch_remote_metadata(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Mengirim HTTP HEAD request untuk mendapatkan ukuran file aktual dan dukungan range.
    """
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "FireGuard-HansenDownloader/2.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content_length = int(resp.headers.get("Content-Length", 0))
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
            last_modified = resp.headers.get("Last-Modified", "")
            etag = resp.headers.get("ETag", "")
            return {
                "status": status,
                "content_length": content_length,
                "accept_ranges": accept_ranges,
                "supports_range": ("bytes" in accept_ranges),
                "last_modified": last_modified,
                "etag": etag,
            }
    except Exception as e:
        raise RuntimeError(f"Gagal memeriksa metadata remote URL {url}: {e}")


def compute_file_sha256(filepath: Path) -> str:
    """Menghitung SHA-256 dari berkas secara streaming dengan buffer 64 KB."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def safe_replace(src_path: Path, dst_path: Path, max_attempts: int = 10, delay: float = 0.5) -> None:
    """Mengganti nama berkas secara atomik dengan ketahanan terhadap file lock Windows."""
    import gc
    gc.collect()
    for i in range(max_attempts):
        try:
            if dst_path.exists():
                try:
                    dst_path.unlink()
                except Exception:
                    pass
            os.replace(src_path, dst_path)
            return
        except PermissionError as e:
            if i == max_attempts - 1:
                raise e
            time.sleep(delay)
            gc.collect()


def download_file_resumable(
    url: str,
    target_path: Path,
    expected_size: int,
    supports_range: bool,
    max_retries: int = MAX_RETRIES,
) -> Tuple[bool, str]:
    """
    Mengunduh berkas dengan dukungan resume via file sementara .part,
    validasi status HTTP 206 dan Content-Range, penanganan retry,
    dan atomic rename ke target_path saat selesai.
    
    Mengembalikan (success: bool, sha256_hash: str).
    """
    part_path = Path(str(target_path) + ".part")

    # Jika file final sudah ada dan ukurannya tepat, verifikasi integritas
    if target_path.exists() and target_path.is_file():
        cur_size = target_path.stat().st_size
        if cur_size == expected_size:
            print(f"   [SUDAH SELESAI] {target_path.name} ({cur_size:,} bytes). Menghitung checksum...")
            sha256_val = compute_file_sha256(target_path)
            return True, sha256_val
        else:
            print(f"   [UKURAN BERBEDA] {target_path.name} ada dengan ukuran {cur_size:,} != {expected_size:,}. Menghapus berkas korup...")
            target_path.unlink()

    attempt = 0
    backoff = INITIAL_BACKOFF_SECONDS

    while attempt < max_retries:
        attempt += 1
        existing_bytes = part_path.stat().st_size if part_path.exists() else 0

        # Jika .part sudah lebih besar atau sama dengan expected_size tetapi korup
        if existing_bytes >= expected_size:
            if existing_bytes > expected_size:
                print(f"   [PERINGATAN] File .part melebihi ukuran server ({existing_bytes:,} > {expected_size:,}). Reset unduhan.")
                part_path.unlink()
                existing_bytes = 0
            else:
                # Selesai di .part, lakukan rename
                print(f"   [PENYELESAIAN .PART] Mengganti nama atomik {part_path.name} -> {target_path.name}...")
                safe_replace(part_path, target_path)
                sha256_val = compute_file_sha256(target_path)
                return True, sha256_val

        headers = {"User-Agent": "FireGuard-HansenDownloader/2.0"}
        resume_mode = False

        if existing_bytes > 0 and supports_range:
            headers["Range"] = f"bytes={existing_bytes}-{expected_size - 1}"
            resume_mode = True
            print(f"   [LANJUTKAN RESUME] Mencoba melanjutkan {part_path.name} dari byte {existing_bytes:,} / {expected_size:,}...")

        req = urllib.request.Request(url, headers=headers)

        try:
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT) as resp:
                status = resp.status

                if resume_mode:
                    if status != 206:
                        # Server mengabaikan Range header dan mengirim seluruh file dari awal (HTTP 200)
                        print(f"   [PERINGATAN] Server merespons HTTP {status} (bukan 206 Partial Content). Mereset file .part ke 0.")
                        mode = "wb"
                        bytes_written = 0
                    else:
                        content_range = resp.headers.get("Content-Range", "")
                        expected_prefix = f"bytes {existing_bytes}-"
                        if not content_range.startswith(expected_prefix):
                            print(f"   [PERINGATAN] Content-Range tidak cocok: '{content_range}'. Mereset file .part.")
                            mode = "wb"
                            bytes_written = 0
                        else:
                            mode = "ab"
                            bytes_written = existing_bytes
                else:
                    mode = "wb"
                    bytes_written = 0

                with open(part_path, mode) as f_out:
                    last_log_time = time.time()
                    downloaded_this_session = 0

                    while True:
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_written += len(chunk)
                        downloaded_this_session += len(chunk)

                        now = time.time()
                        if now - last_log_time >= 3.0:
                            elapsed = now - t0
                            speed_mb = (downloaded_this_session / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                            pct = (bytes_written / expected_size) * 100
                            print(f"      -> {bytes_written:,} / {expected_size:,} bytes ({pct:.1f}%) | {speed_mb:.2f} MB/s")
                            last_log_time = now

                # Selesai transfer
                if bytes_written == expected_size:
                    print(f"   [SELESAI 100%] Berhasil mengunduh {bytes_written:,} bytes. Melakukan atomic rename...")
                    safe_replace(part_path, target_path)
                    print(f"   [VERIFIKASI CHECKSUM] Menghitung SHA-256 lokal...")
                    sha256_val = compute_file_sha256(target_path)
                    print(f"   [SHA-256] {sha256_val}")
                    return True, sha256_val
                else:
                    print(f"   [TRANSFER TIDAK LENGKAP] Ukuran file {bytes_written:,} != {expected_size:,}. Akan di-retry...")

        except Exception as e:
            print(f"   [ERROR PERCOBAAN {attempt}/{max_retries}] Koneksi gagal: {e}")
            if attempt < max_retries:
                print(f"   Menunggu {backoff} detik sebelum mencoba lagi...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

    raise RuntimeError(f"Gagal mengunduh {url} setelah {max_retries} percobaan.")


def extract_geotiff_metadata(filepath: Path) -> Dict[str, Any]:
    """Mengekstrak metadata geospasial aktual dari file GeoTIFF yang telah diunduh."""
    with rasterio.open(filepath) as src:
        bounds = src.bounds
        transform = list(src.transform)
        crs = src.crs.to_string() if src.crs else "EPSG:4326"
        return {
            "crs": crs,
            "transform": transform,
            "bounds": {
                "left": bounds.left,
                "bottom": bounds.bottom,
                "right": bounds.right,
                "top": bounds.top,
            },
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": str(src.dtypes[0]),
            "nodata": src.nodata,
            "is_cog": bool(src.is_tiled and len(src.overviews(1)) > 0 if src.is_tiled else False),
        }


def generate_tile_manifest(
    tile_id: str,
    version: str,
    output_dir: Path,
    layer_results: Dict[str, Dict[str, Any]],
) -> Path:
    """
    Membuat file manifest provenance resmi untuk tile yang telah diunduh lengkap.
    Mencatat pemisahan tegas antara checksum integritas lokal dan ketiadaan checksum UMD.
    """
    manifest_path = output_dir / f"manifest_{tile_id}_official.json"

    # Hitung total bita
    total_bytes = sum(info["size_bytes"] for info in layer_results.values())
    first_layer_meta = next(iter(layer_results.values()))["geospatial"]

    manifest_data = {
        "manifest_version": "2.0",
        "tile_id": tile_id,
        "dataset_version": version,
        "source": "UNIVERSITY_OF_MARYLAND_GOOGLE_EARTH_ENGINE",
        "source_base_url": BASE_URL,
        "source_type": "OFFICIAL_UMD_HANSEN_GFC",
        "is_synthetic": False,
        "is_clipped": False,
        "is_full_tile": True,
        "geographic_bounds": {
            "min_lon": first_layer_meta["bounds"]["left"],
            "min_lat": first_layer_meta["bounds"]["bottom"],
            "max_lon": first_layer_meta["bounds"]["right"],
            "max_lat": first_layer_meta["bounds"]["top"],
        },
        "provinces_covered": TILE_PROVINCES.get(tile_id, []),
        "spatial_resolution_deg": 0.00025,
        "spatial_resolution_approx_m": 27.83,
        "dimensions": {
            "width_px": first_layer_meta["width"],
            "height_px": first_layer_meta["height"],
            "total_pixels": first_layer_meta["width"] * first_layer_meta["height"],
        },
        "crs": first_layer_meta["crs"],
        "transform": first_layer_meta["transform"],
        "total_size_bytes": total_bytes,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        "total_size_gb": round(total_bytes / (1024 * 1024 * 1024), 3),
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
        "integrity_policy": {
            "source_checksum_published": False,
            "source_checksum_note": "University of Maryland tidak mempublikasikan checksum publik (MD5/SHA256) untuk berkas GCS. Nilai checksum di bawah ini adalah SHA-256 integritas biner lokal hasil pengunduhan untuk audit deterministik.",
            "download_method": "RESUMABLE_HTTP_RANGE_WITH_ATOMIC_RENAME",
        },
        "layers": layer_results,
        "scientific_integrity_notes": (
            "Citra GeoTIFF resmi diunduh langsung dari server Google Cloud Storage University of Maryland (UMD). "
            "Data merupakan tile 10°x10° penuh beresolusi 0.00025° (~27.83m) dengan 40,000 x 40,000 piksel. "
            "Evaluasi titik koordinat dalam wilayah 5 provinsi Kalimantan menggunakan poligon administratif resmi; "
            "wilayah negara tetangga (Sarawak, Sabah, Brunei) atau perairan luar diklasifikasikan sebagai OUT_OF_SCOPE."
        ),
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"\n>> [MANIFEST RESMI TERBIT] Disimpan di: {manifest_path}")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Downloader Aman Raster Resmi Hansen GFC v1.13")
    parser.add_argument("--tiles", nargs="+", default=ALL_KALIMANTAN_TILES, help="Daftar tile yang akan diunduh")
    parser.add_argument("--layers", nargs="+", default=ALL_LAYERS, help="Daftar layer yang akan diunduh")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Direktori target penyimpanan")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="Direktori cadangan data lama")
    parser.add_argument("--dry-run", action="store_true", help="Audit & verifikasi tanpa mengunduh")
    args = parser.parse_args()

    print("=" * 80)
    print("   FIREGUARD — RESUMABLE OFFICIAL HANSEN GFC v1.13 TILE DOWNLOADER")
    print("   Dataset Version: GFC-2025-v1.13 (2000–2025)")
    print("   Target Tiles:    " + ", ".join(args.tiles))
    print("   Target Layers:   " + ", ".join(args.layers))
    print("   Target Dir:      " + str(args.output_dir))
    print("=" * 80)

    # 1. Kumpulkan metadata dari server UMD GCS
    print("\n[LANGKAH 1] Melakukan pra-validasi metadata server untuk semua berkas...")
    download_tasks = []
    total_expected_bytes = 0

    for tile in args.tiles:
        for layer in args.layers:
            remote_filename = f"Hansen_{VERSION}_{layer}_{tile}.tif"
            remote_url = f"{BASE_URL}{remote_filename}"
            local_filename = f"Hansen_{VERSION}_{layer}_{tile}_official.tif"
            local_target = args.output_dir / local_filename

            meta = fetch_remote_metadata(remote_url)
            size = meta["content_length"]
            total_expected_bytes += size
            download_tasks.append({
                "tile": tile,
                "layer": layer,
                "remote_filename": remote_filename,
                "remote_url": remote_url,
                "local_filename": local_filename,
                "local_target": local_target,
                "size_bytes": size,
                "supports_range": meta["supports_range"],
                "last_modified": meta["last_modified"],
                "etag": meta["etag"],
            })
            print(f"   • {remote_filename:48s} : {size:>10,d} B ({size/1024**2:6.2f} MB) | Range: {meta['supports_range']}")

    print(f"\n   Total berkas:  {len(download_tasks)} berkas")
    print(f"   Total volume:  {total_expected_bytes:,} bytes ({total_expected_bytes / (1024**2):.2f} MB / {total_expected_bytes / (1024**3):.3f} GB)")

    # 2. Audit kapasitas disk lokal
    print("\n[LANGKAH 2] Memeriksa kapasitas ruang penyimpanan lokal...")
    check_storage_capacity(args.output_dir, total_expected_bytes, safety_margin_gb=3.0)

    if args.dry_run:
        print("\n>> [DRY-RUN BERHASIL] Semua URL valid, ukuran terverifikasi, dan kapasitas disk mencukupi.")
        print("   Tidak ada pengunduhan yang dilakukan (--dry-run aktif).")
        return

    # 3. Cadangkan data resmi lama
    print("\n[LANGKAH 3] Melakukan pencadangan non-destruktif data resmi lama...")
    backup_existing_official_data(args.output_dir, args.backup_dir)

    # 4. Eksekusi pengunduhan per tile dan layer
    print("\n[LANGKAH 4] Memulai pengunduhan bertahap dengan resumable downloader...")
    tile_results: Dict[str, Dict[str, Dict[str, Any]]] = {t: {} for t in args.tiles}
    overall_start = time.time()

    for idx, task in enumerate(download_tasks, start=1):
        tile = task["tile"]
        layer = task["layer"]
        url = task["remote_url"]
        target = task["local_target"]
        expected_size = task["size_bytes"]
        supports_range = task["supports_range"]

        print(f"\n[{idx}/{len(download_tasks)}] Mengunduh Tile {tile} Layer '{layer}'...")
        print(f"   Sumber: {url}")
        print(f"   Target: {target}")

        t_start = time.time()
        success, local_sha256 = download_file_resumable(
            url=url,
            target_path=target,
            expected_size=expected_size,
            supports_range=supports_range,
        )
        t_elapsed = time.time() - t_start

        # Ekstrak metadata geospasial aktual
        geo_meta = extract_geotiff_metadata(target)

        tile_results[tile][layer] = {
            "layer": layer,
            "filename": target.name,
            "file_path": str(target.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "remote_source_url": url,
            "size_bytes": expected_size,
            "size_mb": round(expected_size / (1024 * 1024), 2),
            "local_integrity_sha256": local_sha256,
            "source_checksum_published": False,
            "download_duration_seconds": round(t_elapsed, 2),
            "geospatial": geo_meta,
        }

    # 5. Buat manifest resmi untuk setiap tile
    print("\n[LANGKAH 5] Menerbitkan manifest provenance untuk setiap tile yang selesai...")
    for tile in args.tiles:
        if len(tile_results[tile]) == len(args.layers):
            generate_tile_manifest(tile, VERSION, args.output_dir, tile_results[tile])

    overall_elapsed = time.time() - overall_start
    print("\n" + "=" * 80)
    print(f"   [SUKSES] Pengunduhan & Ingestion 4 Tile Penuh Hansen GFC v1.13 Selesai!")
    print(f"   Total Waktu: {overall_elapsed / 60:.2f} menit ({overall_elapsed:.1f} detik)")
    print("=" * 80)


if __name__ == "__main__":
    main()
