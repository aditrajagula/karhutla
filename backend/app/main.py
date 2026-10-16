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
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from shapely.geometry import mapping, shape

from .config import (
    BOUNDARIES_PATH,
    CORS_ORIGINS,
    FIRMS_DEFAULT_SOURCE,
    FIRMS_MAP_KEY,
    GLAD_FOREST_DIR,
    SNAPSHOTS_DIR,
    UPLOADS_DIR,
)
from .pipeline import HotspotPipeline
from .snapshot_manager import find_latest_valid_snapshot
from .reports_storage import (
    reports_repo,
    ReportCategory,
    ReportStatus,
    UserRole,
    create_auth_token,
    verify_auth_token,
)
from .forest_change_service import (
    get_forest_loss_summary,
    evaluate_forest_change_point,
    KALIMANTAN_PROVINCES,
    HANSEN_PROVINCIAL_BASELINE_HA,
    HANSEN_ANNUAL_LOSS_HA,
)
from .evidence_service import assess_report_evidence, parse_iso_utc
from .glad_forest_reader import (
    lookup_forest_extent,
    check_glad_forest_layer_availability,
    KALIMANTAN_GLAD_TILES,
)

logger = logging.getLogger(__name__)
PEATLAND_GEOJSON_PATH = Path(__file__).with_name("peat_kalimantan_big_official.geojson")
PEATLAND_DISPLAY_GEOJSON_PATH = Path(__file__).with_name("peat_kalimantan_display.geojson")
FOREST_AREA_GEOJSON_PATH = Path(__file__).with_name("kawasan_hutan_kalimantan.geojson")
FOREST_AREA_DISPLAY_GEOJSON_PATH = Path(__file__).with_name("kawasan_hutan_kalimantan_display.geojson")
CLASSIFIED_HOTSPOTS_GEOJSON_PATH = (
    Path(__file__).with_name("final_hotspots_segmentation.geojson")
    if Path(__file__).with_name("final_hotspots_segmentation.geojson").is_file()
    else Path(__file__).with_name("hotspots_kalimantan_final.geojson")
)
FIRMS_MANIFEST_PATH = Path(__file__).with_name("firms_manifest.json")
FOREST_OVERLAY_PNG_PATH = GLAD_FOREST_DIR / "kalimantan" / "kalteng_forest_overlay.png"
FOREST_SUBSET_TIF_PATH = GLAD_FOREST_DIR / "kalimantan" / "GLAD_Forest_extent_2020_00N_110E_kalteng_demo.tif"
PEATLAND_DISPLAY_SIMPLIFICATION_DEGREES = 0.0001

REFRESH_INTERVAL_SECONDS = int(os.getenv("FIRMS_REFRESH_INTERVAL_SECONDS", "1800"))


async def _firms_auto_refresh_loop() -> None:
    # Tunggu satu interval sebelum auto-refresh pertama agar start-up server instan
    if REFRESH_INTERVAL_SECONDS > 0:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.to_thread(pipeline_instance.run, total_days=2, force_snapshot=False)
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

