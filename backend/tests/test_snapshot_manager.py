"""
Pengujian Unit untuk Penyimpanan Snapshot Lokal Tim, Checksum SHA-256, dan Manifest.
"""

from pathlib import Path
from app.snapshot_manager import (
    compute_sha256,
    find_latest_valid_snapshot,
    parse_csv_content,
    save_team_snapshot,
)


def test_save_and_find_team_snapshot(tmp_path: Path):
    """Menguji penyimpanan snapshot mandiri tim dan pembacaan manifest valid."""
    csv_sample = "latitude,longitude,acq_date,acq_time\n0.53,101.44,2026-10-13,0400\n"

    manifest = save_team_snapshot(
        raw_csv_content=csv_sample,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        min_date="2026-10-13",
        max_date="2026-10-13",
        record_count=1
    )

    assert manifest.snapshot_type == "TEAM_LOCAL_CAPTURE"
    assert manifest.checksum_sha256 == compute_sha256(csv_sample)
    assert "Bukan Benchmark Panitia" in manifest.label

    # Temukan snapshot terbaru
    latest = find_latest_valid_snapshot(tmp_path)
    assert latest is not None
    csv_file, found_manifest = latest
    assert csv_file.exists()
    assert found_manifest.checksum_sha256 == manifest.checksum_sha256


def test_tampered_snapshot_rejected(tmp_path: Path):
    """Menguji penolakan snapshot jika file telah dimodifikasi (checksum tidak cocok)."""
    csv_sample = "latitude,longitude,acq_date,acq_time\n0.53,101.44,2026-10-13,0400\n"

    manifest = save_team_snapshot(
        raw_csv_content=csv_sample,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        record_count=1
    )

    # Modifikasi file CSV secara ilegal
    csv_file = tmp_path / manifest.snapshot_filename
    with open(csv_file, "a", encoding="utf-8") as f:
        f.write("tampered,data,0,0\n")

    # Pencarian harus menolak file yang rusak checksum-nya
    latest = find_latest_valid_snapshot(tmp_path)
    assert latest is None


def test_empty_snapshot_dir_returns_none(tmp_path: Path):
    """Menguji pengembalian None jika direktori snapshot kosong."""
    empty_dir = tmp_path / "empty_snapshots"
    empty_dir.mkdir()
    assert find_latest_valid_snapshot(empty_dir) is None
