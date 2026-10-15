"""
Pengujian Privasi Warga dan Pemisahan Status Penyimpanan vs Penilaian Bukti.
Memverifikasi:
1. Informasi kontak pribadi (reporter_contact) TIDAK PERNAH bocor ke publik melalui API.
2. Koordinat publik disamarkan/dibulatkan (3 desimal) untuk menjaga privasi warga.
3. Status penyimpanan (PENDING) terpisah dari penilaian bukti ilmiah.
4. Kategori hasil penilaian bukti menggunakan 3 kategori terjelaskan:
   - Ada indikasi pendukung
   - Belum ditemukan kecocokan
   - Belum dapat dinilai
5. Kategori kebakaran vs pembukaan lahan memiliki alur analisis berbeda:
   - Kebakaran mencari anomali termal FIRMS (<= 10 km, +- 3 hari).
   - Pembukaan lahan menggunakan Hansen GFC, dan TIDAK menggunakan hotspot sebagai bukti.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient
from app import auth
from app.main import app, pipeline_instance
from app.reports_storage import reports_repo, CitizenReportModel
from app.evidence_service import assess_report_evidence

def authenticated_client(role: str = "warga") -> TestClient:
    username = f"privacy_{uuid.uuid4().hex[:10]}"
    test_client = TestClient(app, client=(username, 50000))
    payload = {
        "username": username,
        "password": "test-password-123",
        "role": role,
    }
    if role == "petugas":
        auth.PETUGAS_REGISTRATION_CODE = "test-institution-code"
        payload["institution_code"] = "test-institution-code"
    registered = test_client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 200, registered.text
    login = test_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return test_client


@pytest.fixture
def client():
    return authenticated_client()


@pytest.fixture
def officer_client():
    return authenticated_client("petugas")


@pytest.fixture(autouse=True)
def clean_reports_db():
    session = reports_repo.SessionLocal()
    session.query(CitizenReportModel).delete()
    session.commit()
    session.close()
    yield


def test_reporter_contact_privacy_never_exposed(client: TestClient):
    """Memastikan bahwa reporter_contact tidak pernah dibocorkan pada endpoint publik mana pun."""
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "kebakaran",
        "latitude": -0.0263,
        "longitude": 109.3425,
        "observed_at_utc": now_utc,
        "description": "Terlihat kepulan asap putih di semak belukar dekat kebun warga.",
        "reporter_name": "Budi Santoso",
        "reporter_contact": "081298765432_RAHASIA",
    }

    # 1. POST /api/v1/reports
    res_post = client.post("/api/v1/reports", json=payload)
    assert res_post.status_code == 200
    post_json = res_post.json()
    assert "reporter_contact" not in post_json["data"]
    assert "081298765432_RAHASIA" not in str(post_json)
    report_id = post_json["data"]["id"]

    # 2. GET /api/v1/reports
    res_list = client.get("/api/v1/reports")
    assert res_list.status_code == 200
    list_json = res_list.json()
    assert "081298765432_RAHASIA" not in str(list_json)
    for rec in list_json["records"]:
        assert "reporter_contact" not in rec
    for feat in list_json["features"]:
        assert "reporter_contact" not in feat["properties"]

    # 3. GET /api/v1/reports/{id}
    res_detail = client.get(f"/api/v1/reports/{report_id}")
    assert res_detail.status_code == 200
    detail_json = res_detail.json()
    assert "reporter_contact" not in detail_json
    assert "081298765432_RAHASIA" not in str(detail_json)


def test_public_coordinates_protection(client: TestClient):
    """Memverifikasi penyamaran koordinat persis menjadi 3 desimal (~110m) untuk perlindungan privasi."""
    now_utc = datetime.now(timezone.utc).isoformat()
    # Koordinat presisi tinggi 6 desimal
    payload = {
        "category": "kebakaran",
        "latitude": -0.026789,
        "longitude": 109.342123,
        "observed_at_utc": now_utc,
        "description": "Kepulan asap terpantau di belakang area permukiman warga.",
        "reporter_name": "Warga Peduli",
    }
    res_post = client.post("/api/v1/reports", json=payload)
    assert res_post.status_code == 200
    data = res_post.json()["data"]

    # Pada tampilan publik, koordinat dibulatkan ke 3 desimal
    assert data["latitude"] == -0.027
    assert data["longitude"] == 109.342


def test_evidence_assessment_separation_fire_category():
    """
    Menguji penilaian bukti kategori kebakaran:
    - Status penyimpanan tetap 'PENDING'.
    - Jika ada hotspot dalam radius 10 km dan rentang waktu: 'Ada indikasi pendukung'.
    - Jika tidak ada hotspot: 'Belum ditemukan kecocokan' (dengan penjelasan bahwa ketiadaan bukan bukti tidak ada api).
    """
    # Kasus A: Ada hotspot cocok
    now_iso = "2026-10-10T04:00:00Z"
    report_fire = {
        "category": "kebakaran",
        "latitude": -0.02,
        "longitude": 109.34,
        "observed_at_utc": now_iso,
        "province": "Kalimantan Barat"
    }
    mock_hotspots = [
        {
            "geometry": {"coordinates": [109.35, -0.02]},  # ~1.1 km jauhnya
            "properties": {
                "satellite": "NOAA-20 (VIIRS)",
                "acq_date": "2026-10-10",
                "acq_time": "0400",
                "confidence": "high",
                "frp": 25.5
            }
        }
    ]
    eval_match = assess_report_evidence(report_fire, hotspots=mock_hotspots, firms_available=True)
    assert eval_match["category_result"] == "Ada indikasi pendukung"
    assert eval_match["assessment_code"] == "SUPPORTING_INDICATION"
    assert eval_match["details"]["distance_km"] < 5.0
    assert "indikasi anomali termal" in eval_match["limitations_caveat"].lower()

    # Kasus B: Tidak ada hotspot cocok
    eval_no_match = assess_report_evidence(report_fire, hotspots=[], firms_available=True)
    assert eval_no_match["category_result"] == "Belum ditemukan kecocokan"
    assert eval_no_match["assessment_code"] == "NO_MATCH_FOUND"
    assert "bukan bukti bahwa tidak ada kebakaran" in eval_no_match["limitations_caveat"].lower()


def test_evidence_assessment_land_clearing_uses_forest_change_not_hotspot():
    """
    Menguji bahwa kategori pembukaan lahan / perubahan tutupan menggunakan Hansen GFC
    dan TIDAK MENGGUNAKAN anomali termal/hotspot sebagai bukti pembukaan lahan.
    Ketika raster tingkat piksel belum tersedia secara lokal, sistem mengembalikan
    INSUFFICIENT_DATA ('Belum dapat dinilai'), BUKAN SUPPORTING_INDICATION palsu
    dan BUKAN NO_MATCH_FOUND.
    """
    report_clearing = {
        "category": "pembukaan_lahan",
        "latitude": -0.05,
        "longitude": 110.35,
        "observed_at_utc": "2026-10-10T08:00:00Z",
        "province": "Kalimantan Barat"
    }
    # Bahkan jika ada hotspot di sekitarnya, analisis tutupan pohon menggunakan data biofisik Hansen
    mock_hotspot_near = [
        {
            "geometry": {"coordinates": [110.351, -0.051]},
            "properties": {"confidence": "high", "frp": 100.0, "acq_date": "2026-10-10", "acq_time": "0800"}
        }
    ]
    eval_clearing = assess_report_evidence(report_clearing, hotspots=mock_hotspot_near, firms_available=True)
    assert eval_clearing["assessment_code"] == "INSUFFICIENT_DATA"
    assert eval_clearing["category_result"] == "Belum dapat dinilai"
    assert eval_clearing["assessment_code"] != "SUPPORTING_INDICATION"
    assert eval_clearing["assessment_code"] != "NO_MATCH_FOUND"
    assert eval_clearing["evidence_type"] == "hansen_gfc_treecover_loss"
    assert "bukan 'belum ditemukan kecocokan'" in eval_clearing["limitations_caveat"].lower()
    assert "tidak secara otomatis membuktikan" in eval_clearing["limitations_caveat"].lower()


def test_land_clearing_report_api_endpoint_insufficient_data_consistency(client: TestClient):
    """
    Memastikan bahwa pembuatan laporan pembukaan lahan di Kalimantan melalui POST /api/v1/reports
    dan pengambilan via GET /api/v1/reports/{id} menghasilkan status bukti INSUFFICIENT_DATA,
    kontak reporter tidak bocor, dan koordinat disamarkan.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "pembukaan_lahan",
        "latitude": -0.051234,
        "longitude": 110.351234,
        "observed_at_utc": now_utc,
        "description": "Terlihat penebangan alat berat di dekat batas konsesi.",
        "reporter_name": "Saksi Warga",
        "reporter_contact": "081299998888_SENSITIF",
    }
    res_post = client.post("/api/v1/reports", json=payload)
    assert res_post.status_code == 200
    post_json = res_post.json()

    # Bukti harus INSUFFICIENT_DATA
    ev = post_json["evidence_assessment"]
    assert ev["assessment_code"] == "INSUFFICIENT_DATA"
    assert ev["category_result"] == "Belum dapat dinilai"
    assert ev["assessment_code"] != "SUPPORTING_INDICATION"
    assert ev["assessment_code"] != "NO_MATCH_FOUND"

    # Privasi kontak dan koordinat
    assert "reporter_contact" not in post_json["data"]
    assert "081299998888_SENSITIF" not in str(post_json)
    assert post_json["data"]["latitude"] == -0.051
    assert post_json["data"]["longitude"] == 110.351

    # GET detail
    rep_id = post_json["data"]["id"]
    res_get = client.get(f"/api/v1/reports/{rep_id}")
    assert res_get.status_code == 200
    get_json = res_get.json()
    assert get_json["evidence_assessment"]["assessment_code"] == "INSUFFICIENT_DATA"
    assert get_json["evidence_assessment"]["category_result"] == "Belum dapat dinilai"
    assert "reporter_contact" not in get_json
    assert "081299998888_SENSITIF" not in str(get_json)


