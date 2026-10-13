from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_endpoint():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "apiConfigured" in data
    assert "activeMode" in data
    assert "disclaimer" in data


def test_hotspots_snapshot_mode():
    response = client.get("/api/v1/hotspots?mode=snapshot&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "snapshot"
    assert data["count"] > 0
    assert len(data["records"]) <= 10
    first = data["records"][0]
    assert "latitude" in first
    assert "longitude" in first
    assert "confidence" in first
    assert "satellite" in first

