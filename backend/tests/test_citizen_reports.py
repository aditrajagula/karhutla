"""
Suite Pengujian Fitur Pelaporan Masyarakat (Citizen Reports).
Menguji:
1. Pembuatan laporan valid dalam batas daratan Indonesia.
2. Penolakan koordinat di luar wilayah Indonesia.
3. Validasi kategori, waktu masa depan, dan batas minimum deskripsi.
4. Deteksi otomatis kandidat duplikasi (radius 5 km & selisih waktu 24 jam).
5. Alur verifikasi operator (PENDING -> IN_REVIEW -> VERIFIED / REJECTED).
6. Filter query dan detail laporan.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.reports_storage import reports_repo, ReportStatus, ReportCategory, CitizenReportModel

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_reports_db():
    session = reports_repo.SessionLocal()
    session.query(CitizenReportModel).delete()
    session.commit()
    session.close()
    yield


def test_reports_meta():
    """Memastikan endpoint metadata kategori dan status laporan mengembalikan nilai yang sah."""
    response = client.get("/api/v1/reports-meta")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "statuses" in data
    cat_vals = [c["value"] for c in data["categories"]]
    assert "kebakaran" in cat_vals
    assert "pembukaan_lahan" in cat_vals
    assert "perubahan_tutupan" in cat_vals


def test_create_valid_report():
    """Laporan dengan koordinat valid di daratan Riau berhasil disimpan."""
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "kebakaran",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "Terlihat kepulan asap putih tebal di area semak dekat parit gambut.",
        "reporter_name": "Warga Peduli Gambut",
        "reporter_contact": "08123456789",
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_duplicate_suspect"] is False
    rep = data["data"]
    assert rep["category"] == "kebakaran"
    assert rep["status"] == "PENDING"
    assert "rep_" in rep["id"]
    assert rep["province"] is not None
    assert "Riau" in rep["province"]


def test_create_report_outside_indonesia():
    """Laporan di luar wilayah daratan Indonesia harus ditolak dengan HTTP 422."""
    now_utc = datetime.now(timezone.utc).isoformat()
    # Koordinat di laut Jawa (masuk rentang bbox, tapi di luar daratan)
    payload = {
        "category": "kebakaran",
        "latitude": -5.0,
        "longitude": 108.0,
        "observed_at_utc": now_utc,
        "description": "Asap terlihat di laut lepas jauh dari daratan.",
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json().get("detail", ""))
    assert "luar batas daratan" in err_detail.lower() or "indonesia" in err_detail.lower()


def test_create_report_invalid_category():
    """Kategori tidak sah harus ditolak dengan HTTP 422."""
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "banjir_bandang",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "Banjir melanda area perkebunan warga.",
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json().get("detail", ""))
    assert "kategori" in err_detail.lower()


def test_create_report_future_time():
    """Waktu observasi di masa depan harus ditolak dengan HTTP 422."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    payload = {
        "category": "pembukaan_lahan",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": future_time,
        "description": "Alat berat terindikasi mulai menebang kayu hutan.",
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json().get("detail", ""))
    assert "masa depan" in err_detail.lower()


def test_create_report_description_too_short():
    """Deskripsi kurang dari 10 karakter harus ditolak dengan HTTP 422."""
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "kebakaran",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "api asap",  # hanya 8 karakter
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422


def test_duplicate_detection_workflow():
    """
    Dua laporan pada kategori sama dan lokasi berjarak dekat (< 5 km)
    dalam rentang 24 jam harus ditandai sebagai is_duplicate_suspect.
    Laporan asli TIDAK boleh dihapus.
    """
    obs_time = datetime.now(timezone.utc).isoformat()

    # Laporan pertama di daratan Kalimantan Barat
    payload1 = {
        "category": "pembukaan_lahan",
        "latitude": -0.05,
        "longitude": 110.35,
        "observed_at_utc": obs_time,
        "description": "Lahan gambut di perbatasan desa sedang dibuka dengan ekskavator.",
    }
    res1 = client.post("/api/v1/reports", json=payload1)
    assert res1.status_code == 200
    data1 = res1.json()
    id1 = data1["data"]["id"]
    assert data1["is_duplicate_suspect"] is False

    # Laporan kedua berjarak ~500 meter di kategori dan waktu yang sama
    payload2 = {
        "category": "pembukaan_lahan",
        "latitude": -0.052,
        "longitude": 110.353,
        "observed_at_utc": obs_time,
        "description": "Melihat pembukaan lahan semak dengan alat berat di lokasi yang sama.",
    }
    res2 = client.post("/api/v1/reports", json=payload2)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate_suspect"] is True
    assert data2["duplicate_of_id"] == id1
    # Kedua laporan tetap ada di sistem
    assert data2["data"]["id"] != id1


