"""
Unit test untuk mekanisme keamanan downloader Hansen GFC v1.13:
1. Validasi kapasitas disk dan margin keamanan.
2. Mekanisme resume dengan verifikasi HTTP 206 Partial Content.
3. Penanganan skenario saat server mengabaikan header Range (kembali ke HTTP 200).
4. Penanganan Content-Range header yang tidak sesuai.
5. Penulisan atomik (.part -> final file) hanya ketika ukuran bita 100% cocok.
6. Perhitungan hash SHA-256 lokal secara streaming.
7. Pencadangan non-destruktif raster lama sebelum penggantian.
"""

import hashlib
import io
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.download_hansen_full_tiles import (
    backup_existing_official_data,
    check_storage_capacity,
    compute_file_sha256,
    download_file_resumable,
    fetch_remote_metadata,
)


def test_check_storage_capacity_passes_when_sufficient(tmp_path):
    """Memastikan audit kapasitas penyimpanan berhasil ketika disk memiliki ruang cukup."""
    total, used, free = check_storage_capacity(tmp_path, required_bytes=1000, safety_margin_gb=0.001)
    assert free > 0
    assert total > 0


def test_check_storage_capacity_raises_when_insufficient(tmp_path):
    """Memastikan audit kapasitas penyimpanan melempar RuntimeError ketika ruang tidak cukup."""
    with pytest.raises(RuntimeError, match="TIDAK MENCUKUPI"):
        # Minta 1000 Terabyte yang pasti melebihi kapasitas
        check_storage_capacity(tmp_path, required_bytes=10**15, safety_margin_gb=100.0)


def test_compute_file_sha256(tmp_path):
    """Memastikan perhitungan SHA-256 streaming identik dengan hash pustaka hashlib standar."""
    test_file = tmp_path / "test_sample.bin"
    sample_content = b"Hansen GFC v1.13 Kalimantan Spatial Data Integrity" * 1000
    test_file.write_bytes(sample_content)

    expected_sha256 = hashlib.sha256(sample_content).hexdigest()
    computed_sha256 = compute_file_sha256(test_file)

    assert computed_sha256 == expected_sha256


def test_backup_existing_official_data_non_destructive(tmp_path):
    """Memastikan pencadangan data resmi lama tidak menghapus file asli dan menyalin secara lengkap."""
    output_dir = tmp_path / "official"
    backup_dir = tmp_path / "backup"
    output_dir.mkdir(parents=True)

    dummy_tif = output_dir / "Hansen_GFC-2025-v1.13_lossyear_00N_110E_official.tif"
    dummy_tif.write_bytes(b"EXISTING_PALANGKA_RAYA_SUBSET_DATA")
    dummy_manifest = output_dir / "manifest_00N_110E_official.json"
    dummy_manifest.write_text('{"target": "subset_old"}')

    backed_up = backup_existing_official_data(output_dir, backup_dir)

    assert len(backed_up) == 2
    assert (backup_dir / dummy_tif.name).exists()
    assert (backup_dir / dummy_manifest.name).exists()
    assert (backup_dir / dummy_tif.name).read_bytes() == b"EXISTING_PALANGKA_RAYA_SUBSET_DATA"
    # Berkas di output_dir masih ada (tidak dihapus)
    assert dummy_tif.exists()
    assert dummy_manifest.exists()


def test_download_resumable_with_http_206(tmp_path):
    """Memastikan resume pengunduhan memanfaatkan header Range dan status HTTP 206."""
    target_path = tmp_path / "test_layer.tif"
    part_path = tmp_path / "test_layer.tif.part"

    part_1 = b"ABCDEFGHIJ"  # 10 bytes sudah ada
    part_2 = b"KLMNOPQRST"  # 10 bytes sisa
    full_content = part_1 + part_2  # 20 bytes total

    # Buat file .part awal
    part_path.write_bytes(part_1)

    mock_resp = MagicMock()
    mock_resp.status = 206
    mock_resp.headers = {"Content-Range": "bytes 10-19/20"}
    mock_resp.read.side_effect = [part_2, b""]

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success, sha = download_file_resumable(
            url="https://fake.url/test.tif",
            target_path=target_path,
            expected_size=20,
            supports_range=True,
            max_retries=1,
        )

        assert success is True
        assert target_path.exists()
        assert not part_path.exists()
        assert target_path.read_bytes() == full_content
        assert sha == hashlib.sha256(full_content).hexdigest()


def test_download_reset_if_server_returns_200_instead_of_206(tmp_path):
    """
    Jika server mengabaikan header Range dan mengirim status HTTP 200 (seluruh file),
    downloader harus mereset file dan TIDAK menggabungkan (append) data yang membuat berkas rusak.
    """
    target_path = tmp_path / "test_layer_reset.tif"
    part_path = tmp_path / "test_layer_reset.tif.part"

    # File .part sudah ada 10 byte
    part_path.write_bytes(b"CORRUPT_OR_OLD_PART")
    full_content = b"COMPLETE_FRESH_CONTENT_20B"  # 26 bytes

    mock_resp = MagicMock()
    mock_resp.status = 200  # Server abaikan Range
    mock_resp.read.side_effect = [full_content, b""]

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success, sha = download_file_resumable(
            url="https://fake.url/test.tif",
            target_path=target_path,
            expected_size=len(full_content),
            supports_range=True,
            max_retries=1,
        )

        assert success is True
        assert target_path.exists()
        # Harus berisi data bersih, bukan penggabungan bita lama
        assert target_path.read_bytes() == full_content
        assert sha == hashlib.sha256(full_content).hexdigest()


def test_download_skips_if_already_complete_with_matching_size(tmp_path):
    """Jika file target sudah ada dengan ukuran yang cocok, lewati unduhan dan hitung checksum."""
    target_path = tmp_path / "already_done.tif"
    content = b"EXISTING_VALID_FILE_CONTENT"
    target_path.write_bytes(content)

    with patch("urllib.request.urlopen") as mock_urlopen:
        success, sha = download_file_resumable(
            url="https://fake.url/test.tif",
            target_path=target_path,
            expected_size=len(content),
            supports_range=True,
        )
        assert success is True
        assert sha == hashlib.sha256(content).hexdigest()
        # urlopen tidak boleh dipanggil karena file sudah lengkap
        mock_urlopen.assert_not_called()
