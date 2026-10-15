"""
Modul Penyimpanan dan Manajemen Pelaporan Masyarakat (Citizen Reports).
Menggunakan SQLite via SQLAlchemy untuk persistensi data laporan, status verifikasi,
dan deteksi duplikasi kejadian.
"""

import enum
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Index,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import REPORTS_DB_PATH

Base = declarative_base()


class ReportCategory(str, enum.Enum):
    FIRE = "kebakaran"  # Kebakaran atau kemunculan asap
    LAND_CLEARING = "pembukaan_lahan"  # Indikasi pembukaan lahan
    FOREST_CHANGE = "perubahan_tutupan"  # Indikasi perubahan kondisi tutupan hutan


class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"  # Menunggu verifikasi
    IN_REVIEW = "IN_REVIEW"  # Perlu pemeriksaan lebih lanjut
    VERIFIED = "VERIFIED"  # Terverifikasi
    REJECTED = "REJECTED"  # Ditolak dengan alasan


class CitizenReportModel(Base):
    """Model tabel SQLite untuk laporan masyarakat."""

    __tablename__ = "citizen_reports"

    id = Column(String(50), primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    province = Column(String(100), nullable=True, index=True)
    observed_at_utc = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    photo_filename = Column(String(255), nullable=True)
    photo_url = Column(String(255), nullable=True)
    reporter_name = Column(String(100), nullable=True)
    reporter_contact = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False, default=ReportStatus.PENDING.value, index=True)
    verification_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    is_duplicate_suspect = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(String(50), nullable=True)
    created_at_utc = Column(String(50), nullable=False)
    updated_at_utc = Column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_category_status", "category", "status"),
        Index("idx_lat_lon", "latitude", "longitude"),
    )

    def to_dict(self, public: bool = True) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "category": self.category,
            "latitude": round(self.latitude, 3) if public else self.latitude,
            "longitude": round(self.longitude, 3) if public else self.longitude,
            "province": self.province,
            "observed_at_utc": self.observed_at_utc,
            "description": self.description,
            "photo_filename": self.photo_filename,
            "photo_url": self.photo_url,
            "reporter_name": self.reporter_name,
            "status": self.status,
            "verification_notes": self.verification_notes,
            "rejection_reason": self.rejection_reason,
            "is_duplicate_suspect": bool(self.is_duplicate_suspect),
            "duplicate_of_id": self.duplicate_of_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }
        if not public:
            data["reporter_contact"] = self.reporter_contact
        return data

    def to_geojson_feature(self, public: bool = True) -> Dict[str, Any]:
        """Konversi ke format GeoJSON Feature untuk dirender pada peta Leaflet."""
        lon = round(self.longitude, 3) if public else self.longitude
        lat = round(self.latitude, 3) if public else self.latitude
        return {
            "type": "Feature",
            "id": self.id,
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": self.id,
                "category": self.category,
                "province": self.province,
                "observed_at_utc": self.observed_at_utc,
                "description": self.description,
                "photo_url": self.photo_url,
                "status": self.status,
                "is_duplicate_suspect": bool(self.is_duplicate_suspect),
                "created_at_utc": self.created_at_utc,
            },
        }