def test_get_reports_list_and_filters():
    """Menguji endpoint GET /api/v1/reports dan filter kategori."""
    now_utc = datetime.now(timezone.utc).isoformat()
    client.post("/api/v1/reports", json={
        "category": "kebakaran",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "Laporan uji kebakaran untuk filter query.",
    })
    client.post("/api/v1/reports", json={
        "category": "pembukaan_lahan",
        "latitude": -0.05,
        "longitude": 110.35,
        "observed_at_utc": now_utc,
        "description": "Laporan uji pembukaan lahan untuk filter query.",
    })

    response = client.get("/api/v1/reports?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "features" in data
    assert data["count"] >= 2

    # Filter berdasarkan kategori kebakaran
    res_cat = client.get("/api/v1/reports?category=kebakaran")
    assert res_cat.status_code == 200
    for r in res_cat.json()["records"]:
        assert r["category"] == "kebakaran"


def test_operator_verification_status_update():
    """Menguji verifikasi oleh operator: PENDING -> IN_REVIEW -> VERIFIED / REJECTED."""
    # 1. Buat laporan uji baru
    now_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "category": "perubahan_tutupan",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "Penebangan pohon di zona penyangga hutan lindung.",
    }
    res_create = client.post("/api/v1/reports", json=payload)
    assert res_create.status_code == 200
    rep_id = res_create.json()["data"]["id"]

    # 2. Operator meninjau (IN_REVIEW)
    patch_review = {
        "status": "IN_REVIEW",
        "verification_notes": "Petugas pos kehutanan telah ditugaskan melakukan pengecekan.",
    }
    res_review = client.patch(f"/api/v1/reports/{rep_id}/status", json=patch_review)
    assert res_review.status_code == 200
    assert res_review.json()["data"]["status"] == "IN_REVIEW"
    assert res_review.json()["data"]["verification_notes"] == patch_review["verification_notes"]

    # 3. Status REJECTED tanpa alasan harus gagal (HTTP 422)
    res_reject_no_reason = client.patch(
        f"/api/v1/reports/{rep_id}/status",
        json={"status": "REJECTED", "rejection_reason": ""}
    )
    assert res_reject_no_reason.status_code == 422

    # 4. Operator menolak dengan alasan sah
    patch_reject = {
        "status": "REJECTED",
        "verification_notes": "Pengecekan drone tidak menemukan aktivitas penebangan.",
        "rejection_reason": "Bukan aktivitas perambahan hutan, hanya pembersihan kebun warga berizin.",
    }
    res_reject = client.patch(f"/api/v1/reports/{rep_id}/status", json=patch_reject)
    assert res_reject.status_code == 200
    assert res_reject.json()["data"]["status"] == "REJECTED"
    assert res_reject.json()["data"]["rejection_reason"] == patch_reject["rejection_reason"]

    # 5. Verifikasi terkonfirmasi (VERIFIED)
    patch_verify = {
        "status": "VERIFIED",
        "verification_notes": "Dikonfirmasi oleh tim patroli lapangan.",
    }
    res_verify = client.patch(f"/api/v1/reports/{rep_id}/status", json=patch_verify)
    assert res_verify.status_code == 200
    assert res_verify.json()["data"]["status"] == "VERIFIED"


def test_get_report_by_id():
    """Menguji GET /api/v1/reports/{report_id} sukses dan kasus 404 jika tidak ditemukan."""
    res_404 = client.get("/api/v1/reports/rep_nonexistent123")
    assert res_404.status_code == 404

    now_utc = datetime.now(timezone.utc).isoformat()
    res_new = client.post("/api/v1/reports", json={
        "category": "kebakaran",
        "latitude": 0.53,
        "longitude": 101.44,
        "observed_at_utc": now_utc,
        "description": "Laporan pengujian untuk get by id endpoint.",
    })
    target_id = res_new.json()["data"]["id"]

    res_found = client.get(f"/api/v1/reports/{target_id}")
    assert res_found.status_code == 200
    assert res_found.json()["id"] == target_id