def test_firms_failure_or_unavailable_returns_insufficient_data():
    """
    Jika sinkronisasi atau pengambilan data FIRMS gagal / tidak tersedia,
    hasil harus menunjukkan 'Belum dapat dinilai' (INSUFFICIENT_DATA),
    BUKAN 'Belum ditemukan kecocokan' (NO_MATCH_FOUND).
    """
    report = {
        "category": "kebakaran",
        "latitude": -0.02,
        "longitude": 109.34,
        "observed_at_utc": "2026-10-10T04:00:00Z",
        "province": "Kalimantan Barat"
    }

    # 1. FIRMS unavailable
    eval_unavail = assess_report_evidence(report, hotspots=[], firms_available=False)
    assert eval_unavail["assessment_code"] == "INSUFFICIENT_DATA"
    assert eval_unavail["category_result"] == "Belum dapat dinilai"
    assert eval_unavail["assessment_code"] != "NO_MATCH_FOUND"
    assert "gagal" in eval_unavail["summary"].lower() or "tidak tersedia" in eval_unavail["summary"].lower()

    # 2. Hotspots is None
    eval_none = assess_report_evidence(report, hotspots=None, firms_available=True)
    assert eval_none["assessment_code"] == "INSUFFICIENT_DATA"
    assert eval_none["category_result"] == "Belum dapat dinilai"
    assert eval_none["assessment_code"] != "NO_MATCH_FOUND"


