"""
Manajer Snapshot Lokal Tim.
Menyimpan data hasil penarikan API sebagai snapshot lokal tim beserta checksum SHA-256,
serta menyediakan pembaca fallback saat koneksi API tidak tersedia.
"""

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import SnapshotManifest


def compute_sha256(content: str) -> str:
    """Menghitung hash SHA-256 dari teks."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_team_snapshot(
    raw_csv_content: str,
    source: str,
    sensor_product: str,
    query_params: Dict[str, Any],
    snapshots_dir: Path,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    record_count: int = 0
) -> SnapshotManifest:
    """
    Menyimpan snapshot hasil penarikan live API ke disk lokal tim beserta manifest.
    Diberi label eksplisit sebagai hasil penarikan mandiri tim, bukan data benchmark panitia.
    """
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    timestamp_tag = now_utc.strftime("%Y%m%d_%H%M%S")
    fetched_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    csv_filename = f"snapshot_team_{timestamp_tag}.csv"
    manifest_filename = f"manifest_{timestamp_tag}.json"

    csv_path = snapshots_dir / csv_filename
    manifest_path = snapshots_dir / manifest_filename

    # Simpan file CSV mentah
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(raw_csv_content)

    checksum = compute_sha256(raw_csv_content)

    manifest = SnapshotManifest(
        snapshot_filename=csv_filename,
        snapshot_type="TEAM_LOCAL_CAPTURE",
        label="Snapshot Hasil Pengambilan Mandiri Tim (Bukan Benchmark Panitia)",
        fetched_at_utc=fetched_at_utc,
        source=source,
        sensor_product=sensor_product,
        observation_date_range={"min": min_date, "max": max_date},
        query_parameters=query_params,
        record_count=record_count,
        checksum_sha256=checksum
    )

    # Simpan manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, indent=2)

    # Rotasi otomatis: simpan maksimal 5 snapshot terakhir agar disk server tidak penuh
    for old_manifest in sorted(snapshots_dir.glob("manifest_*.json"), reverse=True)[5:]:
        old_tag = old_manifest.stem.replace("manifest_", "")
        (snapshots_dir / f"snapshot_team_{old_tag}.csv").unlink(missing_ok=True)
        old_manifest.unlink(missing_ok=True)

    return manifest


def find_latest_valid_snapshot(snapshots_dir: Path) -> Optional[Tuple[Path, SnapshotManifest]]:
    """
    Mencari snapshot tim lokal terbaru yang ada di direktori dan memvalidasi integritas checksum-nya.
    Mengembalikan (path_csv, manifest) jika ditemukan dan valid, atau None jika tidak ada file valid.
    """
    if not snapshots_dir.exists():
        return None

    manifest_files = sorted(snapshots_dir.glob("manifest_*.json"), reverse=True)
    for m_file in manifest_files:
        try:
            with open(m_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest = SnapshotManifest(**data)
            csv_path = snapshots_dir / manifest.snapshot_filename

            if not csv_path.exists():
                continue

            # Verifikasi checksum SHA-256
            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()
            if compute_sha256(content) == manifest.checksum_sha256:
                return csv_path, manifest
        except Exception:
            continue

    return None


def parse_csv_content(csv_text: str) -> List[Dict[str, str]]:
    """Mengurai string CSV menjadi daftar dictionary baris."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    return [dict(row) for row in reader]
