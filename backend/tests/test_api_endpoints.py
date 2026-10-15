"""
Pengujian Unit dan Integrasi untuk Endpoint FastAPI.
Menguji kondisi:
1. Data tidak tersedia (kunci belum ada & tanpa snapshot).
2. Fallback snapshot tim lokal.
3. Status layer konteks (hutan & gambut).
4. Validasi parameter input (HTTP 422 untuk nilai tidak valid).
5. Filter query parameters (confidence, min_frp, province).
"""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.main import app, pipeline_instance
from app.snapshot_manager import save_team_snapshot


@pytest.fixture
def client():
    return TestClient(app)


def test_get_context_layers(client: TestClient):
    """Menguji endpoint /api/v1/context-layers melaporkan layer secara transparan tanpa mengarang data."""
    response = client.get("/api/v1/context-layers")
    assert response.status_code == 200
    data = response.json()

    assert data["forest_layer"]["available"] is False
    assert "belum tersedia" in data["forest_layer"]["status_message"]

    assert data["peatland_layer"]["available"] is False
    assert "belum tersedia" in data["peatland_layer"]["status_message"]

    assert data["boundary_layer"]["available"] is True
    assert data["boundary_layer"]["feature_count"] == 5


def test_get_hotspots_no_key_and_no_snapshot(client: TestClient, tmp_path: Path):
    """Menguji respons ketika MAP_KEY kosong dan belum ada snapshot tim tersimpan."""
    # Arahkan snapshot dir ke direktori kosong
    original_snapshots_dir = pipeline_instance.snapshots_dir
    original_key = pipeline_instance.map_key
    try:
        pipeline_instance.snapshots_dir = tmp_path
        pipeline_instance.map_key = ""

        response = client.get("/api/v1/hotspots")
        assert response.status_code == 200
        data = response.json()

        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 0
        prov = data["provenance"]
        assert prov["data_source"] == "NONE"
        assert "belum dikonfigurasi" in prov["status_message"]
    finally:
        pipeline_instance.snapshots_dir = original_snapshots_dir
        pipeline_instance.map_key = original_key


def test_get_provenance_no_data(client: TestClient, tmp_path: Path):
    """Menguji endpoint /api/v1/provenance saat status NO_DATA_AVAILABLE."""
    original_snapshots_dir = pipeline_instance.snapshots_dir
    original_key = pipeline_instance.map_key
    try:
        pipeline_instance.snapshots_dir = tmp_path
        pipeline_instance.map_key = ""

        response = client.get("/api/v1/provenance")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "NO_DATA_AVAILABLE"
        assert data["is_snapshot"] is False
        assert data["data_source"] == "NONE"
    finally:
        pipeline_instance.snapshots_dir = original_snapshots_dir
        pipeline_instance.map_key = original_key


def test_get_hotspots_fallback_snapshot(client: TestClient, tmp_path: Path):
    """Menguji pemuatan data dari snapshot lokal tim saat live API offline."""
    # Siapkan file snapshot sintetis berlabel test di folder sementara
    sample_csv = (
        "latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti4,bright_ti5,frp,daynight\n"
        "0.53,101.44,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,320.0,295.0,15.5,D\n"
        "-2.21,113.92,2026-10-13,0415,20,VIIRS,high,2.0NRT,335.0,300.0,42.0,D\n"
    )

    save_team_snapshot(
        raw_csv_content=sample_csv,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        min_date="2026-10-13",
        max_date="2026-10-13",
        record_count=2
    )

    original_snapshots_dir = pipeline_instance.snapshots_dir
    original_key = pipeline_instance.map_key
    try:
        pipeline_instance.snapshots_dir = tmp_path
        pipeline_instance.map_key = ""

        response = client.get("/api/v1/hotspots")
        assert response.status_code == 200
        data = response.json()

        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        prov = data["provenance"]
        assert prov["is_snapshot"] is True
        assert prov["data_source"] == "LOCAL_TEAM_SNAPSHOT"
        assert prov["snapshot_type"] == "TEAM_LOCAL_CAPTURE"

        # Uji juga endpoint /api/v1/provenance
        prov_resp = client.get("/api/v1/provenance")
        assert prov_resp.status_code == 200
        prov_data = prov_resp.json()
        assert prov_data["status"] == "FALLBACK_LOCAL_SNAPSHOT"
        assert prov_data["is_snapshot"] is True
    finally:
        pipeline_instance.snapshots_dir = original_snapshots_dir
        pipeline_instance.map_key = original_key


def test_get_hotspots_query_filters(client: TestClient, tmp_path: Path):
    """Menguji filter query parameters: confidence, min_frp, dan province."""
    sample_csv = (
        "latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti4,bright_ti5,frp,daynight\n"
        "0.53,101.44,2026-10-13,0400,20,VIIRS,nominal,2.0NRT,320.0,295.0,15.5,D\n"
        "-2.21,113.92,2026-10-13,0415,20,VIIRS,high,2.0NRT,335.0,300.0,42.0,D\n"
    )
    save_team_snapshot(
        raw_csv_content=sample_csv,
        source="NASA_FIRMS_API",
        sensor_product="VIIRS_NOAA20_NRT",
        query_params={"bbox": "95,-11,141,6"},
        snapshots_dir=tmp_path,
        record_count=2
    )

    original_snapshots_dir = pipeline_instance.snapshots_dir
    original_key = pipeline_instance.map_key
    try:
        pipeline_instance.snapshots_dir = tmp_path
        pipeline_instance.map_key = ""

        # Filter confidence 'high'
        resp_conf = client.get("/api/v1/hotspots?confidence=high")
        assert resp_conf.status_code == 200
        feats_conf = resp_conf.json()["features"]
        assert len(feats_conf) == 1
        assert feats_conf[0]["properties"]["confidence"] == "high"

        # Filter min_frp >= 20.0
        resp_frp = client.get("/api/v1/hotspots?min_frp=20.0")
        assert resp_frp.status_code == 200
        feats_frp = resp_frp.json()["features"]
        assert len(feats_frp) == 1
        assert feats_frp[0]["properties"]["frp"] == 42.0

        # Filter province 'Riau'
        resp_prov = client.get("/api/v1/hotspots?province=riau")
        assert resp_prov.status_code == 200
        feats_prov = resp_prov.json()["features"]
        assert len(feats_prov) == 1
        assert "Riau" in feats_prov[0]["properties"]["province"]
    finally:
        pipeline_instance.snapshots_dir = original_snapshots_dir
        pipeline_instance.map_key = original_key


def test_get_hotspots_invalid_params(client: TestClient):
    """Menguji penolakan parameter tidak valid dengan status HTTP 422 Unprocessable Entity."""
    # days di bawah 1
    resp_days_low = client.get("/api/v1/hotspots?days=0")
    assert resp_days_low.status_code == 422

    # days di atas 10
    resp_days_high = client.get("/api/v1/hotspots?days=15")
    assert resp_days_high.status_code == 422

    # min_frp negatif
    resp_frp_neg = client.get("/api/v1/hotspots?min_frp=-5.0")
    assert resp_frp_neg.status_code == 422