def test_role_based_auth_and_petugas_verification():
    """
    Menguji alur login Warga vs Petugas:
    - Warga dapat login & mengirim laporan, namun ditolak (403) jika mencoba memverifikasi laporan.
    - Petugas dapat login & memverifikasi laporan hingga berstatus VERIFIED.
    """
    # 1. Login sebagai Warga
    res_warga = client.post(
        "/api/v1/auth/login",
        json={"email": "warga@jagaborneo.id", "password": "warga123"},
    )
    assert res_warga.status_code == 200
    warga_token = res_warga.json()["token"]
    assert res_warga.json()["user"]["role"] == "warga"

    # 2. Warga mengirim laporan
    now_utc = datetime.now(timezone.utc).isoformat()
    res_rep = client.post(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {warga_token}"},
        json={
            "category": "kebakaran",
            "latitude": -2.21,
            "longitude": 113.92,
            "observed_at_utc": now_utc,
            "description": "Kepulan asap tebal di sekitar lahan gambut Palangka Raya.",
        },
    )
    assert res_rep.status_code == 200
    rep_id = res_rep.json()["data"]["id"]

    # 3. Warga mencoba memverifikasi laporan -> harus ditolak 403 Forbidden
    res_forbidden = client.patch(
        f"/api/v1/reports/{rep_id}/status",
        headers={"Authorization": f"Bearer {warga_token}"},
        json={"status": "VERIFIED", "verification_notes": "Coba verifikasi sendiri"},
    )
    assert res_forbidden.status_code == 403

    # 4. Login sebagai Petugas
    res_petugas = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@jagaborneo.id", "password": "admin123"},
    )
    assert res_petugas.status_code == 200
    petugas_token = res_petugas.json()["token"]
    assert res_petugas.json()["user"]["role"] == "petugas"

    # 5. Petugas memverifikasi laporan -> sukses 200 OK
    res_verify = client.patch(
        f"/api/v1/reports/{rep_id}/status",
        headers={"Authorization": f"Bearer {petugas_token}"},
        json={
            "status": "VERIFIED",
            "verification_notes": "Telah diverifikasi oleh petugas posko lapangan.",
        },
    )
    assert res_verify.status_code == 200
    assert res_verify.json()["data"]["status"] == "VERIFIED"
    assert "evidence_assessment" in res_verify.json()["data"]


def test_create_deforestation_reports_logging_and_encroachment():
    """Memverifikasi pelaporan kategori deforestasi baru (penebangan liar & perambahan hutan)."""
    now_utc = datetime.now(timezone.utc).isoformat()

    # 1. Laporan penebangan liar
    res_logging = client.post(
        "/api/v1/reports",
        json={
            "category": "penebangan_liar",
            "latitude": -0.52,
            "longitude": 117.14,
            "observed_at_utc": now_utc,
            "description": "Ditemukan tumpukan kayu gelondongan dan suara mesin chainsaw di dalam kawasan hutan.",
            "reporter_name": "Masyarakat Peduli Hutan",
        },
    )
    assert res_logging.status_code == 200
    data_logging = res_logging.json()
    assert data_logging["status"] == "success"
    assert data_logging["data"]["category"] == "penebangan_liar"
    assert "evidence_assessment" in data_logging["data"]

    # 2. Laporan perambahan kawasan hutan
    res_encroach = client.post(
        "/api/v1/reports",
        json={
            "category": "perambahan_hutan",
            "latitude": -1.82,
            "longitude": 114.12,
            "observed_at_utc": now_utc,
            "description": "Perambahan dan pembukaan kebun baru di dalam area batas hutan konservasi.",
            "reporter_name": "Ranger Swadaya",
        },
    )
    assert res_encroach.status_code == 200
    data_encroach = res_encroach.json()
    assert data_encroach["status"] == "success"
    assert data_encroach["data"]["category"] == "perambahan_hutan"

    # 3. Filter berdasarkan kategori deforestasi
    res_filter = client.get("/api/v1/reports?category=penebangan_liar")
    assert res_filter.status_code == 200
    recs = res_filter.json()["records"]
    assert len(recs) >= 1
    assert all(r["category"] == "penebangan_liar" for r in recs)