def test_pipeline_failure_in_api_returns_insufficient_data(client: TestClient):
    """
    Ketika pipeline_instance.run melempar exception atau status NO_DATA_AVAILABLE,
    endpoint laporan warga mengembalikan status INSUFFICIENT_DATA pada bukti laporan kebakaran.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    with patch.object(pipeline_instance, "run", side_effect=Exception("NASA FIRMS network outage")):
        res_post = client.post("/api/v1/reports", json={
            "category": "kebakaran",
            "latitude": -0.0263,
            "longitude": 109.3425,
            "observed_at_utc": now_utc,
            "description": "Kepulan asap terlihat di tepi kebun kelapa sawit.",
        })
        assert res_post.status_code == 200
        post_json = res_post.json()
        ev = post_json["evidence_assessment"]
        assert ev["assessment_code"] == "INSUFFICIENT_DATA"
        assert ev["category_result"] == "Belum dapat dinilai"
        assert ev["assessment_code"] != "NO_MATCH_FOUND"

        rep_id = post_json["data"]["id"]
        res_get = client.get(f"/api/v1/reports/{rep_id}")
        assert res_get.status_code == 200
        get_json = res_get.json()
        assert get_json["evidence_assessment"]["assessment_code"] == "INSUFFICIENT_DATA"
        assert get_json["evidence_assessment"]["category_result"] == "Belum dapat dinilai"


def test_historical_report_outside_coverage_returns_insufficient_data():
    """
    Laporan kebakaran historis di luar cakupan tanggal observasi yang tersedia
    harus mengembalikan INSUFFICIENT_DATA, bukan NO_MATCH_FOUND.
    """
    hist_report = {
        "category": "kebakaran",
        "latitude": -0.02,
        "longitude": 109.34,
        "observed_at_utc": "2024-05-15T10:00:00Z",
        "province": "Kalimantan Barat"
    }
    available_hotspots = [
        {
            "geometry": {"coordinates": [109.34, -0.02]},
            "properties": {"acq_date": "2026-10-10", "acq_time": "0400"}
        }
    ]
    cov_range = {"min": "2026-10-07", "max": "2026-10-13"}

    eval_hist = assess_report_evidence(
        report=hist_report,
        hotspots=available_hotspots,
        firms_available=True,
        coverage_date_range=cov_range
    )
    assert eval_hist["assessment_code"] == "INSUFFICIENT_DATA"
    assert eval_hist["category_result"] == "Belum dapat dinilai"
    assert eval_hist["assessment_code"] != "NO_MATCH_FOUND"
    assert "belum tersedia dalam cakupan data" in eval_hist["summary"].lower()


def test_full_privacy_across_all_endpoints_and_db_persistence(
    client: TestClient,
    officer_client: TestClient,
):
    """
    Audit komprehensif privasi:
    1. POST, GET list, GET detail, dan PATCH status tidak mengekspos reporter_contact.
    2. Semua endpoint publik membulatkan koordinat ke 3 desimal (~110m).
    3. GeoJSON features menggunakan koordinat yang dibulatkan.
    4. Database SQLite internal tetap menyimpan koordinat float presisi tinggi dan kontak.
    """
    high_prec_lat = -0.123456
    high_prec_lon = 109.876543
    secret_contact = "081122334455_CONFIDENTIAL"
    now_utc = datetime.now(timezone.utc).isoformat()

    payload = {
        "category": "pembukaan_lahan",
        "latitude": high_prec_lat,
        "longitude": high_prec_lon,
        "observed_at_utc": now_utc,
        "description": "Laporan pengujian privasi koordinat dan kontak pelapor.",
        "reporter_name": "Warga Kalimantan",
        "reporter_contact": secret_contact,
    }

    # 1. POST /api/v1/reports
    res_post = client.post("/api/v1/reports", json=payload)
    assert res_post.status_code == 200
    post_data = res_post.json()["data"]
    rep_id = post_data["id"]
    assert "reporter_contact" not in post_data
    assert secret_contact not in str(res_post.json())
    assert post_data["latitude"] == -0.123
    assert post_data["longitude"] == 109.877

    # 2. GET /api/v1/reports (list & GeoJSON)
    res_list = client.get("/api/v1/reports")
    assert res_list.status_code == 200
    list_json = res_list.json()
    assert secret_contact not in str(list_json)
    matched_record = next(r for r in list_json["records"] if r["id"] == rep_id)
    assert "reporter_contact" not in matched_record
    assert matched_record["latitude"] == -0.123
    assert matched_record["longitude"] == 109.877

    matched_feature = next(f for f in list_json["features"] if f["id"] == rep_id)
    assert matched_feature["geometry"]["coordinates"] == [109.877, -0.123]
    assert "reporter_contact" not in matched_feature["properties"]

    # 3. GET /api/v1/reports/{id} (detail)
    res_detail = client.get(f"/api/v1/reports/{rep_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert "reporter_contact" not in detail_data
    assert secret_contact not in str(detail_data)
    assert detail_data["latitude"] == -0.123
    assert detail_data["longitude"] == 109.877

    # 4. PATCH /api/v1/reports/{id}/status
    res_patch = officer_client.patch(
        f"/api/v1/reports/{rep_id}/status",
        json={"status": "IN_REVIEW", "verification_notes": "Sedang diteliti tim."}
    )
    assert res_patch.status_code == 200
    patch_data = res_patch.json()["data"]
    assert "reporter_contact" not in patch_data
    assert secret_contact not in str(res_patch.json())
    assert patch_data["latitude"] == -0.123
    assert patch_data["longitude"] == 109.877

    # 5. Verifikasi bahwa database internal SQLite mempertahankan koordinat presisi tinggi
    session = reports_repo.SessionLocal()
    try:
        db_model = session.query(CitizenReportModel).filter(CitizenReportModel.id == rep_id).first()
        assert db_model is not None
        assert abs(db_model.latitude - high_prec_lat) < 1e-6
        assert abs(db_model.longitude - high_prec_lon) < 1e-6
        assert db_model.reporter_contact == secret_contact
    finally:
        session.close()


def test_hansen_demonstration_stats_transparency_consistency(client: TestClient):
    """
    Statistik demonstrasi Hansen tetap ditandai secara konsisten pada seluruh endpoint
    dan tidak disajikan sebagai data terverifikasi.
    """
    # 1. /api/v1/forest-loss/summary
    res_summary = client.get("/api/v1/forest-loss/summary")
    assert res_summary.status_code == 200
    sum_json = res_summary.json()
    assert sum_json["data_status"] == "demonstration"
    assert sum_json["data_verified"] is False
    assert "verification_notes" in sum_json
    assert "demonstrasi" in sum_json["verification_notes"].lower()
    for prov in sum_json["provincial_data"]:
        assert prov["data_status"] == "demonstration"
        assert prov["data_verified"] is False
        assert "verification_notes" in prov

    # 2. /api/v1/boundaries/kalimantan
    res_bounds = client.get("/api/v1/boundaries/kalimantan")
    assert res_bounds.status_code == 200
    bounds_json = res_bounds.json()
    for feat in bounds_json.get("features", []):
        props = feat.get("properties", {})
        assert props.get("data_status") == "demonstration"
        assert props.get("data_verified") is False
        assert "verification_notes" in props

    # 3. /api/v1/forest-loss/point (titik di Kalimantan tanpa raster lokal)
    res_pt = client.get("/api/v1/forest-loss/point?latitude=-0.05&longitude=110.35&province=Kalimantan+Barat")
    assert res_pt.status_code == 200
    pt_json = res_pt.json()
    assert pt_json["status"] == "INSUFFICIENT_DATA"
    assert pt_json["category_result"] == "Belum dapat dinilai"
    assert pt_json["data_status"] == "demonstration"
    assert pt_json["data_verified"] is False
