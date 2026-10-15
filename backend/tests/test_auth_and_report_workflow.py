from datetime import datetime, timedelta, timezone
from io import BytesIO
import uuid

from fastapi.testclient import TestClient
from PIL import Image

from app import auth, main
from app.main import app, save_report_photo
from app.reports_storage import UserSessionModel, reports_repo


def account(client: TestClient, role: str = "warga", code: str | None = None):
    username = f"qa_{uuid.uuid4().hex[:12]}"
    payload = {
        "username": username,
        "email": f"{username}@example.test",
        "password": "test-password-123",
        "role": role,
    }
    if code is not None:
        payload["institution_code"] = code
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return login.json()["user"], login.json()["access_token"]


def report_payload(**overrides):
    return {
        "category": "asap_kebakaran",
        "latitude": -0.0263,
        "longitude": 109.3425,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "description": "Terlihat asap di area hutan dekat permukiman.",
        "reporter_name": "Nama Privat",
        "reporter_contact": "kontak-privat",
        **overrides,
    }


def test_registration_session_and_logout():
    client = TestClient(app)
    try:
        username = f"logout_{uuid.uuid4().hex[:10]}"
        response = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "test-password-123", "role": "warga"},
        )
        assert response.status_code == 200
        login = client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "test-password-123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        assert client.get("/api/v1/auth/me").json()["user"]["role"] == "warga"

        session = reports_repo.SessionLocal()
        stored = session.query(UserSessionModel).filter_by(user_id=login.json()["user"]["id"]).one()
        stored.expires_at_utc = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        session.commit()
        session.close()
        assert client.get("/api/v1/auth/me").status_code == 401

        fresh_login = client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "test-password-123"},
        )
        client.headers["Authorization"] = f"Bearer {fresh_login.json()['access_token']}"
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
    finally:
        client.close()


def test_citizen_report_requires_auth_and_other_citizen_validates(monkeypatch):
    monkeypatch.setattr(main, "fetch_hotspots_for_reports", lambda reports: ([], False, None))
    client = TestClient(app)
    try:
        unauthenticated = client.post("/api/v1/reports", json=report_payload())
        assert unauthenticated.status_code == 401

        owner, _ = account(client)
        created = client.post("/api/v1/reports", json=report_payload())
        assert created.status_code == 200, created.text
        report = created.json()["data"]
        report_id = report["id"]
        assert report["status"] == "menunggu_validasi"
        assert report["latitude"] == -0.026
        assert report["longitude"] == 109.343
        assert "reporter_contact" not in report
        assert "reporter_name" not in report
        assert "reporter_id" not in report

        self_validation = client.post(f"/api/v1/reports/{report_id}/validate", json={})
        assert self_validation.status_code == 409

        other = TestClient(app)
        account(other)
        validated = other.post(f"/api/v1/reports/{report_id}/validate", json={})
        assert validated.status_code == 200, validated.text
        assert validated.json()["data"]["status"] == "riwayat_kebakaran_validasi_warga"
        assert validated.json()["data"]["citizen_validation_count"] == 1
        duplicate = other.post(f"/api/v1/reports/{report_id}/validate", json={})
        assert duplicate.status_code == 409
        assert owner["id"] != report.get("reporter_id")
        other.close()
    finally:
        client.close()


def test_petugas_registration_code_role_and_audit(monkeypatch):
    monkeypatch.setattr(auth, "PETUGAS_REGISTRATION_CODE", "private-test-code")
    monkeypatch.setattr(main, "fetch_hotspots_for_reports", lambda reports: ([], False, None))
    citizen = TestClient(app)
    officer = TestClient(app)
    try:
        assert citizen.post(
            "/api/v1/auth/register",
            json={
                "username": f"bad_{uuid.uuid4().hex[:8]}",
                "password": "test-password-123",
                "role": "petugas",
                "institution_code": "wrong",
            },
        ).status_code == 403
        account(citizen)
        created = citizen.post("/api/v1/reports", json=report_payload()).json()["data"]
        report_id = created["id"]
        forbidden = citizen.patch(
            f"/api/v1/reports/{report_id}/status",
            json={"status": "terverifikasi_petugas"},
        )
        assert forbidden.status_code == 403

        account(officer, "petugas", "private-test-code")
        invalid_rejection = officer.patch(
            f"/api/v1/reports/{report_id}/status",
            json={"status": "ditolak", "rejection_reason": "singkat"},
        )
        assert invalid_rejection.status_code == 422
        assert officer.patch(
            f"/api/v1/reports/{report_id}/status",
            json={
                "status": "ditolak",
                "rejection_reason": "Koordinat dan bukti foto tidak cocok dengan laporan.",
            },
        ).status_code == 200

        assert officer.get(f"/api/v1/reports/{report_id}/private").status_code == 200
        precise = officer.get(f"/api/v1/reports/{report_id}/private").json()
        assert precise["latitude"] == -0.0263
        audit = officer.get(f"/api/v1/reports/{report_id}/audit").json()
        assert any(event["action"] == "petugas_mengakses_lokasi_presisi" for event in audit["events"])
        assert any(event["action"] == "laporan_status_petugas" for event in audit["events"])
    finally:
        citizen.close()
        officer.close()


def test_reports_and_nearby_alert_scope_privacy_and_settings(monkeypatch):
    monkeypatch.setattr(main, "fetch_hotspots_for_reports", lambda reports: ([], False, None))
    client = TestClient(app)
    try:
        account(client)
        created = client.post("/api/v1/reports", json=report_payload()).json()["data"]
        report_id = created["id"]

        outside_kalimantan = client.post(
            "/api/v1/reports",
            json=report_payload(latitude=0.53, longitude=101.44),
        )
        assert outside_kalimantan.status_code == 422

        nearby = client.get(
            "/api/v1/reports/nearby?latitude=-0.0263&longitude=109.3425&radius_km=1"
        )
        assert nearby.status_code == 200
        assert nearby.json()["count"] >= 1
        match = next(record for record in nearby.json()["records"] if record["id"] == report_id)
        assert match["distance_km"] == 0
        assert "latitude" not in match and "longitude" not in match
        assert "reporter_contact" not in str(nearby.json())
        assert "hotspot" not in nearby.json()["message"].lower()

        saved = client.put(
            "/api/v1/alerts/settings",
            json={"enabled": True, "radius_m": 5000},
        )
        assert saved.status_code == 200
        setting = client.get("/api/v1/alerts/settings").json()
        assert setting["enabled"] is True
        assert setting["radius_m"] == 5000
        assert "last_lat" not in setting and "last_lon" not in setting
    finally:
        client.close()


def test_report_photo_is_reencoded_without_exif(tmp_path):
    image = Image.new("RGB", (8, 8), color="red")
    exif = Image.Exif()
    exif[36867] = "2026:10:15 12:00:00"
    image_bytes = BytesIO()
    image.save(image_bytes, format="JPEG", exif=exif)

    filename, _ = save_report_photo(
        "data:image/jpeg;base64," + __import__("base64").b64encode(image_bytes.getvalue()).decode(),
        tmp_path,
    )
    with Image.open(tmp_path / filename) as sanitized:
        assert not sanitized.getexif()
