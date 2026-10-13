from fastapi import APIRouter
from app.core.config import settings
from app.services.firms import _load_snapshot, _CACHE

router = APIRouter()


@router.get("/")
def get_system_status():
    """
    Menampilkan status kebaruan data (freshness), status koneksi NASA FIRMS API,
    dan metadata snapshot benchmark nasional JOINTS 2026.
    """
    # Cek sync time terakhir dari cache jika ada
    last_sync = None
    active_mode = "live" if bool(settings.FIRMS_MAP_KEY) else "snapshot"
    
    for entry in _CACHE.values():
        _, _, mode, sync_str = entry
        active_mode = mode
        last_sync = sync_str
        break

    if not last_sync:
        _, last_sync = _load_snapshot()

    return {
        "apiConfigured": bool(settings.FIRMS_MAP_KEY and settings.FIRMS_MAP_KEY != "YOUR_NASA_FIRMS_MAP_KEY_HERE"),
        "api_configured": bool(settings.FIRMS_MAP_KEY and settings.FIRMS_MAP_KEY != "YOUR_NASA_FIRMS_MAP_KEY_HERE"),
        "activeMode": active_mode,
        "active_mode": active_mode,
        "api_sensor_default": settings.DEFAULT_SENSOR,
        "lastSyncUtc": last_sync,
        "last_sync_utc": last_sync,
        "snapshot_status": "Tersedia",
        "snapshotPath": settings.SNAPSHOT_FALLBACK_PATH,
        "snapshot_path": settings.SNAPSHOT_FALLBACK_PATH,
        "disclaimer": (
            "Titik pada peta menunjukkan deteksi anomali termal satelit pada waktu tertentu. "
            "Deteksi dapat terlewat atau berasal dari anomali panas non-kebakaran. "
            "Verifikasi lapangan tetap diperlukan oleh pihak berwenang."
        ),
    }
