# Pantau Hotspot, Jaga Hutan dan Gambut
**Proyek Hackathon JOINTS 2026 — Subtema: Sustainability**

Backend REST API (FastAPI) dan pipeline data processing anomali termal satelit (hotspot) NASA FIRMS VIIRS dengan validasi geospasial batas Indonesia dan manajemen snapshot mandiri tim.

---

## 1. Ringkasan & Ruang Lingkup

Sesuai ketentuan [PRD.md](file:///c:/Data-Karhutla/PRD.md):
* **Fokus Inti:** Mengambil data anomali termal aktif dari NASA FIRMS API (sensor VIIRS NOAA-20/21), memvalidasi koordinat dan waktu observasi UTC, membuang duplikasi, memotong titik hanya di dalam daratan Indonesia (*Point-in-Polygon*), serta menyajikan data melalui REST API berstandar GeoJSON (RFC 7946) lengkap dengan audit provenance.
* **Batas Integritas Ilmiah:** Titik deteksi satelit adalah anomali termal, **bukan bukti tunggal kebakaran pasti**. Sistem ini **tidak menggunakan model Machine Learning untuk prediksi kebakaran**, dan tidak mengklaim deteksi sebagai bukti deforestasi tanpa dataset perubahan tutupan lahan.

---

## 2. Penyesuaian Kondisi Dataset (Tanpa Dataset Panitia)

1. **Tidak Ada Snapshot Resmi Panitia:** Seluruh snapshot lokal yang disimpan oleh pipeline dilabeli sebagai `"TEAM_LOCAL_CAPTURE"` (hasil penarikan mandiri tim), bukan data benchmark resmi panitia.
2. **Penyimpanan Snapshot Otomatis:** Ketika panggilan ke NASA FIRMS API berhasil, data mentah otomatis disimpan di `data/snapshots/` dengan hash integritas **SHA-256** dan file `manifest_*.json`.
3. **Penanganan Saat Kunci Kosong / API Gagal:**
   * Jika snapshot tim lokal tersedia: Sistem beralih otomatis ke snapshot terbaru (`"FALLBACK_LOCAL_SNAPSHOT"`).
   * Jika belum ada snapshot: Sistem mengembalikan status jelas `"NO_DATA_AVAILABLE"` tanpa mengalami crash.
4. **Cakupan fitur laporan warga:** Dibatasi pada geometri administratif lima provinsi Kalimantan Indonesia (EPSG:4326); batas disimpan dalam GeoJSON dan diverifikasi dengan point-in-polygon.
5. **Layer Hutan dan Gambut:** Layer poligon gambut tersedia dari GeoJSON lokal dan kawasan hutan Kalimantan menggunakan `backend/app/forest_kalimantan_STRICT.geojson`. Metadata provenance, tahun, dan lisensi data gambut perlu dilengkapi dari sumber dataset.
6. **Penyaringan hotspot:** Titik hotspot pada endpoint peta dan overlay lokal dicocokkan dengan `data/boundaries/kalimantan_hotspot_mask.geojson`, bukan hanya bounding box atau batas administratif yang tergeneralisasi. Mask menghilangkan laut dan menggunakan zona pengecualian konservatif 10 km di dekat batas internasional Malaysia/Brunei. Zona ini dapat membuang deteksi sah di dekat perbatasan dan bukan batas hukum; sumber dan ketentuan GADM dijelaskan di [`data/boundaries/SOURCES.md`](data/boundaries/SOURCES.md). Setelah memperbarui mask atau kode filter, muat ulang backend agar endpoint menggunakannya.

---

## 3. Struktur Direktori Proyek

```text
c:/Data-Karhutla/
├── PRD.md                             # Dokumen kebutuhan resmi proyek
├── DESIGN.md                          # Dokumen arsitektur & desain
├── docker-compose.yml                 # Layanan PostGIS kontainer
├── pytest.ini                         # Konfigurasi pengujian pytest
├── requirements.txt                   # Pointer dependensi Python (-r backend/requirements.txt)
├── .env                               # Environment variable konfigurasi
├── .env.example                       # Template konfigurasi environment
├── .gitignore                         # Pengecualian secrets & build artifacts
├── README.md                          # Panduan instalasi dan pengoperasian
├── backend/                           # Service Backend FastAPI
│   ├── pytest.ini                     # Konfigurasi pytest backend
│   ├── requirements.txt               # Dependensi pustaka Python backend
│   ├── app/                           # Modul aplikasi FastAPI
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI App & Endpoints REST
│   │   ├── config.py                  # Konfigurasi path & environment
│   │   ├── models.py                  # Model Pydantic (HotspotRecord, Provenance)
│   │   ├── validation.py              # Validasi lat/lon, parse UTC, strict null handling
│   │   ├── cleaner.py                 # Deduplikasi & audit alasan penolakan
│   │   ├── spatial_filter.py          # Point-in-Polygon dengan Shapely STRtree
│   │   ├── snapshot_manager.py        # Simpan capture tim & verifikasi SHA-256
│   │   ├── firms_client.py            # Klien NASA FIRMS (chunking <= 5 hari)
│   │   └── pipeline.py                # Orkestrator end-to-end
│   └── tests/                         # Suite pengujian unit & integrasi
│       ├── __init__.py
│       ├── conftest.py                # Fixtures sintetis berlabel TEST ONLY
│       ├── test_api_endpoints.py      # Uji endpoint FastAPI (sukses, fallback, 422)
│       ├── test_audit_pipeline_independent.py # Audit pipeline independen
│       ├── test_cleaner.py            # Uji deduplikasi
│       ├── test_firms_integration.py  # Uji integrasi NASA FIRMS API
│       ├── test_frontend_integration_live.py # Uji integrasi frontend-backend
│       ├── test_hotspots.py           # Uji endpoint hotspot & format payload
│       ├── test_pipeline.py           # Uji alur pipeline utuh & fallback
│       ├── test_snapshot_manager.py   # Uji snapshot mandiri tim & SHA-256
│       ├── test_spatial_filter.py     # Uji titik dalam/luar Indonesia
│       └── test_validation.py         # Uji koordinat, timestamp, missing values
├── frontend/                          # Dashboard Antarmuka Web (React + Vite + TypeScript)
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/                           # Komponen peta, status bar, detail modal, services
└── data/                              # Dataset spasial dan penyimpanan snapshot
    ├── boundaries/
    │   ├── indonesia_provinces.geojson# Geometri administratif untuk batas wilayah
    │   └── SOURCES.md                 # Dokumentasi sumber & verifikasi batas
    ├── snapshots/
    │   └── README.md                  # Kebijakan snapshot mandiri & manifest SHA-256
    └── context_layers/
        └── README.md                  # Dokumentasi layer hutan & gambut opsional
```

---

## 4. Panduan Setup & Menjalankan Aplikasi (Windows PowerShell)

Pastikan berada pada direktori utama `C:\Data-Karhutla`:

### A. Siapkan Virtual Environment & Pasang Dependensi
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### B. Konfigurasi Environment (`.env`)
Salin template konfigurasi jika belum ada:
```powershell
Copy-Item .env.example .env
```
Pastikan `FIRMS_MAP_KEY` terisi di `.env`:
```env
FIRMS_MAP_KEY=d4208fc31485aff61dda184dc5f1a4c8
```

### C. Inisialisasi & Manajemen Database (SQLite)
Aplikasi menggunakan database SQLite tertanam (*embedded*) melalui SQLAlchemy ORM. **Tidak memerlukan instalasi server database eksternal** (PostgreSQL/MySQL terpisah).

1. **Lokasi File Database:**
   File database secara default disimpan di `data/citizen_reports.db`; lokasi dapat diubah melalui `REPORTS_DB_PATH`.
2. **Inisialisasi dan kompatibilitas otomatis:**
   Tabel laporan, akun, sesi, validasi warga, audit, dan pengaturan alert dibuat saat startup. Kolom baru untuk database laporan lama ditambahkan melalui migrasi SQLite saat backend mulai.
3. **Verifikasi Koneksi / Inisialisasi Manual:**
   ```powershell
   .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from app.reports_storage import reports_repo; print('Database terhubung di:', reports_repo.db_path)"
   ```
4. **Melihat / Monitoring Isi Database Laporan Warga:**
   ```powershell
   .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from app.reports_storage import reports_repo, CitizenReportModel; s = reports_repo.SessionLocal(); print(f'Total Laporan: {s.query(CitizenReportModel).count()}'); [print(f'- [{r.id}] {r.province} | {r.category} | {r.created_at_utc}') for r in s.query(CitizenReportModel).all()]; s.close()"
   ```
5. **Reset Database Bersih (Opsional):**
   Jika ingin mengosongkan data uji coba dan memulai database dari awal:
   ```powershell
   Remove-Item data\citizen_reports.db -ErrorAction SilentlyContinue
   ```
   Ini menghapus data laporan, akun, sesi, validasi, audit, dan pengaturan alert; jangan jalankan pada database yang berisi data yang perlu dipertahankan.

### D. Autentikasi dan Alur Laporan
* Registrasi warga dan login tersedia melalui `POST /api/v1/auth/register` dan `POST /api/v1/auth/login`. Gunakan token Bearer dari login untuk membuat laporan, melihat riwayat sendiri, memvalidasi laporan warga lain, dan mengakses pengaturan alert.
* Registrasi petugas hanya diaktifkan jika `PETUGAS_REGISTRATION_CODE` dikonfigurasi pada environment backend. Simpan kode tersebut hanya pada `.env` lokal/secret deployment; jangan commit atau mengirimkannya ke frontend.
* Petugas dapat menggunakan endpoint status laporan dan audit trail; lokasi presisi pelapor hanya tersedia bagi petugas dan aksesnya dicatat. Respons publik menghilangkan identitas/kontak dan membulatkan koordinat.
* `GET /api/v1/reports/nearby` memakai koordinat saat diminta untuk pencarian radius 1, 3, 5, atau 10 km. Pengaturan alert hanya menyimpan status dan radius, bukan koordinat GPS. Alert laporan warga bukan peringatan darurat atau konfirmasi kebakaran.

### E. Jalankan Server FastAPI Backend
```powershell
.\.venv\Scripts\uvicorn backend.app.main:app --reload --port 8000
```
Server aktif di:
* **Base URL:** `http://localhost:8000`
* **Dokumentasi Interaktif (Swagger UI):** `http://localhost:8000/docs`
* **Health Check:** `http://localhost:8000/health`

### F. Jalankan Dashboard Frontend
Pada terminal terpisah:
```powershell
cd frontend
npm install
npm run dev
```
Dashboard aktif di: `http://localhost:5173`

---

## 5. Kontrak Endpoint REST API

### 1. `GET /api/v1/hotspots`
Mengambil data hotspot yang telah divalidasi dan difilter dalam format GeoJSON FeatureCollection standar RFC 7946.

**Query Parameters:**
* `days` *(integer, default 7, rentang 1-10)*: Rentang hari observasi.
* `source` *(string, opsional)*: Sensor satelit (misal `VIIRS_NOAA20_NRT` atau `VIIRS_NOAA21_NRT`).
* `confidence` *(string, opsional)*: Tingkat keyakinan (`low`, `nominal`, `high`).
* `min_frp` *(float, opsional, $\ge 0.0$)*: Ambang batas minimum Fire Radiative Power (MW).
* `province` *(string, opsional)*: Nama provinsi Kalimantan.
* `force_snapshot` *(boolean, default false)*: Memaksa membaca snapshot lokal tim tanpa menghubungi API.

Endpoint hotspot dan overlay hotspot lokal selalu memeriksa titik dengan geometri batas lima provinsi Kalimantan sebelum mengembalikan hasil, terlepas dari parameter `region` atau metadata provinsi dari FIRMS. Jika API key tidak tersedia, mode snapshot diminta, atau panggilan live gagal, backend menggunakan `backend/app/firms_kalimantan_STRICT.csv` sebelum snapshot umum lainnya. File tersebut merupakan dataset statis, bukan data live; waktu pengambilannya tidak tersedia.

> [!NOTE]
> **Status Contoh:** Payload JSON di bawah ini adalah **CONTOH ILUSTRATIF SKEMA RESPON** untuk panduan kontrak antarmuka API dan integrasi frontend, bukan rekaman kebakaran nyata dari lapangan.

**Contoh Response (Ilustratif):**
```json
{
  "type": "FeatureCollection",
  "provenance": {
    "data_source": "LOCAL_TEAM_SNAPSHOT",
    "sensor_product": "VIIRS_NOAA20_NRT",
    "is_snapshot": true,
    "snapshot_type": "TEAM_LOCAL_CAPTURE",
    "fetched_at_utc": "2026-10-13T09:50:00Z",
    "processed_at_utc": "2026-10-13T10:00:00Z",
    "observation_date_range": { "min": "2026-10-12", "max": "2026-10-13" },
    "audit_stats": {
      "total_initial_records": 100,
      "total_valid_records": 85,
      "total_rejected_records": 15,
      "reasons": {
        "outside_indonesia_boundary": 12,
        "duplicate_record": 2,
        "invalid_coordinates": 1
      }
    },
    "status_message": "Menampilkan snapshot lokal tim yang diambil pada 2026-10-13T09:50:00Z."
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [101.44, 0.53]
      },
      "properties": {
        "observation_time_utc": "2026-10-13T04:00:00Z",
        "acq_date": "2026-10-13",
        "acq_time": "0400",
        "satellite": "20",
        "instrument": "VIIRS",
        "confidence": "nominal",
        "version": "2.0NRT",
        "bright_ti4": 325.4,
        "bright_ti5": 295.1,
        "frp": 15.5,
        "daynight": "D",
        "province": "Riau"
      }
    }
  ]
}
```

### 2. `GET /api/v1/provenance`
Melaporkan metadata asal-usul data dan status mode data secara transparan.

**Contoh Response (Ilustratif):**
```json
{
  "data_source": "LOCAL_TEAM_SNAPSHOT",
  "status": "FALLBACK_LOCAL_SNAPSHOT",
  "is_snapshot": true,
  "snapshot_type": "TEAM_LOCAL_CAPTURE",
  "fetched_at_utc": "2026-10-13T09:50:00Z",
  "processed_at_utc": "2026-10-13T10:00:00Z",
  "observation_date_range": { "min": "2026-10-12", "max": "2026-10-13" },
  "audit_stats": { ... },
  "status_message": "FIRMS_MAP_KEY belum diatur di .env. Menggunakan fallback snapshot lokal tim."
}
```

### 3. `GET /api/v1/context-layers`
Melaporkan ketersediaan layer konteks kawasan hutan dan gambut tanpa mengarang data.

**Contoh Response (Aktual dari Server):**
```json
{
  "forest_layer": {
    "available": false,
    "source": "Kementerian Lingkungan Hidup dan Kehutanan (KLHK)",
    "status_message": "Dataset resmi kawasan hutan belum tersedia dari panitia/instansi.",
    "feature_count": null
  },
  "peatland_layer": {
    "available": true,
    "source": "GeoJSON lokal peat_kalimantan_big_official.geojson",
    "status_message": "Layer poligon gambut Kalimantan tersedia untuk ditampilkan. Tahun, lisensi, dan provenance dataset belum tercatat pada manifest.",
    "feature_count": null
  },
  "boundary_layer": {
    "available": true,
    "source": "Batas 5 provinsi Kalimantan (WGS84 EPSG:4326)",
    "status_message": "Geometri 5 provinsi Kalimantan aktif untuk filter spasial.",
    "feature_count": 5
  }
}
```

### 4. Layer GeoJSON tematik untuk peta Kalimantan
Frontend memuat layer ini hanya saat pengguna menyalakannya. Backend mencari aset lokal berikut di `backend/app/`:

* `GET /api/v1/map-data/peatland` — poligon gambut; endpoint mengembalikan geometri yang disederhanakan hanya untuk tampilan peta (toleransi 0.0001 derajat, sekitar 11 m). File sumber tidak diubah dan geometri hasil tampilan tidak digunakan untuk klasifikasi hotspot.
* `GET /api/v1/map-data/forest` — poligon kawasan hutan Kalimantan dari `backend/app/forest_kalimantan_STRICT.geojson`.
* `GET /api/v1/map-data/classified-hotspots` — snapshot titik FIRMS beserta `in_peat`, `peat_class`, dan `fire_risk_priority`.
* `GET /api/v1/map-data/segmented-hotspots` — snapshot titik FIRMS dari `final_hotspots_segmentation.geojson` dengan atribut `in_peat`, `in_forest`, dan `is_focus_hotspot`.
* `GET /api/v1/map-data/firms-manifest` — sumber, tanggal pengambilan, bbox, dan jumlah catatan snapshot.

Kontrol peta menyediakan overlay poligon gambut dan kawasan hutan, snapshot hotspot terklasifikasi, serta hotspot segmentasi. Snapshot ini terpisah dari layer hotspot near-real-time API. Pastikan file GeoJSON sumber yang dipakai endpoint tersedia di `backend/app/` pada deployment. Hotspot adalah indikasi anomali termal, bukan bukti kebakaran atau batas area terbakar; metadata asal, tahun, dan lisensi GeoJSON gambut masih perlu dicatat.

---

## 6. Menjalankan Pengujian (Testing)

### A. Eksekusi Seluruh Suite Backend
Jalankan seluruh test suite otomatis:
```powershell
.\.venv\Scripts\pytest -v
```
Atau menggunakan runner script:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1
```

### B. Eksekusi Berdasarkan Modul
```powershell
# 1. Modul Inti FIRMS & Geospasial 34 Provinsi (50 tests)
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1 core

# 2. Modul Raster Hansen GFC & Analisis Kalimantan (43 tests)
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1 raster

# 3. Modul Laporan Bukti Warga & Proteksi Privasi (20 tests)
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1 citizen
```

### C. Pembuatan Tile Lokal untuk Demo (<5 ms Latency)
Untuk demonstrasi offline tanpa ketergantungan internet dan tanpa latensi remote 9 detik:
```powershell
.\.venv\Scripts\python.exe scripts/generate_kalimantan_demo_tiles.py
```

### D. Hasil Pengujian Aktual
* Backend: **117 passed, 1 skipped** pada eksekusi terakhir seluruh suite (`pytest -q backend/tests`). Satu warning deprecation berasal dari integrasi Starlette TestClient/httpx.
* Frontend: `npm run build` berhasil. `npm run lint` berhasil dengan dua warning `react(set-state-in-effect)` yang sudah ada di `ReportFormModal.tsx`.
* Cakupan test meliputi pipeline FIRMS, validasi geospasial, layer Hansen, autentikasi/sesi, alur laporan warga/petugas, privasi, alert, dan endpoint API.
