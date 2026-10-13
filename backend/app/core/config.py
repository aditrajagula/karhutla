from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pantau Hotspot & Gambut API"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://karhutla_user:karhutla_password@localhost:5432/karhutla_db"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # NASA FIRMS API
    FIRMS_MAP_KEY: str = ""
    FIRMS_BASE_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    DEFAULT_SENSOR: str = "VIIRS_NOAA20_NRT"

    # Snapshot Fallback
    SNAPSHOT_FALLBACK_PATH: str = "./data/snapshots/joints_benchmark_7days.csv"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="allow")


settings = Settings()
