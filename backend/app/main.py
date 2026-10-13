"""
FastAPI Backend Application.
Menyediakan REST API untuk data hotspot, metadata provenance, dan status layer konteks.
"""

from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from .config import (
    BOUNDARIES_PATH,
    FIRMS_DEFAULT_SOURCE,
    FIRMS_MAP_KEY,
    SNAPSHOTS_DIR,
)
from .pipeline import HotspotPipeline
from .snapshot_manager import find_latest_valid_snapshot

app = FastAPI(
    title="Pantau Hotspot, Jaga Hutan dan Gambut API",
    description=(
        "Backend REST API untuk pemantauan anomali termal satelit (hotspot) NASA FIRMS "
        "dengan validasi batas daratan Indonesia dan fallback snapshot mandiri tim."
    ),
    version="1.0.0"
)

# Aktifkan CORS agar frontend (Vite dev server & browser klien) dapat mengakses API secara aman
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inisialisasi pipeline singleton (menggunakan konfigurasi backend terkini)
pipeline_instance = HotspotPipeline(
    boundaries_path=BOUNDARIES_PATH,
    snapshots_dir=SNAPSHOTS_DIR,
    map_key=FIRMS_MAP_KEY,
    default_source=FIRMS_DEFAULT_SOURCE
)


# ==============================================================================
# Model Respons Skema
# ==============================================================================

class ContextLayerItem(BaseModel):
    available: bool
    source: str
    status_message: str
    feature_count: Optional[int] = None


class ContextLayersResponse(BaseModel):
    forest_layer: ContextLayerItem
    peatland_layer: ContextLayerItem
    boundary_layer: ContextLayerItem


class ProvenanceStatusResponse(BaseModel):
    data_source: str
    status: str
    is_snapshot: bool
    snapshot_type: Optional[str] = None
    fetched_at_utc: Optional[str] = None
    processed_at_utc: str
    observation_date_range: Dict[str, Optional[str]]
    audit_stats: Dict[str, Any]
    status_message: str


# ==============================================================================
# Endpoints
# ==============================================================================

