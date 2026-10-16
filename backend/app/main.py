"""
FastAPI Backend Application.
Menyediakan REST API untuk data hotspot, metadata provenance, dan status layer konteks.
"""

import asyncio
import base64
from contextlib import asynccontextmanager
import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import (
    BOUNDARIES_PATH,
    FIRMS_DEFAULT_SOURCE,
    FIRMS_MAP_KEY,
    SNAPSHOTS_DIR,
    UPLOADS_DIR,
)
from .pipeline import HotspotPipeline
from .snapshot_manager import find_latest_valid_snapshot
from .reports_storage import reports_repo, ReportCategory, ReportStatus
from .forest_change_service import (
    get_forest_loss_summary,
    evaluate_forest_change_point,
    KALIMANTAN_PROVINCES,
    HANSEN_PROVINCIAL_BASELINE_HA,
    HANSEN_ANNUAL_LOSS_HA,
)
from .evidence_service import assess_report_evidence, parse_iso_utc

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = int(os.getenv("FIRMS_REFRESH_INTERVAL_SECONDS", "1800"))


async def _firms_auto_refresh_loop() -> None:
    # ponytail: single-process asyncio loop, pakai OS cron jika multi-worker
    while True:
        try:
            await asyncio.to_thread(pipeline_instance.run, total_days=5, force_snapshot=False)
        except Exception as exc:
            logger.warning("Auto-refresh FIRMS gagal: %s", exc)
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_firms_auto_refresh_loop()) if REFRESH_INTERVAL_SECONDS > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="Pantau Hotspot, Jaga Hutan dan Gambut API",
    description=(
        "Backend REST API untuk pemantauan anomali termal satelit (hotspot) NASA FIRMS "
        "dengan validasi batas daratan Indonesia dan analisis tutupan pohon Kalimantan."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Pastikan folder upload ada dan mount StaticFiles untuk foto laporan masyarakat
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/reports", StaticFiles(directory=str(UPLOADS_DIR)), name="reports_uploads")

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

kalimantan_geojson_cache: Optional[Dict[str, Any]] = None


def get_kalimantan_geojson() -> Dict[str, Any]:
    global kalimantan_geojson_cache
    if kalimantan_geojson_cache is not None:
        return kalimantan_geojson_cache

    features = []
    if BOUNDARIES_PATH.exists():
        with open(BOUNDARIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            name = p.get("state") or p.get("NAME_1") or p.get("name")
            if name in KALIMANTAN_PROVINCES:
                feat_copy = dict(feat)
                annual = HANSEN_ANNUAL_LOSS_HA.get(name, {})
                cum_loss = sum(annual.values())
                baseline = HANSEN_PROVINCIAL_BASELINE_HA.get(name, 0.0)
                feat_copy["properties"] = {
                    "province": name,
                    "name": name,
                    "baseline_treecover_2000_ha": baseline,
                    "cumulative_loss_2001_2025_ha": cum_loss,
                    "percentage_lost": round((cum_loss / baseline) * 100, 2) if baseline > 0 else 0.0,
                    "source": "Hansen GFC 2025 v1.13",
                    "data_status": "demonstration",
                    "data_verified": False,
                    "verification_notes": (
                        "Statistik tutupan pohon disajikan sebagai data demonstrasi sementara "
                        "dan belum diverifikasi melalui raster tingkat piksel."
                    )
                }
                features.append(feat_copy)
    kalimantan_geojson_cache = {
        "type": "FeatureCollection",
        "name": "Batas 5 Provinsi Kalimantan Bagian Indonesia",
        "features": features
    }
    return kalimantan_geojson_cache



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
    region: Optional[str] = Query(None, description="Filter cakupan wilayah: 'kalimantan' untuk membatasi 5 provinsi Kalimantan"),
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

    if region and region.strip().lower() == "kalimantan":
        kalimantan_names = {p.lower() for p in KALIMANTAN_PROVINCES}
        features = [
            f for f in features
            if f["properties"].get("province") and f["properties"]["province"].strip().lower() in kalimantan_names
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


# ==============================================================================
# Model Skema Pelaporan Masyarakat (Citizen Reports)
# ==============================================================================

class CitizenReportCreate(BaseModel):
    category: str = Field(..., description="Kategori: kebakaran, pembukaan_lahan, perubahan_tutupan")
    latitude: float = Field(..., ge=-11.0, le=6.0, description="Latitude daratan Indonesia (-11.0 s.d. 6.0)")
    longitude: float = Field(..., ge=95.0, le=141.5, description="Longitude daratan Indonesia (95.0 s.d. 141.5)")
    observed_at_utc: str = Field(..., description="Waktu pengamatan standar ISO (UTC)")
    description: str = Field(..., min_length=10, max_length=2000, description="Keterangan pengamatan lapangan (min 10 karakter)")
    photo_base64: Optional[str] = Field(None, description="Foto pendukung dalam format Base64 data URL atau string")
    reporter_name: Optional[str] = Field(None, max_length=100, description="Nama pelapor (opsional)")
    reporter_contact: Optional[str] = Field(None, max_length=100, description="Kontak pelapor (opsional)")


class ReportStatusUpdate(BaseModel):
    status: str = Field(..., description="Status verifikasi: PENDING, IN_REVIEW, VERIFIED, REJECTED")
    verification_notes: Optional[str] = Field(None, max_length=2000, description="Catatan verifikasi operator")
    rejection_reason: Optional[str] = Field(None, max_length=2000, description="Alasan penolakan jika status REJECTED")


def save_report_photo(photo_raw: str, uploads_dir: Path) -> tuple[str, str]:
    """Menyimpan data gambar Base64 ke direktori penyimpanan lokal uploads."""
    ext = "jpg"
    b64_content = photo_raw.strip()

    if "," in b64_content and b64_content.startswith("data:"):
        header, b64_content = b64_content.split(",", 1)
        header_lower = header.lower()
        if "image/png" in header_lower:
            ext = "png"
        elif "image/webp" in header_lower:
            ext = "webp"
        elif "image/jpeg" in header_lower or "image/jpg" in header_lower:
            ext = "jpg"

    try:
        binary_data = base64.b64decode(b64_content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Data gambar Base64 tidak valid.") from exc

    if len(binary_data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Ukuran file foto melebihi batas 5 MB.")

    if len(binary_data) < 10:
        raise HTTPException(status_code=422, detail="Data file foto terlalu kecil atau rusak.")

    filename = f"report_{uuid.uuid4().hex[:12]}.{ext}"
    target_path = uploads_dir / filename
    with open(target_path, "wb") as f:
        f.write(binary_data)

    photo_url = f"/uploads/reports/{filename}"
    return filename, photo_url


# ==============================================================================
# Helper & Endpoints Pelaporan Masyarakat
# ==============================================================================

def fetch_hotspots_for_reports(
    reports: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], bool, Optional[Dict[str, Optional[str]]]]:
    """
    Mengambil data hotspot FIRMS dengan rentang hari dinamis berdasarkan waktu pengamatan laporan kebakaran.
    Mengembalikan tuple: (hotspots_list, firms_available, coverage_date_range).
    Jika sinkronisasi API gagal atau tidak ada data tersedia, firms_available bernilai False.
    """
    now_utc = datetime.now(timezone.utc)
    fire_reports = [r for r in reports if r.get("category") == "kebakaran"]
    if not fire_reports:
        return [], True, None

    valid_deltas = []
    for r in fire_reports:
        dt = parse_iso_utc(r.get("observed_at_utc"))
        if dt:
            delta_days = (now_utc - dt).total_seconds() / 86400.0
            valid_deltas.append(delta_days)

    if valid_deltas:
        oldest_delta = max(valid_deltas)
        days_needed = math.ceil(oldest_delta + 3)
        effective_days = max(3, min(10, days_needed))
    else:
        effective_days = 3

    try:
        hotspots_res = pipeline_instance.run(total_days=effective_days)
        prov = hotspots_res.get("provenance", {})
        status = prov.get("status")

        if status == "NO_DATA_AVAILABLE":
            return [], False, None

        features = hotspots_res.get("features", [])
        cov_range = prov.get("observation_date_range") or {"min": None, "max": None}

        if not cov_range.get("min") or not cov_range.get("max"):
            min_d = (now_utc - timedelta(days=effective_days)).strftime("%Y-%m-%d")
            max_d = now_utc.strftime("%Y-%m-%d")
            cov_range = {"min": min_d, "max": max_d}

        return features, True, cov_range
    except Exception as exc:
        logger.warning("Kegagalan penarikan data FIRMS untuk laporan warga: %s", exc)
        return [], False, None


@app.get("/api/v1/reports", summary="Mengambil daftar laporan masyarakat")
def get_citizen_reports(
    category: Optional[str] = Query(None, description="Filter kategori: kebakaran, pembukaan_lahan, perubahan_tutupan"),
    status: Optional[str] = Query(None, description="Filter status: PENDING, IN_REVIEW, VERIFIED, REJECTED"),
    province: Optional[str] = Query(None, description="Filter nama provinsi daratan Indonesia"),
    region: Optional[str] = Query(None, description="Filter wilayah: 'kalimantan' untuk membatasi 5 provinsi Kalimantan"),
    limit: int = Query(200, ge=1, le=1000, description="Batas maksimum rekaman")
) -> Dict[str, Any]:
    """
    Mengambil data laporan warga masyarakat yang telah tersimpan di database.
    Format respons mendukung FeatureCollection GeoJSON dan array records untuk fleksibilitas klien.
    Informasi kontak pribadi (reporter_contact) dilindungi dan tidak ditampilkan ke publik.
    Koordinat publik disamarkan ke 3 desimal (~110m) demi privasi warga.
    """
    raw_reports = reports_repo.get_reports(
        category=category,
        status=status,
        province=province,
        limit=limit,
        public=False
    )

    if region and region.strip().lower() == "kalimantan":
        kalimantan_names = {p.lower() for p in KALIMANTAN_PROVINCES}
        raw_reports = [
            r for r in raw_reports
            if r.get("province") and r["province"].strip().lower() in kalimantan_names
        ]

    # Ambil data hotspot FIRMS dengan rentang waktu sesuai observasi laporan
    recent_hotspots, firms_available, cov_range = fetch_hotspots_for_reports(raw_reports)

    sanitized_reports = []
    for r in raw_reports:
        evidence = assess_report_evidence(
            report=r,
            hotspots=recent_hotspots,
            firms_available=firms_available,
            coverage_date_range=cov_range
        )
        pub_r = {
            **r,
            "latitude": round(float(r["latitude"]), 3),
            "longitude": round(float(r["longitude"]), 3),
            "evidence_assessment": evidence
        }
        pub_r.pop("reporter_contact", None)
        sanitized_reports.append(pub_r)

    features = [
        {
            "type": "Feature",
            "id": r["id"],
            "geometry": {
                "type": "Point",
                "coordinates": [round(float(r["longitude"]), 3), round(float(r["latitude"]), 3)]
            },
            "properties": {
                "id": r["id"],
                "category": r["category"],
                "province": r["province"],
                "observed_at_utc": r["observed_at_utc"],
                "description": r["description"],
                "photo_url": r["photo_url"],
                "status": r["status"],
                "evidence_assessment": r.get("evidence_assessment"),
                "is_duplicate_suspect": r["is_duplicate_suspect"],
                "duplicate_of_id": r["duplicate_of_id"],
                "created_at_utc": r["created_at_utc"],
            }
        }
        for r in sanitized_reports
    ]

    return {
        "type": "FeatureCollection",
        "count": len(sanitized_reports),
        "records": sanitized_reports,
        "features": features
    }


@app.post("/api/v1/reports", summary="Menyimpan laporan baru dari masyarakat")
def create_citizen_report(payload: CitizenReportCreate) -> Dict[str, Any]:
    """
    Menerima dan memvalidasi laporan indikasi kejadian dari masyarakat:
    - Validasi kategori kejadian.
    - Validasi batas daratan wilayah Indonesia (point-in-polygon).
    - Validasi rentang waktu pengamatan.
    - Deteksi otomatis kandidat duplikasi (radius 5 km & 24 jam).
    - Penyimpanan foto opsional jika disertakan.
    """
    valid_categories = [c.value for c in ReportCategory]
    if payload.category not in valid_categories:
        raise HTTPException(
            status_code=422,
            detail=f"Kategori '{payload.category}' tidak valid. Pilihan: {valid_categories}"
        )

    # Validasi rentang waktu observasi tidak di masa depan (toleransi 1 jam skews)
    try:
        clean_time_str = payload.observed_at_utc.replace("Z", "+00:00")
        dt_obs = datetime.fromisoformat(clean_time_str)
        if dt_obs.tzinfo is None:
            dt_obs = dt_obs.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        diff_future = (dt_obs - now_utc).total_seconds()
        if diff_future > 3600:
            raise HTTPException(
                status_code=422,
                detail="Waktu pengamatan tidak boleh berada di masa depan."
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Format waktu pengamatan (observed_at_utc) tidak valid. Gunakan format ISO-8601 UTC."
        ) from exc

    # Validasi koordinat terhadap poligon batas wilayah Indonesia
    is_inside, prov_name = pipeline_instance.spatial_filter.is_inside(payload.longitude, payload.latitude)
    if not is_inside:
        raise HTTPException(
            status_code=422,
            detail="Koordinat lokasi laporan berada di luar batas daratan wilayah Indonesia."
        )

    # Simpan file foto jika disertakan
    photo_fn = None
    photo_url = None
    if payload.photo_base64:
        photo_fn, photo_url = save_report_photo(payload.photo_base64, UPLOADS_DIR)

    report_dict, is_dup = reports_repo.create_report(
        category=payload.category,
        latitude=payload.latitude,
        longitude=payload.longitude,
        observed_at_utc=payload.observed_at_utc,
        description=payload.description.strip(),
        province=prov_name,
        photo_filename=photo_fn,
        photo_url=photo_url,
        reporter_name=payload.reporter_name.strip() if payload.reporter_name else None,
        reporter_contact=payload.reporter_contact.strip() if payload.reporter_contact else None,
        public=False
    )

    # Lakukan evaluasi bukti langsung untuk response yang baru disimpan
    recent_hotspots, firms_available, cov_range = fetch_hotspots_for_reports([report_dict])

    evidence = assess_report_evidence(
        report=report_dict,
        hotspots=recent_hotspots,
        firms_available=firms_available,
        coverage_date_range=cov_range
    )

    # Konteks kerentanan lingkungan prediktif (tanpa mengubah status bukti faktual)
    try:
        from .prediction_service import get_prediction_service
        env_risk = get_prediction_service().predict_fire_risk(
            lat=float(report_dict["latitude"]),
            lon=float(report_dict["longitude"]),
            province=report_dict.get("province")
        )
    except Exception:
        env_risk = None

    public_report = {
        **report_dict,
        "latitude": round(float(report_dict["latitude"]), 3),
        "longitude": round(float(report_dict["longitude"]), 3),
        "evidence_assessment": evidence,
        "environmental_risk": env_risk
    }
    public_report.pop("reporter_contact", None)

    return {
        "status": "success",
        "message": (
            "Laporan masyarakat berhasil disimpan sebagai informasi awal peninjauan."
            if not is_dup else
            "Laporan masyarakat berhasil disimpan. Terdeteksi indikasi duplikasi dengan laporan sebelumnya di area berdekatan."
        ),
        "is_duplicate_suspect": is_dup,
        "duplicate_of_id": public_report.get("duplicate_of_id"),
        "evidence_assessment": evidence,
        "data": public_report
    }


@app.get("/api/v1/reports/{report_id}", summary="Mengambil detail satu laporan masyarakat")
def get_citizen_report_by_id(report_id: str) -> Dict[str, Any]:
    """Mengambil informasi detail satu laporan berdasarkan ID (privasi kontak terlindungi)."""
    report = reports_repo.get_report_by_id(report_id, public=False)
    if not report:
        raise HTTPException(status_code=404, detail=f"Laporan dengan ID '{report_id}' tidak ditemukan.")

    recent_hotspots, firms_available, cov_range = fetch_hotspots_for_reports([report])

    evidence = assess_report_evidence(
        report=report,
        hotspots=recent_hotspots,
        firms_available=firms_available,
        coverage_date_range=cov_range
    )

    # Konteks kerentanan lingkungan prediktif (tanpa mengubah status bukti faktual)
    try:
        from .prediction_service import get_prediction_service
        env_risk = get_prediction_service().predict_fire_risk(
            lat=float(report["latitude"]),
            lon=float(report["longitude"]),
            province=report.get("province")
        )
    except Exception:
        env_risk = None

    public_report = {
        **report,
        "latitude": round(float(report["latitude"]), 3),
        "longitude": round(float(report["longitude"]), 3),
        "evidence_assessment": evidence,
        "environmental_risk": env_risk
    }
    public_report.pop("reporter_contact", None)
    return public_report


@app.patch("/api/v1/reports/{report_id}/status", summary="Verifikasi laporan oleh operator")
def update_report_status(report_id: str, payload: ReportStatusUpdate) -> Dict[str, Any]:
    """
    Memperbarui status verifikasi laporan oleh operator (disediakan untuk kompatibilitas sistem).
    Status valid: PENDING, IN_REVIEW, VERIFIED, REJECTED.
    Jika status REJECTED, alasan penolakan wajib disertakan.
    """
    valid_statuses = [s.value for s in ReportStatus]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Status '{payload.status}' tidak valid. Pilihan: {valid_statuses}"
        )

    if payload.status == ReportStatus.REJECTED.value:
        if not payload.rejection_reason or not payload.rejection_reason.strip():
            raise HTTPException(
                status_code=422,
                detail="Alasan penolakan (rejection_reason) wajib diisi jika laporan ditolak."
            )

    try:
        updated = reports_repo.update_verification_status(
            report_id=report_id,
            status=payload.status,
            verification_notes=payload.verification_notes.strip() if payload.verification_notes else None,
            rejection_reason=payload.rejection_reason.strip() if payload.rejection_reason else None,
            public=True
        )
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=str(val_err)) from val_err

    if not updated:
        raise HTTPException(status_code=404, detail=f"Laporan dengan ID '{report_id}' tidak ditemukan.")

    # Sanitasi kontak pribadi dan koordinat presisi
    updated.pop("reporter_contact", None)
    if "latitude" in updated:
        updated["latitude"] = round(float(updated["latitude"]), 3)
    if "longitude" in updated:
        updated["longitude"] = round(float(updated["longitude"]), 3)

    return {
        "status": "success",
        "message": f"Status verifikasi laporan berhasil diperbarui menjadi {payload.status}.",
        "data": updated
    }


@app.get("/api/v1/reports-meta", summary="Metadata kategori dan status pelaporan")
def get_reports_meta() -> Dict[str, Any]:
    """Mengembalikan daftar nilai kategori, status, dan kategori penilaian bukti yang sah."""
    return {
        "categories": [
            {"value": "kebakaran", "label": "Kebakaran atau kemunculan asap"},
            {"value": "pembukaan_lahan", "label": "Indikasi pembukaan lahan"},
            {"value": "perubahan_tutupan", "label": "Indikasi perubahan kondisi tutupan hutan"},
        ],
        "statuses": [
            {"value": "PENDING", "label": "Menunggu verifikasi"},
            {"value": "IN_REVIEW", "label": "Perlu pemeriksaan lebih lanjut"},
            {"value": "VERIFIED", "label": "Terverifikasi"},
            {"value": "REJECTED", "label": "Ditolak dengan alasan"},
        ],
        "evidence_assessments": [
            {
                "code": "SUPPORTING_INDICATION",
                "label": "Ada indikasi pendukung",
                "description": "Ditemukan data anomali termal atau riwayat perubahan tutupan pohon yang mendukung laporan."
            },
            {
                "code": "NO_MATCH_FOUND",
                "label": "Belum ditemukan kecocokan",
                "description": "Belum terdeteksi anomali termal pada radius/waktu terkait (ketiadaan hotspot bukan bukti tidak adanya kebakaran)."
            },
            {
                "code": "INSUFFICIENT_DATA",
                "label": "Belum dapat dinilai",
                "description": "Data raster atau satelit belum memadai untuk menilai titik spesifik secara objektif."
            },
            {
                "code": "NOT_ASSESSED",
                "label": "Belum dapat dinilai",
                "description": "Data satelit belum tersedia atau lokasi di luar cakupan evaluasi."
            }
        ],
        "scope": {
            "region": "Kalimantan Indonesia",
            "provinces": KALIMANTAN_PROVINCES,
            "excluded_territories": ["Sarawak (Malaysia)", "Sabah (Malaysia)", "Brunei Darussalam"]
        }
    }


@app.get("/api/v1/forest-loss/summary", summary="Ringkasan data kehilangan tutupan pohon Hansen GFC 2025 v1.13")
def get_forest_loss_summary_endpoint() -> Dict[str, Any]:
    """
    Mengembalikan statistik agregat kehilangan tutupan pohon Kalimantan Indonesia (2000–2025)
    berdasarkan dataset ilmiah UMD Hansen Global Forest Change v1.13.
    """
    return get_forest_loss_summary()


@app.get("/api/v1/forest-loss/point", summary="Evaluasi tutupan pohon titik koordinat")
def get_forest_loss_point_endpoint(
    latitude: float = Query(..., ge=-11.0, le=6.0, description="Latitude"),
    longitude: float = Query(..., ge=95.0, le=141.5, description="Longitude"),
    province: Optional[str] = Query(None, description="Nama provinsi"),
    use_official: Optional[bool] = Query(None, description="Gunakan data subset resmi Hansen UMD jika tersedia"),
) -> Dict[str, Any]:
    """
    Mengevaluasi indikasi tutupan pohon dan menghitung luas 1 piksel WGS84 dalam hektare
    menggunakan proyeksi geodesik berdasarkan garis lintang koordinat.
    """
    return evaluate_forest_change_point(
        lat=latitude,
        lon=longitude,
        province=province,
        use_official=use_official,
    )


@app.get("/api/v1/boundaries/kalimantan", summary="Poligon batas 5 provinsi Kalimantan Indonesia")
def get_kalimantan_boundaries_endpoint() -> Dict[str, Any]:
    """
    Mengembalikan GeoJSON FeatureCollection poligon batas administratif 5 provinsi Kalimantan Indonesia
    yang dilengkapi dengan data baseline tutupan pohon Hansen GFC v1.13.
    """
    return get_kalimantan_geojson()


@app.get("/api/v1/predict/fire-risk", summary="Prediksi probabilitas risiko karhutla berbasis ML")
def predict_fire_risk_endpoint(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    province: Optional[str] = Query(None, description="Nama provinsi"),
) -> Dict[str, Any]:
    """
    Memprediksi probabilitas risiko kebakaran hutan/lahan berbasis model Machine Learning
    dengan parameter cuaca mikro real-time Open-Meteo dan tutupan kanopi Hansen GFC v1.13.
    """
    from .prediction_service import get_prediction_service
    service = get_prediction_service()
    return service.predict_fire_risk(lat=latitude, lon=longitude, province=province)



