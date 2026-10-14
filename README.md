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
4. **Batas Geografis Terverifikasi:** Menggunakan geometri administratif 34 provinsi Indonesia (EPSG:4326) yang divalidasi topologinya dengan Shapely 2.x STRtree. Dokumentasi sumber dicatat di [data/boundaries/SOURCES.md](file:///c:/Data-Karhutla/data/boundaries/SOURCES.md).
5. **Layer Hutan dan Gambut (Opsional):** Dilaporkan transparan sebagai *belum tersedia* melalui endpoint `GET /api/v1/context-layers`.

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
    │   ├── indonesia_provinces.geojson# Batas administratif 34 provinsi daratan Indonesia
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
   File database disimpan di `data/citizen_reports.db` (dikonfigurasi melalui `REPORTS_DB_PATH` di `.env`).
2. **Inisialisasi Otomatis:**
   Skema tabel `citizen_reports` otomatis dibuat saat backend pertama kali dijalankan.
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

### D. Jalankan Server FastAPI Backend
```powershell
.\.venv\Scripts\uvicorn backend.app.main:app --reload --port 8000
```
Server aktif di:
* **Base URL:** `http://localhost:8000`
* **Dokumentasi Interaktif (Swagger UI):** `http://localhost:8000/docs`
* **Health Check:** `http://localhost:8000/health`

### E. Jalankan Dashboard Frontend
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
* `province` *(string, opsional)*: Nama provinsi daratan Indonesia (misal `Riau`, `Kalimantan Barat`).
* `force_snapshot` *(boolean, default false)*: Memaksa membaca snapshot lokal tim tanpa menghubungi API.

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
    "available": false,
    "source": "Badan Restorasi Gambut dan Mangrove (BRGM)",
    "status_message": "Dataset resmi kesatuan hidrologis gambut belum tersedia dari panitia/instansi.",
    "feature_count": null
  },
  "boundary_layer": {
    "available": true,
    "source": "Batas Daratan 34 Provinsi Indonesia (WGS84 EPSG:4326)",
    "status_message": "Geometri batas wilayah daratan Indonesia aktif untuk filter spasial.",
    "feature_count": 34
  }
}
```

---

## 6. Menjalankan Pengujian (Testing)

### A. Eksekusi Seluruh Suite Backend (113 Tests)
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
* **113 tests passed (100% lulus)** mencakup 15 file pengujian:
  1. **Modul Inti FIRMS & Geospasial Nasional (50 tests):** Unit validator (`test_validation.py`), deduplikasi 5 desimal (`test_cleaner.py`), STRtree Point-in-Polygon 34 provinsi daratan Indonesia (`test_spatial_filter.py`), snapshot integritas SHA-256 (`test_snapshot_manager.py`), integrasi NASA FIRMS API live (`test_firms_integration.py`), orkestrasi pipeline (`test_pipeline.py`), kontrak endpoint REST API & health (`test_api_endpoints.py`, `test_hotspots.py`), audit pipeline independen (`test_audit_pipeline_independent.py`), dan integrasi frontend live (`test_frontend_integration_live.py`).
  2. **Modul Raster Hansen GFC & Kalimantan (43 tests):** Batas spasial 5 provinsi Kalimantan & eksklusi wilayah luar (`test_kalimantan_spatial.py`), pembacaan piksel GeoTIFF & isolasi status data demo (`test_hansen_raster_integration.py`), kalkulasi tutupan hutan (`test_forest_change.py`), verifikasi analitik transformasi koordinat GeoTIFF EPSG:4326, audit kewajaran baseline non-hutan perkotaan Palangka Raya, pembacaan paralel multi-layer (*ThreadPoolExecutor*), batas waktu tunggu ketat (*strict timeout* 3.0s), dan *dual-tier caching* memori grid 30m.
  3. **Modul Laporan Bukti Warga & Privasi (20 tests):** Siklus hidup laporan warga, anti-duplikasi, & status verifikasi operator (`test_citizen_reports.py`), serta proteksi kontak pelapor, penyamaran koordinat publik (*privacy obfuscation*), dan penilaian bukti (*evidence assessment*) terpisah (`test_citizen_evidence_and_privacy.py`).
