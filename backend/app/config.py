"""
Konfigurasi Environment dan Konstanta Sistem.
"""

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass

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

# Direktori Data, Database, dan Uploads
BOUNDARIES_PATH = BASE_DIR / os.getenv("BOUNDARIES_PATH", "data/boundaries/indonesia_provinces.geojson")
SNAPSHOTS_DIR = BASE_DIR / os.getenv("SNAPSHOTS_DIR", "data/snapshots")
REPORTS_DB_PATH = BASE_DIR / os.getenv("REPORTS_DB_PATH", "data/citizen_reports.db")
UPLOADS_DIR = BASE_DIR / os.getenv("UPLOADS_DIR", "data/uploads/reports")

# Mode eksekusi
FORCE_SNAPSHOT_MODE = os.getenv("FORCE_SNAPSHOT_MODE", "false").lower() in ("true", "1", "yes")

# Hansen Global Forest Change Configurations
HANSEN_DATASET_VERSION = os.getenv("HANSEN_DATASET_VERSION", "GFC-2025-v1.13")
HANSEN_TILES_DIR = BASE_DIR / os.getenv("HANSEN_TILES_DIR", "data/raster/hansen")
HANSEN_OFFICIAL_DIR = BASE_DIR / os.getenv("HANSEN_OFFICIAL_DIR", "data/raster/hansen/official")
HANSEN_USE_OFFICIAL = os.getenv("HANSEN_USE_OFFICIAL", "false").lower() in ("true", "1", "yes")
HANSEN_ENABLE_REMOTE_ACCESS = os.getenv("HANSEN_ENABLE_REMOTE_ACCESS", "false").lower() in ("true", "1", "yes")
HANSEN_REMOTE_TIMEOUT_SECONDS = float(os.getenv("HANSEN_REMOTE_TIMEOUT_SECONDS", "3.0"))
HANSEN_MAX_PARALLEL_WORKERS = int(os.getenv("HANSEN_MAX_PARALLEL_WORKERS", "3"))
HANSEN_CACHE_MAX_ENTRIES = int(os.getenv("HANSEN_CACHE_MAX_ENTRIES", "10000"))
HANSEN_REMOTE_BASE_URL = os.getenv(
    "HANSEN_REMOTE_BASE_URL",
    "https://storage.googleapis.com/earthenginepartners-hansen/{version}/"
)

# Pastikan direktori penting ada
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
HANSEN_TILES_DIR.mkdir(parents=True, exist_ok=True)
HANSEN_OFFICIAL_DIR.mkdir(parents=True, exist_ok=True)

# Open-Meteo Weather API Configurations
WEATHER_API_BASE_URL = os.getenv(
    "WEATHER_API_BASE_URL",
    "https://api.open-meteo.com/v1/forecast"
)
WEATHER_REQUEST_TIMEOUT_SECONDS = float(os.getenv("WEATHER_REQUEST_TIMEOUT_SECONDS", "5.0"))

# GLAD Forest Extent 2020 Configurations
GLAD_FOREST_DIR = BASE_DIR / os.getenv("GLAD_FOREST_DIR", "data/raster/forest")
GLAD_FOREST_DIR.mkdir(parents=True, exist_ok=True)

# Predictive Fire Risk ML Model Configurations
PREDICTIVE_MODEL_PATH = BASE_DIR / os.getenv("PREDICTIVE_MODEL_PATH", "data/model_regresi_logistik.joblib")
PREDICTIVE_SCALER_PATH = BASE_DIR / os.getenv("PREDICTIVE_SCALER_PATH", "data/scaler_regresi_logistik.joblib")
