"""
scripts/download_glad_kalimantan_full.py
Skrip Pengunduhan Resmi Berkas Penuh GLAD Forest Extent 2020 untuk Pulau Kalimantan.

Sumber Resmi:
University of Maryland (GLAD / Potapov et al., 2022)
URL Direktori: https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/{tile_id}.tif

4 Tile Resmi yang Diperlukan:
1. 00N_100E: Kalbar Barat Daya (1,531 MB)
2. 00N_110E: Kalteng & Kalsel (1,531 MB)
3. 10N_100E: Kalbar Utara & Sarawak Barat (1,531 MB)
4. 10N_110E: Kaltim, Kaltara, Sarawak Timur, Sabah, Brunei (1,531 MB)

Fitur:
- Resumable download (HTTP Range header)
- Validasi integritas Rasterio (dimensi 40.000x40.000, CRS EPSG:4326, bounds)
- Progress bar detail (MB, %, kecepatan, ETA)
- Penyimpanan ke direktori terpisah: data/raster/forest/tiles_full/
"""

import argparse
import sys
import time
import ssl
from pathlib import Path
import urllib.request
import urllib.error

OFFICIAL_GLAD_BASE_URL = "https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/"
KALIMANTAN_TILES = ["00N_100E", "00N_110E", "10N_100E", "10N_110E"]
OUTPUT_DIR = Path("data/raster/forest/tiles_full")

EXPECTED_TILE_BOUNDS = {
    "00N_100E": (100.0, -10.0, 110.0, 0.0),
    "00N_110E": (110.0, -10.0, 120.0, 0.0),
    "10N_100E": (100.0, 0.0, 110.0, 10.0),
    "10N_110E": (110.0, 0.0, 120.0, 10.0),
}