@app.get("/api/v1/hotspots", summary="Mengambil data hotspot hasil pipeline terfilter")
def get_hotspots(
    days: Optional[int] = Query(None, ge=1, le=10, description="Rentang hari observasi (1 s.d. 10 hari)"),
    day_range: Optional[int] = Query(None, ge=1, le=10, description="Alias untuk rentang hari observasi"),
    source: Optional[str] = Query(None, description="Sensor satelit (misal VIIRS_NOAA20_NRT atau VIIRS_NOAA21_NRT)"),
    confidence: Optional[str] = Query(None, description="Filter tingkat confidence: low, nominal, high (atau l, n, h)"),
    min_frp: Optional[float] = Query(None, ge=0.0, description="Ambang batas minimum Fire Radiative Power (MW)"),
    province: Optional[str] = Query(None, description="Filter nama provinsi daratan Indonesia (case-insensitive)"),
    force_snapshot: bool = Query(False, description="Paksa membaca snapshot tim lokal tanpa menghubungi live API"),
    mode: Optional[str] = Query(None, description="Mode sumber data ('live' atau 'snapshot')"),
    start_date: Optional[str] = Query(None, description="Filter tanggal awal observasi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter tanggal akhir observasi (YYYY-MM-DD)"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Maksimum jumlah titik yang dikembalikan")
) -> Dict[str, Any]:
    """
    Mengambil data hotspot terverifikasi dalam format GeoJSON FeatureCollection (RFC 7946).
    Data telah divalidasi koordinatnya, dipotong sesuai poligon Indonesia, dan dideduplikasi.
    """
    effective_days = days or day_range or 7
    effective_force_snapshot = force_snapshot or (mode == "snapshot")

    try:
        result = pipeline_instance.run(
            total_days=effective_days,
            source=source,
            force_snapshot=effective_force_snapshot
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan saat mengeksekusi pipeline pengolahan data: {str(exc)}"
        ) from exc

    features = result.get("features", [])

    # Filter tanggal manual jika diberikan
    if start_date:
        s_date = start_date.strip()
        features = [
            f for f in features
            if f["properties"].get("acq_date") and f["properties"]["acq_date"] >= s_date
        ]

    if end_date:
        e_date = end_date.strip()
        features = [
            f for f in features
            if f["properties"].get("acq_date") and f["properties"]["acq_date"] <= e_date
        ]

    # Filter tambahan berdasarkan parameter kueri
    if confidence:
        c_filter = confidence.strip().lower()
        # Mendukung baik 'l'/'low', 'n'/'nominal', 'h'/'high'
        c_map = {"l": "low", "n": "nominal", "h": "high"}
        normalized_target = c_map.get(c_filter, c_filter)

        def matches_confidence(feat: Dict[str, Any]) -> bool:
            c_val = str(feat["properties"].get("confidence") or "").strip().lower()
            return c_map.get(c_val, c_val) == normalized_target

        features = [f for f in features if matches_confidence(f)]

    if min_frp is not None:
        features = [
            f for f in features
            if f["properties"].get("frp") is not None and f["properties"]["frp"] >= min_frp
        ]

    if province:
        prov_target = province.strip().lower()
        features = [
            f for f in features
            if f["properties"].get("province") and prov_target in f["properties"]["province"].lower()
        ]

    # Susun kembali GeoJSON hasil filter dan payload list records
    is_snap = result.get("provenance", {}).get("is_snapshot", False) or effective_force_snapshot
    records_list = [
        {
            "id": f.get("id") or f"{f['properties'].get('satellite')}_{f['properties'].get('acq_date')}_{f['properties'].get('acq_time')}_{f['geometry']['coordinates'][1]}_{f['geometry']['coordinates'][0]}",
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "confidence": f["properties"].get("confidence"),
            "satellite": f["properties"].get("satellite"),
            "acq_date": f["properties"].get("acq_date"),
            "acq_time": f["properties"].get("acq_time"),
            "frp": f["properties"].get("frp"),
            "province": f["properties"].get("province")
        }
        for f in features
    ]
    if limit is not None:
        records_list = records_list[:limit]
        features = features[:limit]

    return {
        "type": "FeatureCollection",
        "mode": "snapshot" if is_snap else "live",
        "count": len(features),
        "records": records_list,
        "provenance": result.get("provenance", {}),
        "features": features
    }


@app.get(
    "/api/v1/provenance",
    response_model=ProvenanceStatusResponse,
    summary="Melihat metadata asal data, waktu, dan status mode"
)
def get_provenance() -> ProvenanceStatusResponse:
    """
    Melaporkan status dataset terkini:
    - LIVE_API: Pengambilan langsung dari NASA FIRMS API.
    - FALLBACK_LOCAL_SNAPSHOT: Menggunakan snapshot lokal tim akibat API offline / tanpa MAP_KEY.
    - NO_DATA_AVAILABLE: Belum ada koneksi API dan belum ada snapshot tim tersimpan.
    """
    if pipeline_instance.last_provenance is not None:
        prov = pipeline_instance.last_provenance
    else:
        # Jalankan pipeline 2 hari untuk inisialisasi awal
        result = pipeline_instance.run(total_days=2)
        prov = result.get("provenance", {})

    data_src = prov.get("data_source", "NONE")
    is_snap = prov.get("is_snapshot", False)
    status_label = prov.get("status", "NO_DATA_AVAILABLE")

    return ProvenanceStatusResponse(
        data_source=data_src,
        status=status_label,
        is_snapshot=is_snap,
        snapshot_type=prov.get("snapshot_type"),
        fetched_at_utc=prov.get("fetched_at_utc"),
        processed_at_utc=prov.get("processed_at_utc", ""),
        observation_date_range=prov.get("observation_date_range", {"min": None, "max": None}),
        audit_stats=prov.get("audit_stats", {}),
        status_message=prov.get("status_message", "")
    )


@app.get(
    "/api/v1/context-layers",
    response_model=ContextLayersResponse,
    summary="Melaporkan status ketersediaan layer konteks hutan dan gambut"
)
def get_context_layers() -> ContextLayersResponse:
    """
    Melaporkan ketersediaan layer kontekstual secara transparan.
    Tidak mengarang data kawasan hutan atau gambut jika belum tersedia dari sumber resmi.
    """
    return ContextLayersResponse(
        forest_layer=ContextLayerItem(
            available=False,
            source="Kementerian Lingkungan Hidup dan Kehutanan (KLHK)",
            status_message="Dataset resmi kawasan hutan belum tersedia dari panitia/instansi."
        ),
        peatland_layer=ContextLayerItem(
            available=False,
            source="Badan Restorasi Gambut dan Mangrove (BRGM)",
            status_message="Dataset resmi kesatuan hidrologis gambut belum tersedia dari panitia/instansi."
        ),
        boundary_layer=ContextLayerItem(
            available=True,
            source="Batas Daratan 34 Provinsi Indonesia (WGS84 EPSG:4326)",
            status_message="Geometri batas wilayah daratan Indonesia aktif untuk filter spasial.",
            feature_count=len(pipeline_instance.spatial_filter.geometries)
        )
    )


@app.get("/", summary="Root endpoint - redirect ke dokumentasi Swagger API", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/health", summary="Health check endpoint")
def health_check():
    return {"status": "ok", "service": "Pantau Hotspot, Jaga Hutan dan Gambut API"}


@app.get("/api/v1/status", summary="Alias untuk /api/v1/provenance", include_in_schema=False)
def get_status_alias():
    prov = get_provenance()
    is_live = prov.status == "LIVE_API"
    res = prov.model_dump()
    res.update({
        "apiConfigured": is_live,
        "api_configured": is_live,
        "activeMode": "live" if is_live else "snapshot",
        "active_mode": "live" if is_live else "snapshot",
        "lastSyncUtc": prov.fetched_at_utc,
        "disclaimer": prov.status_message,
        "snapshotPath": prov.snapshot_type or "",
    })
    return res


@app.get("/api/v1/boundaries", summary="Alias untuk /api/v1/context-layers", include_in_schema=False)
def get_boundaries_alias():
    return get_context_layers()

