"""
Konfigurasi Environment dan Konstanta Sistem.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Path direktori proyek (C:\Data-Karhutla)
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Coba cari data directory di root atau backend
if (PROJECT_ROOT / "data").exists():
    BASE_DIR = PROJECT_ROOT
else:
    BASE_DIR = BACKEND_DIR

# Muat file .env dari root atau backend
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    load_dotenv(override=True)

# NASA FIRMS API Configurations
# PERINGATAN: Kunci ini hanya ada di environment backend dan tidak boleh dibagikan ke klien.
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "").strip()
FIRMS_DEFAULT_SOURCE = os.getenv("FIRMS_DEFAULT_SOURCE", "VIIRS_NOAA20_NRT")
FIRMS_BACKUP_SOURCE = os.getenv("FIRMS_BACKUP_SOURCE", "VIIRS_NOAA21_NRT")
FIRMS_AREA_BBOX = os.getenv("FIRMS_AREA_BBOX", "95.0,-11.0,141.5,6.0")
FIRMS_REQUEST_TIMEOUT_SECONDS = int(os.getenv("FIRMS_REQUEST_TIMEOUT_SECONDS", "20"))

# Path direktori dan data
BOUNDARIES_PATH = BASE_DIR / os.getenv("BOUNDARIES_PATH", "data/boundaries/indonesia_provinces.geojson")
SNAPSHOTS_DIR = BASE_DIR / os.getenv("SNAPSHOTS_DIR", "data/snapshots")

# Mode eksekusi
FORCE_SNAPSHOT_MODE = os.getenv("FORCE_SNAPSHOT_MODE", "false").lower() in ("true", "1", "yes")

# Pastikan direktori snapshot ada
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
