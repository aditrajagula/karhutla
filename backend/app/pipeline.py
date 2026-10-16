"""
Pipeline Pengolahan Data Hotspot & Geospasial.
Menghubungkan Ingestion, Validasi, Deduplikasi, Filter Spasial Indonesia,
Penyimpanan Snapshot Lokal Tim, dan Penanganan Fallback.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cleaner import clean_and_deduplicate
from .config import (
    BOUNDARIES_PATH,
    FIRMS_AREA_BBOX,
    FIRMS_DEFAULT_SOURCE,
    FIRMS_MAP_KEY,
    FIRMS_REQUEST_TIMEOUT_SECONDS,
    FORCE_SNAPSHOT_MODE,
    SNAPSHOTS_DIR,
)
from .firms_client import FirmsAPIError, FirmsClient
from .models import HotspotRecord, ProvenanceMeta, RejectionStats
from .snapshot_manager import (
    find_latest_valid_snapshot,
    parse_csv_content,
    save_team_snapshot,
)
from .spatial_filter import IndonesiaSpatialFilter

STRICT_KALIMANTAN_CSV_PATH = Path(__file__).with_name("firms_kalimantan_STRICT.csv")


class HotspotPipeline:
    """Orkestrator pipeline pemrosesan data hotspot."""

    def __init__(
        self,
        boundaries_path: Path = BOUNDARIES_PATH,
        snapshots_dir: Path = SNAPSHOTS_DIR,
        map_key: str = FIRMS_MAP_KEY,
        default_source: str = FIRMS_DEFAULT_SOURCE,
        bbox: str = FIRMS_AREA_BBOX,
        timeout_seconds: int = FIRMS_REQUEST_TIMEOUT_SECONDS,
        strict_kalimantan_csv_path: Path = STRICT_KALIMANTAN_CSV_PATH,
    ):
        self.boundaries_path = Path(boundaries_path)
        self.snapshots_dir = Path(snapshots_dir)
        self.map_key = map_key
        self.default_source = default_source
        self.bbox = bbox
        self.timeout_seconds = timeout_seconds
        self.strict_kalimantan_csv_path = Path(strict_kalimantan_csv_path)

        # Inisialisasi filter spasial (memuat poligon batas Indonesia)
        self.spatial_filter = IndonesiaSpatialFilter(self.boundaries_path)
        self.last_provenance: Optional[Dict[str, Any]] = None

    def run(
        self,
        total_days: int = 7,
        source: Optional[str] = None,
        force_snapshot: bool = FORCE_SNAPSHOT_MODE,
        raw_csv_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Menjalankan pipeline end-to-end.
        Parameter:
            total_days: Rentang hari observasi (default 7)
            source: Sensor FIRMS (default VIIRS NOAA-20)
            force_snapshot: Jika True, lewati API dan langsung baca snapshot tim lokal
            raw_csv_override: Input CSV langsung (berguna untuk pengujian unit/mock)
        """
        active_source = source or self.default_source
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        raw_csv: Optional[str] = None
        data_source_label = "NASA_FIRMS_API"
        is_snapshot = False
        snapshot_type = None
        fetched_at_utc = now_utc
        status_message = "Data berhasil diambil secara live dari NASA FIRMS API."

        # 1. Mode Override (untuk unit test)
        if raw_csv_override is not None:
            raw_csv = raw_csv_override
            data_source_label = "TEST_FIXTURE_STREAM"
            status_message = "Memproses stream data pengujian sintetis (TEST ONLY)."

        # 2. Mode Force Snapshot
        elif force_snapshot:
            if self.strict_kalimantan_csv_path.is_file():
                raw_csv = self.strict_kalimantan_csv_path.read_text(encoding="utf-8-sig")
                data_source_label = "LOCAL_KALIMANTAN_STRICT_CSV"
                is_snapshot = True
                snapshot_type = "KALIMANTAN_STRICT_CSV"
                fetched_at_utc = None
                status_message = (
                    "Menampilkan dataset statis firms_kalimantan_STRICT.csv. "
                    "Waktu pengambilan dataset tidak tersedia."
                )
            else:
                latest = find_latest_valid_snapshot(self.snapshots_dir)
                if latest:
                    csv_path, manifest = latest
                    with open(csv_path, "r", encoding="utf-8") as f:
                        raw_csv = f.read()
                    data_source_label = "LOCAL_TEAM_SNAPSHOT"
                    is_snapshot = True
                    snapshot_type = manifest.snapshot_type
                    fetched_at_utc = manifest.fetched_at_utc
                    active_source = manifest.sensor_product
                    status_message = (
                        f"Mode snapshot aktif. Menampilkan snapshot lokal tim yang diambil pada {fetched_at_utc}."
                    )
                else:
                    return self._build_empty_response(
                        status_message=(
                            "Mode snapshot aktif, tetapi dataset firms_kalimantan_STRICT.csv dan "
                            "snapshot lokal tim tidak tersedia."
                        ),
                        processed_at_utc=now_utc,
                        source=active_source
                    )

        # 3. Mode Live API dengan Fallback
        else:
            if not self.map_key:
                # Kunci API belum diatur -> Coba fallback snapshot
                if self.strict_kalimantan_csv_path.is_file():
                    raw_csv = self.strict_kalimantan_csv_path.read_text(encoding="utf-8-sig")
                    data_source_label = "LOCAL_KALIMANTAN_STRICT_CSV"
                    is_snapshot = True
                    snapshot_type = "KALIMANTAN_STRICT_CSV"
                    fetched_at_utc = None
                    status_message = (
                        "FIRMS_MAP_KEY belum diatur. Menampilkan dataset statis "
                        "firms_kalimantan_STRICT.csv; data ini bukan pemantauan live dan "
                        "waktu pengambilan dataset tidak tersedia."
                    )
                else:
                    latest = find_latest_valid_snapshot(self.snapshots_dir)
                    if latest:
                        csv_path, manifest = latest
                        with open(csv_path, "r", encoding="utf-8") as f:
                            raw_csv = f.read()
                        data_source_label = "LOCAL_TEAM_SNAPSHOT"
                        is_snapshot = True
                        snapshot_type = manifest.snapshot_type
                        fetched_at_utc = manifest.fetched_at_utc
                        active_source = manifest.sensor_product
                        status_message = (
                            "FIRMS_MAP_KEY belum diatur di .env. Menggunakan fallback snapshot lokal tim "
                            f"(diambil pada {fetched_at_utc})."
                        )
                    else:
                        return self._build_empty_response(
                            status_message=(
                                "FIRMS_MAP_KEY belum dikonfigurasi di backend (.env), dan dataset "
                                "firms_kalimantan_STRICT.csv maupun snapshot lokal tim tidak tersedia."
                            ),
                            processed_at_utc=now_utc,
                            source=active_source
                        )
            else:
                # Coba penarikan live via API
                client = FirmsClient(
                    map_key=self.map_key,
                    timeout_seconds=self.timeout_seconds,
                    default_source=active_source,
                    bbox=self.bbox
                )
                try:
                    raw_csv = client.fetch_area_hotspots(
                        source=active_source,
                        total_days=total_days
                    )
                    raw_rows_peek = parse_csv_content(raw_csv)
                    # Hanya simpan snapshot jika data berhasil ditarik dan memiliki rekaman valid
                    # Menjaga snapshot valid yang sudah ada agar tidak tertimpa oleh respons kosong
                    if raw_rows_peek:
                        min_d = min((r.get("acq_date") for r in raw_rows_peek if r.get("acq_date")), default=None)
                        max_d = max((r.get("acq_date") for r in raw_rows_peek if r.get("acq_date")), default=None)
                        save_team_snapshot(
                            raw_csv_content=raw_csv,
                            source="NASA_FIRMS_API",
                            sensor_product=active_source,
                            query_params={"bbox": self.bbox, "total_days": total_days},
                            snapshots_dir=self.snapshots_dir,
                            min_date=min_d,
                            max_date=max_d,
                            record_count=len(raw_rows_peek)
                        )
                except FirmsAPIError as exc:
                    # API gagal -> Coba fallback snapshot
                    if self.strict_kalimantan_csv_path.is_file():
                        raw_csv = self.strict_kalimantan_csv_path.read_text(encoding="utf-8-sig")
                        data_source_label = "LOCAL_KALIMANTAN_STRICT_CSV"
                        is_snapshot = True
                        snapshot_type = "KALIMANTAN_STRICT_CSV"
                        fetched_at_utc = None
                        status_message = (
                            f"Panggilan FIRMS gagal ({exc}). Menampilkan dataset statis "
                            "firms_kalimantan_STRICT.csv; data ini bukan pemantauan live dan "
                            "waktu pengambilan dataset tidak tersedia."
                        )
                    else:
                        latest = find_latest_valid_snapshot(self.snapshots_dir)
                        if latest:
                            csv_path, manifest = latest
                            with open(csv_path, "r", encoding="utf-8") as f:
                                raw_csv = f.read()
                            data_source_label = "LOCAL_TEAM_SNAPSHOT"
                            is_snapshot = True
                            snapshot_type = manifest.snapshot_type
                            fetched_at_utc = manifest.fetched_at_utc
                            active_source = manifest.sensor_product
                            status_message = (
                                f"Panggilan API gagal ({str(exc)}). Menampilkan fallback snapshot lokal tim "
                                f"(diambil pada {fetched_at_utc})."
                            )
                        else:
                            return self._build_empty_response(
                                status_message=(
                                    f"Panggilan API gagal ({str(exc)}) dan tidak tersedia dataset "
                                    "firms_kalimantan_STRICT.csv atau snapshot lokal sebagai fallback."
                                ),
                                processed_at_utc=now_utc,
                                source=active_source
                            )

        # 4. Parsing baris data CSV
        raw_rows = parse_csv_content(raw_csv or "")

        # 5. Pembersihan, Validasi, dan Deduplikasi
        cleaned_records, audit_stats = clean_and_deduplicate(raw_rows)

        # 6. Filter Spasial Indonesia (Point-in-Polygon)
        filtered_records, audit_stats = self.spatial_filter.filter_records(cleaned_records, audit_stats)

        # 7. Rentang tanggal observasi aktual dari data tervalidasi
        obs_dates = [r.acq_date for r in filtered_records if r.acq_date]
        obs_range = {
            "min": min(obs_dates) if obs_dates else None,
            "max": max(obs_dates) if obs_dates else None
        }

        # 8. Metadata Provenance
        if data_source_label == "NASA_FIRMS_API":
            status_label = "LIVE_API"
        elif is_snapshot or data_source_label == "LOCAL_TEAM_SNAPSHOT":
            status_label = "FALLBACK_LOCAL_SNAPSHOT"
        elif data_source_label == "TEST_FIXTURE_STREAM":
            status_label = "TEST_FIXTURE"
        else:
            status_label = "NO_DATA_AVAILABLE"

        provenance = ProvenanceMeta(
            data_source=data_source_label,
            status=status_label,
            sensor_product=active_source,
            is_snapshot=is_snapshot,
            snapshot_type=snapshot_type,
            fetched_at_utc=fetched_at_utc,
            processed_at_utc=now_utc,
            observation_date_range=obs_range,
            query_parameters={"bbox": self.bbox, "total_days": total_days},
            audit_stats=audit_stats,
            status_message=status_message
        )

        # 9. Format GeoJSON FeatureCollection standar (RFC 7946)
        features = [r.to_geojson_feature() for r in filtered_records]
        prov_dict = provenance.model_dump()
        self.last_provenance = prov_dict

        return {
            "type": "FeatureCollection",
            "provenance": prov_dict,
            "features": features
        }

    def _build_empty_response(
        self, status_message: str, processed_at_utc: str, source: str
    ) -> Dict[str, Any]:
        """Menyusun respons kosong dengan pesan status yang jelas ketika data gagal dimuat."""
        provenance = ProvenanceMeta(
            data_source="NONE",
            status="NO_DATA_AVAILABLE",
            sensor_product=source,
            is_snapshot=False,
            snapshot_type=None,
            fetched_at_utc=None,
            processed_at_utc=processed_at_utc,
            observation_date_range={"min": None, "max": None},
            query_parameters={"bbox": self.bbox},
            audit_stats=RejectionStats(),
            status_message=status_message
        )
        prov_dict = provenance.model_dump()
        self.last_provenance = prov_dict
        return {
            "type": "FeatureCollection",
            "provenance": prov_dict,
            "features": []
        }