def format_bytes(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def get_remote_file_size(url: str, ctx: ssl.SSLContext) -> int:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FireGuard/1.0")
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        cl = resp.headers.get("Content-Length")
        return int(cl) if cl else 0


def validate_downloaded_tile(tile_path: Path, tile_id: str) -> bool:
    """Memvalidasi integritas berkas GeoTIFF GLAD menggunakan Rasterio."""
    try:
        import rasterio
    except ImportError:
        print("  [WARN] rasterio belum terpasang, lewati validasi geospasial.")
        return True

    try:
        with rasterio.open(str(tile_path)) as src:
            if src.shape != (40000, 40000):
                print(f"  [FAIL] Dimensi piksel salah: {src.shape}, diharapkan (40000, 40000).")
                return False
            if str(src.crs).upper() not in ("EPSG:4326", "WGS 84"):
                print(f"  [FAIL] CRS salah: {src.crs}, diharapkan EPSG:4326.")
                return False

            b = src.bounds
            exp_b = EXPECTED_TILE_BOUNDS.get(tile_id)
            if exp_b:
                if (abs(b.left - exp_b[0]) > 0.001 or
                    abs(b.bottom - exp_b[1]) > 0.001 or
                    abs(b.right - exp_b[2]) > 0.001 or
                    abs(b.top - exp_b[3]) > 0.001):
                    print(f"  [FAIL] Bounds salah: {b}, diharapkan {exp_b}.")
                    return False

            print(f"  [PASS] Validasi Rasterio sukses: {src.shape}, {src.crs}, Bounds: {b}")
            return True
    except Exception as exc:
        print(f"  [FAIL] Gagal membaca GeoTIFF: {exc}")
        return False


def download_tile(tile_id: str, dest_dir: Path, dry_run: bool = False) -> bool:
    url = f"{OFFICIAL_GLAD_BASE_URL}{tile_id}.tif"
    dest_file = dest_dir / f"{tile_id}.tif"
    part_file = dest_dir / f"{tile_id}.tif.part"

    ctx = ssl.create_default_context()

    print(f"\n--- Memeriksa Tile GLAD: {tile_id} ---")
    print(f"URL: {url}")

    try:
        remote_size = get_remote_file_size(url, ctx)
        print(f"Ukuran di Server UMD: {format_bytes(remote_size)} ({remote_size:,} bytes)")
    except Exception as exc:
        print(f"[ERROR] Gagal menghubungi server UMD: {exc}")
        return False

    if dry_run:
        print("[DRY-RUN] Selesai memeriksa metadata server.")
        return True

    # Jika file selesai sudah ada dan ukurannya cocok, validasi langsung
    if dest_file.exists():
        local_size = dest_file.stat().st_size
        if local_size == remote_size:
            print(f"[INFO] Berkas utuh sudah ada ({format_bytes(local_size)}). Memvalidasi...")
            if validate_downloaded_tile(dest_file, tile_id):
                print(f"[OK] Tile {tile_id} terverifikasi dan siap digunakan.")
                return True
            else:
                print(f"[WARN] Berkas korup, mengunduh ulang...")
                dest_file.unlink()

    # Cek part file untuk resume
    existing_bytes = 0
    if part_file.exists():
        existing_bytes = part_file.stat().st_size
        if existing_bytes >= remote_size:
            part_file.replace(dest_file)
            return validate_downloaded_tile(dest_file, tile_id)
        print(f"[RESUME] Melanjutkan unduhan dari byte ke-{existing_bytes:,} ({format_bytes(existing_bytes)})...")

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FireGuard/1.0")
    if existing_bytes > 0:
        req.add_header("Range", f"bytes={existing_bytes}-")

    dest_dir.mkdir(parents=True, exist_ok=True)
    mode = "ab" if existing_bytes > 0 else "wb"

    chunk_size = 1024 * 1024  # 1 MB chunk
    start_time = time.time()
    last_print = start_time
    downloaded = existing_bytes

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp, open(part_file, mode) as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_print >= 2.0 or downloaded == remote_size:
                    elapsed = now - start_time
                    speed = (downloaded - existing_bytes) / elapsed if elapsed > 0 else 0
                    pct = (downloaded / remote_size) * 100 if remote_size > 0 else 0
                    remaining = (remote_size - downloaded) / speed if speed > 0 else 0
                    eta_min = int(remaining // 60)
                    eta_sec = int(remaining % 60)

                    sys.stdout.write(
                        f"\r  Unduh: {format_bytes(downloaded)} / {format_bytes(remote_size)} "
                        f"({pct:5.1f}%) | Kecepatan: {format_bytes(int(speed))}/s | "
                        f"ETA: {eta_min:02d}m:{eta_sec:02d}s"
                    )
                    sys.stdout.flush()
                    last_print = now

        print()
        if downloaded == remote_size:
            part_file.replace(dest_file)
            print(f"[SUKSES] Unduhan {tile_id}.tif selesai. Memvalidasi...")
            return validate_downloaded_tile(dest_file, tile_id)
        else:
            print(f"[WARN] Unduhan terhenti pada {format_bytes(downloaded)}. Jalankan kembali untuk melanjutkan.")
            return False

    except Exception as exc:
        print(f"\n[ERROR] Unduhan terganggu: {exc}")
        print(f"[INFO] Bagian yang sudah diunduh ({format_bytes(downloaded)}) tersimpan di {part_file.name}. Dapat dilanjutkan kembali.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pengunduh Resmi GLAD Forest Extent 2020 Full Tiles Kalimantan")
    parser.add_argument("--tile", choices=KALIMANTAN_TILES, help="Unduh 1 tile tertentu")
    parser.add_argument("--all", action="store_true", help="Unduh seluruh 4 tile Kalimantan")
    parser.add_argument("--dry-run", action="store_true", help="Cek ketersediaan dan ukuran file tanpa mengunduh")
    parser.add_argument("--dest-dir", default=str(OUTPUT_DIR), help="Direktori penyimpanan berkas penuh")
    args = parser.parse_args()

    dest = Path(args.dest_dir)
    target_tiles = [args.tile] if args.tile else KALIMANTAN_TILES if args.all else []

    if not target_tiles:
        parser.print_help()
        print("\nContoh penggunaan:")
        print("  python scripts/download_glad_kalimantan_full.py --dry-run")
        print("  python scripts/download_glad_kalimantan_full.py --tile 00N_110E")
        print("  python scripts/download_glad_kalimantan_full.py --all")
        return

    print("==================================================================")
    print("   PENGUNDUH RESMI GLAD FOREST EXTENT 2020 - PULAU KALIMANTAN     ")
    print("==================================================================")
    print(f"Direktori Target: {dest.resolve()}")
    print(f"Jumlah Tile     : {len(target_tiles)}")

    results = {}
    for t in target_tiles:
        ok = download_tile(t, dest, dry_run=args.dry_run)
        results[t] = ok

    print("\n==================================================================")
    print("                      RINGKASAN HASIL                             ")
    print("==================================================================")
    for t, ok in results.items():
        status = "SUKSES" if ok else ("CEK BERHASIL" if args.dry_run else "GAGAL / TERTUNDA")
        print(f"Tile {t}: {status}")


if __name__ == "__main__":
    main()