class CitizenReportsRepository:
    """Repository untuk transaksi data pelaporan masyarakat."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or REPORTS_DB_PATH
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def _calculate_haversine_km(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Menghitung jarak geodetik (km) antara 2 titik koordinat."""
        r = 6371.0  # Radius bumi (km)
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def _parse_iso_utc(self, dt_str: str) -> Optional[datetime]:
        try:
            # Standarisasi format Z atau offset
            clean_str = dt_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def check_duplicate_candidate(
        self,
        latitude: float,
        longitude: float,
        category: str,
        observed_at_utc: str,
        max_dist_km: float = 5.0,
        max_time_diff_hours: float = 24.0,
    ) -> Optional[str]:
        """
        Mendeteksi apakah terdapat laporan sebelumnya dengan:
        1. Kategori yang sama
        2. Jarak geospasial <= 5.0 km
        3. Selisih waktu pengamatan <= 24 jam
        Mengembalikan ID laporan pendahulu jika terindikasi duplikat, atau None.
        """
        session = self.SessionLocal()
        try:
            target_dt = self._parse_iso_utc(observed_at_utc)
            # Cek laporan yang tidak berstatus ditolak
            existing_reports = (
                session.query(CitizenReportModel)
                .filter(
                    CitizenReportModel.category == category,
                    CitizenReportModel.status != ReportStatus.REJECTED.value,
                )
                .all()
            )

            for item in existing_reports:
                dist = self._calculate_haversine_km(
                    latitude, longitude, item.latitude, item.longitude
                )
                if dist <= max_dist_km:
                    item_dt = self._parse_iso_utc(item.observed_at_utc)
                    if target_dt and item_dt:
                        diff_hours = abs((target_dt - item_dt).total_seconds()) / 3600.0
                        if diff_hours <= max_time_diff_hours:
                            return item.id
                    else:
                        # Jika parsing gagal, gunakan jarak spasial saja
                        return item.id
            return None
        finally:
            session.close()

    def create_report(
        self,
        category: str,
        latitude: float,
        longitude: float,
        observed_at_utc: str,
        description: str,
        province: Optional[str] = None,
        photo_filename: Optional[str] = None,
        photo_url: Optional[str] = None,
        reporter_name: Optional[str] = None,
        reporter_contact: Optional[str] = None,
        public: bool = True,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Menyimpan laporan warga baru dengan deteksi duplikasi otomatis.
        Mengembalikan tuple: (report_dict, is_duplicate_suspect).
        Jika public=True (default), koordinat dibulatkan ke 3 desimal dan kontak dirahasiakan.
        """
        # Cek apakah terindikasi duplikat
        dup_of_id = self.check_duplicate_candidate(
            latitude=latitude,
            longitude=longitude,
            category=category,
            observed_at_utc=observed_at_utc,
        )
        is_dup = dup_of_id is not None

        now_utc = datetime.now(timezone.utc).isoformat()
        report_id = f"rep_{uuid.uuid4().hex[:12]}"

        report = CitizenReportModel(
            id=report_id,
            category=category,
            latitude=latitude,
            longitude=longitude,
            province=province,
            observed_at_utc=observed_at_utc,
            description=description,
            photo_filename=photo_filename,
            photo_url=photo_url,
            reporter_name=reporter_name,
            reporter_contact=reporter_contact,
            status=ReportStatus.PENDING.value,
            verification_notes=None,
            rejection_reason=None,
            is_duplicate_suspect=is_dup,
            duplicate_of_id=dup_of_id,
            created_at_utc=now_utc,
            updated_at_utc=now_utc,
        )

        session = self.SessionLocal()
        try:
            session.add(report)
            session.commit()
            session.refresh(report)
            return report.to_dict(public=public), is_dup
        finally:
            session.close()

    def get_reports(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        province: Optional[str] = None,
        limit: int = 200,
        public: bool = True,
    ) -> List[Dict[str, Any]]:
        """Mengambil daftar laporan terurut dari yang terbaru."""
        session = self.SessionLocal()
        try:
            query = session.query(CitizenReportModel)
            if category:
                query = query.filter(CitizenReportModel.category == category)
            if status:
                query = query.filter(CitizenReportModel.status == status)
            if province:
                query = query.filter(
                    CitizenReportModel.province.ilike(f"%{province}%")
                )
            results = (
                query.order_by(desc(CitizenReportModel.created_at_utc))
                .limit(limit)
                .all()
            )
            return [r.to_dict(public=public) for r in results]
        finally:
            session.close()

    def get_report_by_id(
        self, report_id: str, public: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Mengambil detail satu laporan berdasarkan ID."""
        session = self.SessionLocal()
        try:
            report = (
                session.query(CitizenReportModel)
                .filter(CitizenReportModel.id == report_id)
                .first()
            )
            return report.to_dict(public=public) if report else None
        finally:
            session.close()

    def update_verification_status(
        self,
        report_id: str,
        status: str,
        verification_notes: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        public: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Mengubah status verifikasi laporan oleh operator.
        Status valid: PENDING, IN_REVIEW, VERIFIED, REJECTED.
        """
        valid_statuses = [s.value for s in ReportStatus]
        if status not in valid_statuses:
            raise ValueError(
                f"Status '{status}' tidak valid. Pilihan: {valid_statuses}"
            )

        session = self.SessionLocal()
        try:
            report = (
                session.query(CitizenReportModel)
                .filter(CitizenReportModel.id == report_id)
                .first()
            )
            if not report:
                return None

            now_utc = datetime.now(timezone.utc).isoformat()
            report.status = status
            report.updated_at_utc = now_utc

            if verification_notes is not None:
                report.verification_notes = verification_notes
            if rejection_reason is not None:
                report.rejection_reason = rejection_reason

            session.commit()
            session.refresh(report)
            return report.to_dict(public=public)
        finally:
            session.close()


# Singleton repository instance
reports_repo = CitizenReportsRepository()
