"""
Pengujian Integrasi Klien NASA FIRMS dan Manajemen Pemulihan Snapshot.

PERINGATAN TESTING:
Seluruh pengujian dalam berkas ini menggunakan MOCK HTTPX terkontrol untuk menguji
respons API NASA FIRMS dalam berbagai skenario (sukses, rate limit, error server, HTML error,
respons kosong, dan kegagalan jaringan) TANPA melakukan panggilan internet riil.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.config import BOUNDARIES_PATH
from app.firms_client import FirmsAPIError, FirmsClient
from app.pipeline import HotspotPipeline
from app.snapshot_manager import (
    find_latest_valid_snapshot,
    save_team_snapshot,
)


# ==============================================================================
# 1. Pengujian Penanganan Error Klien FIRMS (HTTP & Format Response)
# ==============================================================================

def test_firms_client_no_key_raises_error():
    """Klien wajib melempar FirmsAPIError jika API key kosong."""
    client = FirmsClient(map_key="")
    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "FIRMS_MAP_KEY belum dikonfigurasi" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_http_401_403_access_denied(mock_get):
    """Menguji penanganan kode status HTTP 401 dan 403 (kunci salah / tidak aktif)."""
    mock_get.return_value = httpx.Response(status_code=403, text="Forbidden")
    client = FirmsClient(map_key="dummy_invalid_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "Akses ditolak oleh NASA FIRMS (HTTP 403)" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_http_429_rate_limit(mock_get):
    """Menguji penanganan rate limit / kuota terlampaui (HTTP 429)."""
    mock_get.return_value = httpx.Response(status_code=429, text="Too Many Requests")
    client = FirmsClient(map_key="dummy_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "Batas transaksi/kuota permintaan NASA FIRMS terlampaui (HTTP 429)" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_http_500_server_error(mock_get):
    """Menguji penanganan server error / downtime (HTTP 500+)."""
    mock_get.return_value = httpx.Response(status_code=503, text="Service Unavailable")
    client = FirmsClient(map_key="dummy_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "Layanan server NASA FIRMS sedang mengalami gangguan (HTTP 503)" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_html_error_page_detection(mock_get):
    """Menguji respons error berupa halaman HTML (misal dari Cloudflare / Gateway)."""
    html_error = "<!DOCTYPE html><html><head><title>504 Gateway Timeout</title></head><body>Timeout</body></html>"
    mock_get.return_value = httpx.Response(status_code=200, text=html_error)
    client = FirmsClient(map_key="dummy_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "halaman web HTML" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_corrupt_non_csv(mock_get):
    """Menguji respons teks rusak yang tidak memiliki kolom header standar."""
    mock_get.return_value = httpx.Response(status_code=200, text="Internal system diagnostic failure at line 42")
    client = FirmsClient(map_key="dummy_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "tidak memiliki header kolom standar" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_text_error_indicator(mock_get):
    """Menguji respons status HTTP 200 tetapi berisi teks penolakan dari NASA FIRMS."""
    mock_get.return_value = httpx.Response(status_code=200, text="Invalid MAP_KEY.")
    client = FirmsClient(map_key="dummy_key")

    with pytest.raises(FirmsAPIError) as exc_info:
        client.fetch_area_hotspots()
    assert "FIRMS_MAP_KEY tidak valid menurut server NASA" in str(exc_info.value)


@patch("httpx.Client.get")
def test_firms_client_valid_empty_csv(mock_get):
    """Menguji respons CSV sah yang hanya berisi header (0 hotspot)."""
    header_only = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    mock_get.return_value = httpx.Response(status_code=200, text=header_only)
    client = FirmsClient(map_key="dummy_key")

    result = client.fetch_area_hotspots(total_days=2)
    assert "latitude" in result
    assert "longitude" in result
    # Baris data = 0
    lines = [ln for ln in result.strip().splitlines() if ln]
    assert len(lines) == 1


# ==============================================================================
# 2. Pengujian Alur Pipeline, Snapshot Persistence, dan Fallback Recovery
# ==============================================================================

@patch("app.firms_client.FirmsClient.fetch_area_hotspots")
def test_pipeline_live_success_saves_snapshot(mock_fetch, tmp_path: Path):
    """
    Ketika live API berhasil dan mengembalikan data valid:
    - Status wajib LIVE_API.
    - Snapshot tim lokal baru wajib tersimpan dengan manifest dan checksum SHA-256.
    """
    valid_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
    )
    mock_fetch.return_value = valid_csv

    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key="valid_mock_key"
    )

    result = pipeline.run(total_days=5)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    prov = result["provenance"]
    assert prov["status"] == "LIVE_API"
    assert prov["data_source"] == "NASA_FIRMS_API"
    assert prov["is_snapshot"] is False

    # Verifikasi bahwa file snapshot dan manifest benar-benar tersimpan di tmp_path
    latest = find_latest_valid_snapshot(tmp_path)
    assert latest is not None
    csv_path, manifest = latest
    assert csv_path.exists()
    assert manifest.record_count == 1
    assert manifest.source == "NASA_FIRMS_API"


@patch("app.firms_client.FirmsClient.fetch_area_hotspots")
def test_pipeline_api_failure_fallback_and_no_snapshot_overwrite(mock_fetch, tmp_path: Path):
    """
    Ketika live API gagal (misal koneksi terputus):
    - Sistem wajib beralih ke snapshot lokal tim yang sudah ada (status FALLBACK_LOCAL_SNAPSHOT).
    - Snapshot valid yang sudah ada TIDAK BOLEH tertimpa atau rusak akibat kegagalan API.
    """
    # 1. Simpan snapshot valid awal
    initial_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-12,0400,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
    )
    save_team_snapshot(
        raw_csv_content=initial_csv,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        record_count=1
    )

    # Catat snapshot sebelum pemanggilan gagal
    snapshot_before = find_latest_valid_snapshot(tmp_path)
    assert snapshot_before is not None
    csv_before, manifest_before = snapshot_before

    # 2. Simulasikan kegagalan live API
    mock_fetch.side_effect = FirmsAPIError("Koneksi jaringan ke NASA FIRMS gagal: Connection timed out")

    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key="valid_mock_key"
    )

    result = pipeline.run(total_days=5)

    # 3. Verifikasi respons fallback
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    prov = result["provenance"]
    assert prov["status"] == "FALLBACK_LOCAL_SNAPSHOT"
    assert prov["data_source"] == "LOCAL_TEAM_SNAPSHOT"
    assert prov["is_snapshot"] is True
    assert "Panggilan API gagal" in prov["status_message"]

    # 4. Verifikasi bahwa file snapshot lama tetap utuh dan checksum tidak berubah
    snapshot_after = find_latest_valid_snapshot(tmp_path)
    assert snapshot_after is not None
    csv_after, manifest_after = snapshot_after
    assert csv_after == csv_before
    assert manifest_after.checksum_sha256 == manifest_before.checksum_sha256


@patch("app.firms_client.FirmsClient.fetch_area_hotspots")
def test_pipeline_empty_csv_does_not_overwrite_prior_rich_snapshot(mock_fetch, tmp_path: Path):
    """
    Jika live API mengembalikan CSV kosong (header saja tanpa baris),
    respons live harus menampilkan 0 fitur (LIVE_API),
    tetapi snapshot historis yang sudah ada TIDAK DITIMPA oleh file kosong.
    """
    # 1. Simpan snapshot valid historis
    historical_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "0.53,101.44,325.4,0.4,0.4,2026-10-12,0400,20,VIIRS,nominal,2.0NRT,295.1,15.5,D\n"
    )
    save_team_snapshot(
        raw_csv_content=historical_csv,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        record_count=1
    )

    # 2. Live API mengembalikan CSV kosong (hanya header)
    empty_header_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    )
    mock_fetch.return_value = empty_header_csv

    pipeline = HotspotPipeline(
        boundaries_path=BOUNDARIES_PATH,
        snapshots_dir=tmp_path,
        map_key="valid_mock_key"
    )

    result = pipeline.run(total_days=2)

    # Respons live sah tapi kosong
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 0
    assert result["provenance"]["status"] == "LIVE_API"

    # Snapshot historis tetap menjadi latest valid snapshot (tidak ditimpa oleh file kosong)
    latest_snap = find_latest_valid_snapshot(tmp_path)
    assert latest_snap is not None
    _, manifest = latest_snap
    assert manifest.record_count == 1


@patch("httpx.Client.get")
def test_firms_client_chunking_uses_start_date_and_no_date_for_latest_window(mock_get):
    """Chunk pertama tanpa end_date wajib tanpa date_str, chunk kedua wajib memakai start_date."""
    header = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    mock_get.return_value = httpx.Response(status_code=200, text=header)
    client = FirmsClient(map_key="dummy_key")
    client.fetch_area_hotspots(total_days=7)

    urls = [call.args[0] for call in mock_get.call_args_list]
    assert len(urls) == 2
    assert urls[0].endswith("/5")
    assert "/2/" in urls[1]

