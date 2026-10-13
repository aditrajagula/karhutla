# Pantau Hotspot & Gambut (Karhutla)

Sistem Pemantauan Titik Panas dan Konteks Lahan Gambut untuk Hackathon JOINTS 2026 (Subtema: Sustainability).

## Tech Stack

1. **Frontend:** React 19 + Vite (TypeScript)
   - Peta interaktif Indonesia (koordinat akurat, basemap fleksibel).
   - Filter waktu observasi dan filter wilayah administratif.
   - Daftar deteksi anomali termal dan modal inspeksi detail titik.
   - Indikator status kebaruan data (Live API vs Snapshot Benchmark).
   - Mematuhi panduan desain `DESIGN.md` (dial `ENERGY 1 / RHYTHM 1 / MOTION 1`).

2. **Backend:** FastAPI (Python 3.12)
   - Proxy aman ke NASA FIRMS VIIRS API (menyimpan `MAP_KEY` di server, tidak terekspos ke browser).
   - Validasi data, normalisasi zona waktu, dan filtering geospasial terhadap batas resmi Indonesia.
   - Layanan caching dan fallback otomatis ke snapshot lokal 7 hari jika API bermasalah.

3. **Database Spasial:** PostgreSQL 16 + PostGIS 3
   - Penyimpanan cache deteksi anomali termal satelit.
   - Pencarian spasial (Spatial Indexing) dan filter titik dalam radius/poligon wilayah.
   - Manajemen layer spasial (kawasan hutan dan lahan gambut).

---

## Struktur Proyek

```
karhutla/
├── DESIGN.md                 # Spesifikasi visual, sistem warna, dan aturan antislop
├── README.md                 # Dokumentasi proyek dan panduan setup
├── docker-compose.yml        # PostgreSQL 16 + PostGIS 3
├── .env.example              # Template variabel lingkungan
├── .gitignore                # Aturan ignore git
├── backend/                  # Layanan backend FastAPI
│   ├── app/
│   │   ├── api/              # Endpoint rute (/hotspots, /boundaries, /status)
│   │   ├── core/             # Konfigurasi Pydantic Settings
│   │   ├── db/               # Inisialisasi engine & session database
│   │   ├── models/           # Model data PostGIS (GeoAlchemy2)
│   │   ├── schemas/          # Schema validasi Pydantic
│   │   └── services/         # Client FIRMS API & Spatial Query Service
│   ├── tests/                # Unit test backend
│   └── requirements.txt      # Dependensi Python
├── frontend/                 # Aplikasi antarmuka React + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/       # Loading, EmptyState, ErrorBanner
│   │   │   ├── detection/    # Daftar titik & modal detail inspeksi
│   │   │   ├── filters/      # Panel filter waktu dan wilayah
│   │   │   ├── map/          # Kanvas peta interaktif
│   │   │   └── status/       # Bilah status kebaruan data
│   │   ├── services/         # Client komunikasi ke backend
│   │   └── types/            # Tipe data TypeScript
│   └── package.json
└── data/                     # Data spasial & snapshot fallback
    ├── boundaries/           # Berkas batas spasial resmi (GeoJSON)
    └── snapshots/            # Snapshot benchmark 7 hari dari panitia
```

---

## Panduan Memulai Cepat (Quickstart Setup)

### 1. Menjalankan Database PostGIS
Pastikan Docker Desktop aktif di sistem Anda:
```bash
docker compose up -d db
```

### 2. Menjalankan Backend (FastAPI)
Salin konfigurasi lingkungan:
```bash
copy .env.example backend\.env
```
Isi `FIRMS_MAP_KEY` dengan kunci API gratis dari NASA FIRMS.

Jalankan backend menggunakan Python:
```bash
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Dokumentasi interaktif Swagger dapat diakses di `http://localhost:8000/api/v1/docs`.

### 3. Menjalankan Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Buka browser di `http://localhost:5173`.