# Aktifkan CORS agar frontend (lokal maupun domain produksi Railway/Render/Vercel) dapat mengakses API
DEFAULT_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if not CORS_ORIGINS or CORS_ORIGINS == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    custom_origins = [
        o.strip().strip('"').strip("'")
        for o in CORS_ORIGINS.strip("[]").split(",")
        if o.strip()
    ]
    ALLOWED_ORIGINS = list(dict.fromkeys(DEFAULT_LOCAL_ORIGINS + custom_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
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
# Spatial Filter Gambut & Kawasan Hutan
# ==============================================================================

@lru_cache(maxsize=1)
def _get_known_segmentation_map() -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Map cepat (lat_round, lon_round) -> properties dari final_hotspots_segmentation.geojson"""
    fast_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if CLASSIFIED_HOTSPOTS_GEOJSON_PATH.is_file():
        try:
            with CLASSIFIED_HOTSPOTS_GEOJSON_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
                for ft in data.get("features", []):
                    coords = ft.get("geometry", {}).get("coordinates", [0, 0])
                    key = (round(float(coords[1]), 4), round(float(coords[0]), 4))
                    props = ft.get("properties", {})
                    fast_map[key] = {
                        "in_peat": bool(props.get("in_peat", False)),
                        "peat_landform": props.get("peat_landform"),
                        "in_forest": bool(props.get("in_forest", False)),
                        "forest_fungsi": props.get("forest_fungsi"),
                        "forest_name": props.get("forest_name"),
                        "is_focus_hotspot": bool(props.get("is_focus_hotspot", False)),
                    }
        except Exception as exc:
            logger.warning("Gagal memuat known_segmentation_map: %s", exc)
    return fast_map


@lru_cache(maxsize=1)
def _get_segmentation_tree():
    from shapely.strtree import STRtree
    from shapely.geometry import shape

    peat_path = PEATLAND_DISPLAY_GEOJSON_PATH if PEATLAND_DISPLAY_GEOJSON_PATH.is_file() else PEATLAND_GEOJSON_PATH
    forest_path = FOREST_AREA_DISPLAY_GEOJSON_PATH if FOREST_AREA_DISPLAY_GEOJSON_PATH.is_file() else FOREST_AREA_GEOJSON_PATH

    peat_geoms = []
    peat_props = []
    if peat_path.is_file():
        with peat_path.open(encoding="utf-8") as pf:
            for ft in json.load(pf).get("features", []):
                peat_geoms.append(shape(ft["geometry"]))
                peat_props.append(ft.get("properties", {}))

    forest_geoms = []
    forest_props = []
    if forest_path.is_file():
        with forest_path.open(encoding="utf-8") as ff:
            for ft in json.load(ff).get("features", []):
                forest_geoms.append(shape(ft["geometry"]))
                forest_props.append(ft.get("properties", {}))

    all_geoms = peat_geoms + forest_geoms
    tree = STRtree(all_geoms) if all_geoms else None
    return tree, peat_geoms, peat_props, forest_geoms, forest_props


def check_hotspot_segmentation(lon: float, lat: float) -> Tuple[bool, bool, Optional[str], Optional[str], Optional[str]]:
    """Mengembalikan (in_peat, in_forest, peat_landform, forest_fungsi, forest_name)."""
    # 1. Cek fast precomputed map terlebih dahulu (0 ms)
    fast_map = _get_known_segmentation_map()
    key = (round(float(lat), 4), round(float(lon), 4))
    if key in fast_map:
        m = fast_map[key]
        return m["in_peat"], m["in_forest"], m["peat_landform"], m["forest_fungsi"], m["forest_name"]

    # 2. Jika titik baru dari NASA FIRMS live API, uji via STRtree
    tree, peat_geoms, peat_props, forest_geoms, forest_props = _get_segmentation_tree()
    if not tree:
        return False, False, None, None, None

    from shapely.geometry import Point
    pt = Point(lon, lat)
    candidate_indices = tree.query(pt)
    in_peat = False
    in_forest = False
    peat_landform = None
    forest_fungsi = None
    forest_name = None
    num_peat = len(peat_geoms)

    for idx in candidate_indices:
        if idx < num_peat:
            if not in_peat and peat_geoms[idx].contains(pt):
                in_peat = True
                p = peat_props[idx]
                peat_landform = p.get("landform") or p.get("namobj") or "Lahan Gambut"
        else:
            f_idx = idx - num_peat
            if not in_forest and forest_geoms[f_idx].contains(pt):
                in_forest = True
                f = forest_props[f_idx]
                forest_name = f.get("nkws") or f.get("namobj") or "Kawasan Hutan"
                forest_fungsi = f.get("fungsitap") or f.get("fungsi")
        if in_peat and in_forest:
            break

    return in_peat, in_forest, peat_landform, forest_fungsi, forest_name


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
    region: Optional[str] = Query("kalimantan", description="Filter cakupan wilayah: 'kalimantan' untuk membatasi 5 provinsi Kalimantan"),
    focus_segmentation: bool = Query(True, description="Filter hanya hotspot di kawasan hutan atau lahan gambut"),
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

    # Filter 1: Fokus wilayah Pulau Kalimantan
    if region and region.strip().lower() == "kalimantan":
        kalimantan_names = {p.lower() for p in KALIMANTAN_PROVINCES}
        kalimantan_features = []
        for f in features:
            coords = f["geometry"]["coordinates"]
            lon, lat = coords[0], coords[1]
            prov = str(f["properties"].get("province") or "").strip().lower()
            if prov in kalimantan_names:
                kalimantan_features.append(f)
            else:
                in_kal, _ = pipeline_instance.spatial_filter.is_inside_kalimantan(lon, lat)
                if in_kal:
                    kalimantan_features.append(f)
        features = kalimantan_features

    # Filter 2: Hanya tampilkan titik di segmentasi Kawasan Hutan ATAU Lahan Gambut
    if focus_segmentation:
        segmented_features = []
        for f in features:
            coords = f["geometry"]["coordinates"]
            lon, lat = coords[0], coords[1]
            has_peat_prop = f["properties"].get("in_peat")
            has_forest_prop = f["properties"].get("in_forest")
            if has_peat_prop is not None and has_forest_prop is not None:
                in_peat = bool(has_peat_prop)
                in_forest = bool(has_forest_prop)
            else:
                in_peat, in_forest, peat_landform, forest_fungsi, forest_name = check_hotspot_segmentation(lon, lat)
                f["properties"]["in_peat"] = in_peat
                f["properties"]["in_forest"] = in_forest
                if peat_landform:
                    f["properties"]["peat_landform"] = peat_landform
                if forest_fungsi:
                    f["properties"]["forest_fungsi"] = forest_fungsi
                if forest_name:
                    f["properties"]["forest_name"] = forest_name
                f["properties"]["is_focus_hotspot"] = in_peat or in_forest

            if in_peat or in_forest:
                segmented_features.append(f)
        features = segmented_features

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
            "province": f["properties"].get("province"),
            "in_peat": bool(f["properties"].get("in_peat", False)),
            "in_forest": bool(f["properties"].get("in_forest", False)),
            "peat_landform": f["properties"].get("peat_landform"),
            "forest_fungsi": f["properties"].get("forest_fungsi"),
            "forest_name": f["properties"].get("forest_name"),
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
    glad_available, installed_tiles, details = check_glad_forest_layer_availability()
    kalimantan_installed = [t for t in installed_tiles if t in KALIMANTAN_GLAD_TILES]
    if len(kalimantan_installed) > 0:
        has_subset = any(details.get(t, {}).get("is_subset", False) for t in kalimantan_installed)
        subset_note = " (cakupan parsial: 4 subset zona sampel demo terpasang)" if has_subset else ""
        status_msg = f"Layer raster tutupan hutan GLAD 2020 aktif ({len(kalimantan_installed)}/4 kuadran dengan subset sampel terpasang: {', '.join(kalimantan_installed)}{subset_note})."
    elif len(installed_tiles) > 0:
        status_msg = f"Raster GLAD 2020 terdeteksi ({', '.join(installed_tiles)}), namun 4 tile khusus Kalimantan (00N_100E, 00N_110E, 10N_100E, 10N_110E) belum tersedia di data/raster/forest/."
    else:
        status_msg = "Dataset raster GLAD Forest Extent 2020 belum tersedia di direktori lokal data/raster/forest/."

    return ContextLayersResponse(
        forest_layer=ContextLayerItem(
            available=glad_available,
            source="GLAD Global Land Cover and Land Use Change 2000–2020 (Forest extent 2020, UMD)",
            status_message=status_msg,
            feature_count=len(kalimantan_installed) if glad_available else len(installed_tiles)
        ),
        peatland_layer=ContextLayerItem(
            available=PEATLAND_GEOJSON_PATH.is_file(),
            source="GeoJSON lokal peat_kalimantan_big_official.geojson",
            status_message=(
                "Layer poligon gambut Kalimantan tersedia untuk ditampilkan. "
                "Tahun, lisensi, dan provenance dataset belum tercatat pada manifest."
                if PEATLAND_GEOJSON_PATH.is_file()
                else "Dataset poligon gambut Kalimantan belum tersedia pada server."
            )
        ),
        boundary_layer=ContextLayerItem(
            available=True,
            source="Batas Daratan 34 Provinsi Indonesia (WGS84 EPSG:4326)",
            status_message="Geometri batas wilayah daratan Indonesia aktif untuk filter spasial.",
            feature_count=len(pipeline_instance.spatial_filter.geometries)
        )
    )


@lru_cache(maxsize=1)
def _peatland_display_geojson_bytes() -> bytes:
    """Prepare a lighter display-only copy; source geometry remains unchanged."""
    if PEATLAND_DISPLAY_GEOJSON_PATH.is_file():
        return PEATLAND_DISPLAY_GEOJSON_PATH.read_bytes()

    if not PEATLAND_GEOJSON_PATH.is_file():
        raise HTTPException(status_code=503, detail="GeoJSON gambut belum tersedia.")

    with PEATLAND_GEOJSON_PATH.open(encoding="utf-8") as source_file:
        collection = json.load(source_file)
    if collection.get("type") != "FeatureCollection" or not isinstance(
        collection.get("features"), list
    ):
        raise HTTPException(status_code=500, detail="Format GeoJSON gambut tidak valid.")

    for feature in collection["features"]:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise HTTPException(
                status_code=500,
                detail="GeoJSON gambut memiliki geometri kosong atau tidak valid.",
            )
        display_geometry = geometry.simplify(
            PEATLAND_DISPLAY_SIMPLIFICATION_DEGREES,
            preserve_topology=True,
        )
        feature["geometry"] = mapping(display_geometry)

    return json.dumps(collection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@app.get("/api/v1/map-data/peatland", summary="GeoJSON layer poligon gambut Kalimantan")
def get_peatland_map_data() -> Response:
    return Response(
        content=_peatland_display_geojson_bytes(),
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/v1/map-data/forest-area", summary="GeoJSON layer poligon kawasan hutan Kalimantan (KLHK / SatuPeta)")
def get_forest_area_map_data() -> Response:
    if FOREST_AREA_DISPLAY_GEOJSON_PATH.is_file():
        return Response(
            content=FOREST_AREA_DISPLAY_GEOJSON_PATH.read_bytes(),
            media_type="application/geo+json",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    if not FOREST_AREA_GEOJSON_PATH.is_file():
        raise HTTPException(status_code=503, detail="GeoJSON kawasan hutan belum tersedia.")
    return FileResponse(
        FOREST_AREA_GEOJSON_PATH,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/v1/map-data/classified-hotspots", summary="GeoJSON hotspot FIRMS dengan klasifikasi gambut")
def get_classified_hotspots_map_data() -> FileResponse:
    if not CLASSIFIED_HOTSPOTS_GEOJSON_PATH.is_file():
        raise HTTPException(status_code=503, detail="GeoJSON hotspot terklasifikasi belum tersedia.")
    return FileResponse(
        CLASSIFIED_HOTSPOTS_GEOJSON_PATH,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/v1/map-data/firms-manifest", summary="Metadata dataset hotspot FIRMS peta Kalimantan")
def get_firms_map_manifest() -> FileResponse:
    if not FIRMS_MANIFEST_PATH.is_file():
        raise HTTPException(status_code=503, detail="Manifest dataset FIRMS belum tersedia.")
    return FileResponse(
        FIRMS_MANIFEST_PATH,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


KALIMANTAN_FOREST_TILE_CONFIGS = {
    "00N_100E": {
        "tile_id": "00N_100E",
        "region": "Zona Sampel Kalbar Selatan (Ketapang & Delta Pawan)",
        "province": "Kalimantan Barat",
        "is_full_tile": False,
        "coverage_type": "subset_sample",
        "official_tile_bounds": {"west": 100.0, "east": 110.0, "south": -10.0, "north": 0.0},
        "sample_area_sq_deg": 0.25,
        "tif_file": "GLAD_Forest_extent_2020_00N_100E_ketapang_demo.tif",
        "overlay_file": "ketapang_forest_overlay.png",
        "bounds": {"west": 109.50, "east": 110.00, "south": -2.00, "north": -1.50},
        "leaflet_bounds": [[-2.00, 109.50], [-1.50, 110.00]],
        "resolution_meters": 30.0,
        "resolution_degrees": 0.00025,
        "width_pixels": 2000,
        "height_pixels": 2000,
        "pixel_statistics": {
            "forest_pixels": 80391,
            "non_forest_pixels": 3919609,
            "nodata_pixels": 0,
            "forest_percentage": 2.01,
        },
    },
    "00N_110E": {
        "tile_id": "00N_110E",
        "region": "Zona Sampel Kalteng & Kalsel (Palangka Raya, Pulang Pisau, Sebangau)",
        "province": "Kalimantan Tengah",
        "is_full_tile": False,
        "coverage_type": "subset_sample",
        "official_tile_bounds": {"west": 110.0, "east": 120.0, "south": -10.0, "north": 0.0},
        "sample_area_sq_deg": 0.72,
        "tif_file": "GLAD_Forest_extent_2020_00N_110E_kalteng_demo.tif",
        "overlay_file": "kalteng_forest_overlay.png",
        "bounds": {"west": 113.50, "east": 114.40, "south": -2.60, "north": -1.80},
        "leaflet_bounds": [[-2.60, 113.50], [-1.80, 114.40]],
        "resolution_meters": 30.0,
        "resolution_degrees": 0.00025,
        "width_pixels": 3600,
        "height_pixels": 3200,
        "pixel_statistics": {
            "forest_pixels": 8445845,
            "non_forest_pixels": 3074155,
            "nodata_pixels": 0,
            "forest_percentage": 73.31,
        },
    },
    "10N_100E": {
        "tile_id": "10N_100E",
        "region": "Zona Sampel Kalbar Utara (Pontianak, Mempawah, Kubu Raya)",
        "province": "Kalimantan Barat",
        "is_full_tile": False,
        "coverage_type": "subset_sample",
        "official_tile_bounds": {"west": 100.0, "east": 110.0, "south": 0.0, "north": 10.0},
        "sample_area_sq_deg": 0.25,
        "tif_file": "GLAD_Forest_extent_2020_10N_100E_kalbar_demo.tif",
        "overlay_file": "kalbar_forest_overlay.png",
        "bounds": {"west": 109.10, "east": 109.60, "south": 0.00, "north": 0.50},
        "leaflet_bounds": [[0.00, 109.10], [0.50, 109.60]],
        "resolution_meters": 30.0,
        "resolution_degrees": 0.00025,
        "width_pixels": 2000,
        "height_pixels": 2000,
        "pixel_statistics": {
            "forest_pixels": 2749613,
            "non_forest_pixels": 1250387,
            "nodata_pixels": 0,
            "forest_percentage": 68.74,
        },
    },
    "10N_110E": {
        "tile_id": "10N_110E",
        "region": "Zona Sampel Kaltim (Samarinda, Delta Mahakam, Kutai Kartanegara)",
        "province": "Kalimantan Timur",
        "is_full_tile": False,
        "coverage_type": "subset_sample",
        "official_tile_bounds": {"west": 110.0, "east": 120.0, "south": 0.0, "north": 10.0},
        "sample_area_sq_deg": 0.36,
        "tif_file": "GLAD_Forest_extent_2020_10N_110E_kaltim_demo.tif",
        "overlay_file": "kaltim_forest_overlay.png",
        "bounds": {"west": 116.80, "east": 117.40, "south": 0.00, "north": 0.60},
        "leaflet_bounds": [[0.00, 116.80], [0.60, 117.40]],
        "resolution_meters": 30.0,
        "resolution_degrees": 0.00025,
        "width_pixels": 2400,
        "height_pixels": 2400,
        "pixel_statistics": {
            "forest_pixels": 4108899,
            "non_forest_pixels": 1651101,
            "nodata_pixels": 0,
            "forest_percentage": 71.34,
        },
    },
}

FOREST_LEGEND = [
    {"label": "Hutan Kanopi >= 5m (GLAD 2020)", "color": "#10B981", "value": 1},
    {"label": "Bukan Hutan (GLAD 2020)", "color": "#94A3B8", "value": 0},
]

FOREST_CAVEAT = (
    "Klasifikasi tutupan pohon GLAD 2020 merepresentasikan kondisi biofisik kanopi tahun 2020 "
    "(tinggi >= 5m, FAO FRA baseline), bukan kondisi real-time terkini. "
    "PERINGATAN CAKUPAN: Data aktif merupakan 4 subset sampel demo regional (~1.33 deg² daratan / "
    "~3.05% luas daratan Kalimantan). 96.95% area pulau lainnya belum diunduh (berstatus UNKNOWN). "
    "Persentase tutupan 60.86% adalah persentase sampel dalam 4 jendela observasi tersebut, "
    "bukan statistik seluruh Pulau Kalimantan."
)


@app.get("/api/v1/map-data/forest-extent/tiles", summary="Daftar seluruh tile segmentasi tutupan hutan Kalimantan")
def get_forest_extent_tiles() -> Dict[str, Any]:
    """
    Mengembalikan daftar tile GLAD Forest Extent 2020 yang mencakup zona sampel Pulau Kalimantan,
    beserta status ketersediaan, batas geospasial Leaflet, ukuran berkas, dan URL overlay PNG.
    Mendukung deteksi otomatis jika tile penuh telah diunduh di data/raster/forest/tiles_full/.
    """
    kalimantan_dir = GLAD_FOREST_DIR / "kalimantan"
    tiles_full_dir = GLAD_FOREST_DIR / "tiles_full"
    tile_list = []
    total_forest_pixels = 0
    total_non_forest_pixels = 0

    for tile_id, cfg in KALIMANTAN_FOREST_TILE_CONFIGS.items():
        full_tif_p = tiles_full_dir / f"{tile_id}.tif"
        if full_tif_p.is_file():
            tif_p = full_tif_p
            is_full = True
        else:
            tif_p = kalimantan_dir / cfg["tif_file"]
            is_full = False

        png_p = kalimantan_dir / cfg["overlay_file"]
        is_avail = tif_p.is_file() and png_p.is_file()

        item = dict(cfg)
        item["available"] = is_avail
        item["is_full_tile"] = is_full
        item["coverage_type"] = "full_tile" if is_full else "subset_sample"
        item["tif_size_bytes"] = tif_p.stat().st_size if tif_p.is_file() else 0
        item["overlay_size_bytes"] = png_p.stat().st_size if png_p.is_file() else 0
        item["overlay_url"] = f"/api/v1/map-data/forest-extent/tiles/{tile_id}/overlay"
        item["meta_url"] = f"/api/v1/map-data/forest-extent/tiles/{tile_id}/meta"

        stats = cfg.get("pixel_statistics", {})
        total_forest_pixels += stats.get("forest_pixels", 0)
        total_non_forest_pixels += stats.get("non_forest_pixels", 0)
        tile_list.append(item)

    total_valid = total_forest_pixels + total_non_forest_pixels
    overall_forest_pct = round((total_forest_pixels / total_valid) * 100, 2) if total_valid > 0 else 0

    all_full = len(tile_list) == 4 and all(t.get("is_full_tile", False) for t in tile_list if t["available"])
    coverage_status = "FULL" if all_full else "PARTIAL"
    scope_desc = (
        "Cakupan Penuh (4 Tile Resmi GLAD 2020 Pulau Kalimantan)"
        if all_full else
        "Cakupan Parsial (4 Zona Sampel Regional Kalimantan: Ketapang, Palangka Raya, Pontianak, Samarinda)"
    )
    coverage_pct_land = 100.0 if all_full else 3.05

    return {
        "dataset": "GLAD Global Land Cover and Land Use Change 2000–2020",
        "layer": "Forest extent 2020",
        "period": "2020",
        "scope": scope_desc,
        "coverage_status": coverage_status,
        "is_full_coverage": all_full,
        "coverage_percentage_of_kalimantan": coverage_pct_land,
        "total_quadrants": len(KALIMANTAN_FOREST_TILE_CONFIGS),
        "available_quadrants": sum(1 for t in tile_list if t["available"]),
        "all_quadrants_available": all(t["available"] for t in tile_list),
        "total_forest_pixels": total_forest_pixels,
        "total_non_forest_pixels": total_non_forest_pixels,
        "sample_forest_percentage": overall_forest_pct,
        "overall_forest_percentage": overall_forest_pct,
        "legend": FOREST_LEGEND,
        "caveat": FOREST_CAVEAT,
        "tiles": tile_list,
    }


@app.get("/api/v1/map-data/forest-extent/tiles/{tile_id}/meta", summary="Metadata spesifik per-tile tutupan hutan")
def get_forest_extent_tile_meta(tile_id: str) -> Dict[str, Any]:
    if tile_id not in KALIMANTAN_FOREST_TILE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Tile ID '{tile_id}' tidak dikenal untuk Pulau Kalimantan.")

    cfg = KALIMANTAN_FOREST_TILE_CONFIGS[tile_id]
    kalimantan_dir = GLAD_FOREST_DIR / "kalimantan"
    tif_p = kalimantan_dir / cfg["tif_file"]
    png_p = kalimantan_dir / cfg["overlay_file"]
    is_avail = tif_p.is_file() and png_p.is_file()

    res = dict(cfg)
    res["available"] = is_avail
    res["dataset"] = "GLAD Global Land Cover and Land Use Change 2000–2020"
    res["layer"] = "Forest extent 2020"
    res["period"] = "2020"
    res["tif_size_bytes"] = tif_p.stat().st_size if tif_p.is_file() else 0
    res["overlay_size_bytes"] = png_p.stat().st_size if png_p.is_file() else 0
    res["overlay_url"] = f"/api/v1/map-data/forest-extent/tiles/{tile_id}/overlay"
    res["legend"] = FOREST_LEGEND
    res["caveat"] = FOREST_CAVEAT
    return res


@app.get("/api/v1/map-data/forest-extent/tiles/{tile_id}/overlay", summary="Citra PNG overlay per-tile tutupan hutan")
def get_forest_extent_tile_overlay(tile_id: str) -> FileResponse:
    if tile_id not in KALIMANTAN_FOREST_TILE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Tile ID '{tile_id}' tidak dikenal untuk Pulau Kalimantan.")

    cfg = KALIMANTAN_FOREST_TILE_CONFIGS[tile_id]
    overlay_path = GLAD_FOREST_DIR / "kalimantan" / cfg["overlay_file"]
    if not overlay_path.is_file():
        raise HTTPException(status_code=503, detail=f"Citra overlay untuk tile '{tile_id}' belum tersedia.")

    return FileResponse(
        overlay_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/v1/map-data/forest-extent/meta", summary="Metadata raster segmentasi tutupan hutan GLAD 2020 Kalimantan")
def get_forest_extent_map_meta() -> Dict[str, Any]:
    """
    Mengembalikan metadata geospasial, bounds, statistik piksel, dan legenda
    untuk layer segmentasi tutupan hutan GLAD 2020 (kompatibel ke belakang).
    """
    available = FOREST_OVERLAY_PNG_PATH.is_file() and FOREST_SUBSET_TIF_PATH.is_file()
    file_size_bytes = FOREST_OVERLAY_PNG_PATH.stat().st_size if FOREST_OVERLAY_PNG_PATH.is_file() else 0
    geotiff_size_bytes = FOREST_SUBSET_TIF_PATH.stat().st_size if FOREST_SUBSET_TIF_PATH.is_file() else 0

    return {
        "available": available,
        "dataset": "GLAD Global Land Cover and Land Use Change 2000–2020",
        "layer": "Forest extent 2020",
        "period": "2020",
        "tile_id": "00N_110E",
        "region": "Kalimantan Tengah (Palangka Raya & Sekitarnya)",
        "bounds": {
            "west": 113.50,
            "east": 114.40,
            "south": -2.60,
            "north": -1.80
        },
        "leaflet_bounds": [
            [-2.60, 113.50],
            [-1.80, 114.40]
        ],
        "resolution_degrees": 0.00025,
        "resolution_meters": 30.0,
        "width_pixels": 3600,
        "height_pixels": 3200,
        "crs": "EPSG:4326",
        "overlay_format": "PNG (RGBA 4-band)",
        "overlay_file_size_bytes": file_size_bytes,
        "geotiff_file_size_bytes": geotiff_size_bytes,
        "overlay_url": "/api/v1/map-data/forest-extent/overlay",
        "pixel_statistics": {
            "forest_pixels": 8445845,
            "non_forest_pixels": 3074155,
            "nodata_pixels": 0,
            "forest_percentage": 73.31
        },
        "total_quadrants": 4,
        "all_quadrants_available": True,
        "legend": FOREST_LEGEND,
        "caveat": FOREST_CAVEAT
    }


@app.get("/api/v1/map-data/forest-extent/overlay", summary="Citra PNG overlay segmentasi tutupan hutan GLAD 2020")
def get_forest_extent_overlay() -> FileResponse:
    """
    Mengirimkan citra web-ready PNG 4-band RGBA transparan untuk visualisasi cepat
    lapisan tutupan hutan GLAD 2020 pada peta interaktif (kompatibilitas ke belakang).
    """
    if not FOREST_OVERLAY_PNG_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Berkas overlay tutupan hutan belum dibuat di data/raster/forest/kalimantan/."
        )
    return FileResponse(
        FOREST_OVERLAY_PNG_PATH,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
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
# Model Skema Autentikasi & Pelaporan Masyarakat (Citizen Reports)
# ==============================================================================

class LoginPayload(BaseModel):
    email: str = Field(..., description="Alamat email pengguna")
    password: str = Field(..., description="Kata sandi pengguna")


class RegisterPayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nama lengkap warga")
    email: str = Field(..., max_length=150, description="Alamat email warga")
    password: str = Field(..., min_length=6, max_length=100, description="Kata sandi (minimal 6 karakter)")


def _extract_bearer_user(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Format header Authorization tidak valid.")
    payload = verify_auth_token(parts[1].strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Sesi login telah berakhir atau token tidak valid.")
    return {
        "id": payload["sub"],
        "email": payload["email"],
        "name": payload["name"],
        "role": payload["role"],
    }


@app.post("/api/v1/auth/login", summary="Login akun Warga atau Petugas")
def login_user_endpoint(payload: LoginPayload) -> Dict[str, Any]:
    user = reports_repo.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah.")
    token = create_auth_token(user)
    return {
        "status": "success",
        "token": token,
        "user": user,
    }


@app.post("/api/v1/auth/register", summary="Registrasi akun Warga baru")
def register_user_endpoint(payload: RegisterPayload) -> Dict[str, Any]:
    try:
        user = reports_repo.register_user(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role=UserRole.WARGA.value,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    token = create_auth_token(user)
    return {
        "status": "success",
        "token": token,
        "user": user,
    }


@app.get("/api/v1/auth/me", summary="Profil akun yang sedang login")
def get_current_user_endpoint(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    user = _extract_bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Token autentikasi diperlukan.")
    return {"status": "success", "user": user}


class CitizenReportCreate(BaseModel):
    category: str = Field(..., description="Kategori: penebangan_liar, pembukaan_lahan, perambahan_hutan, kebakaran, perubahan_tutupan")
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
    category: Optional[str] = Query(None, description="Filter kategori: penebangan_liar, pembukaan_lahan, perambahan_hutan, kebakaran, perubahan_tutupan"),
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
    raw_cat = payload.category.strip().lower()
    cat_norm = {
        "asap_kebakaran": "kebakaran",
        "kebakaran_hutan": "kebakaran",
        "deforestasi": "pembukaan_lahan",
        "land_clearing": "pembukaan_lahan",
        "illegal_logging": "penebangan_liar",
        "pembalakan_liar": "penebangan_liar",
        "perambahan": "perambahan_hutan",
        "alih_fungsi_bekas_karhutla": "perubahan_tutupan",
    }.get(raw_cat, raw_cat)

    valid_categories = [c.value for c in ReportCategory]
    if cat_norm not in valid_categories:
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
        category=cat_norm,
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


@app.patch("/api/v1/reports/{report_id}/status", summary="Verifikasi laporan oleh operator / petugas")
def update_report_status(
    report_id: str,
    payload: ReportStatusUpdate,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Memperbarui status verifikasi laporan oleh petugas.
    Status valid: PENDING, IN_REVIEW, VERIFIED, REJECTED.
    Jika status REJECTED, alasan penolakan wajib disertakan.
    """
    user = _extract_bearer_user(authorization)
    if user is not None and user.get("role") != UserRole.PETUGAS.value:
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak. Hanya akun Petugas yang dapat memverifikasi laporan warga."
        )

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
            public=False
        )
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=str(val_err)) from val_err

    if not updated:
        raise HTTPException(status_code=404, detail=f"Laporan dengan ID '{report_id}' tidak ditemukan.")

    recent_hotspots, firms_available, cov_range = fetch_hotspots_for_reports([updated])
    evidence = assess_report_evidence(
        report=updated,
        hotspots=recent_hotspots,
        firms_available=firms_available,
        coverage_date_range=cov_range,
    )

    # Sanitasi kontak pribadi dan koordinat presisi
    updated.pop("reporter_contact", None)
    if "latitude" in updated:
        updated["latitude"] = round(float(updated["latitude"]), 3)
    if "longitude" in updated:
        updated["longitude"] = round(float(updated["longitude"]), 3)
    updated["evidence_assessment"] = evidence

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
            {"value": "penebangan_liar", "label": "Penebangan Liar / Pembalakan Ilegal (Illegal Logging)"},
            {"value": "pembukaan_lahan", "label": "Pembukaan Lahan Hutan (Land Clearing)"},
            {"value": "perambahan_hutan", "label": "Perambahan Kawasan Hutan Lindung/Konservasi"},
            {"value": "kebakaran", "label": "Kebakaran Pembukaan Lahan (Slash-and-Burn)"},
            {"value": "perubahan_tutupan", "label": "Perubahan Drastis Tutupan Kanopi Pohon"},
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


@app.get("/api/v1/forest-extent/point", summary="Klasifikasi tutupan hutan GLAD 2020 titik koordinat")
def get_forest_extent_point_endpoint(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
) -> Dict[str, Any]:
    """
    Lookup klasifikasi tutupan hutan berbasis raster lokal GLAD Forest Extent 2020.
    Mengembalikan FOREST (1), NON_FOREST (0), atau UNKNOWN (NoData / di luar cakupan).
    """
    return lookup_forest_extent(lat=latitude, lon=longitude).to_dict()



