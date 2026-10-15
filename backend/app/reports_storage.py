"""
Modul Penyimpanan dan Manajemen Pelaporan Masyarakat (Citizen Reports).
Menggunakan SQLite via SQLAlchemy untuk persistensi data laporan, status verifikasi,
dan deteksi duplikasi kejadian.
"""

import enum
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    desc,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import REPORTS_DB_PATH

Base = declarative_base()


class ReportCategory(str, enum.Enum):
    FIRE = "kebakaran"  # Legacy category
    FIRE_SMOKE = "asap_kebakaran"
    LAND_CLEARING = "pembukaan_lahan"  # Legacy category
    DEFORESTATION = "deforestasi"
    FOREST_CHANGE = "perubahan_tutupan"  # Legacy category
    POST_FIRE_LAND_USE = "alih_fungsi_bekas_karhutla"
    OTHER = "lainnya"


class ReportStatus(str, enum.Enum):
    PENDING = "menunggu_validasi"
    CITIZEN_VALIDATED = "riwayat_kebakaran_validasi_warga"
    IN_REVIEW = "perlu_tinjauan_lapangan"
    VERIFIED = "terverifikasi_petugas"
    REJECTED = "ditolak"


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(32), nullable=False, unique=True, index=True)
    email = Column(String(254), nullable=True, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="aktif")
    created_at_utc = Column(String(50), nullable=False)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "status": self.status,
            "created_at_utc": self.created_at_utc,
        }


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at_utc = Column(String(50), nullable=False, index=True)
    created_at_utc = Column(String(50), nullable=False)


class ReportValidationModel(Base):
    __tablename__ = "report_validations"
    __table_args__ = (UniqueConstraint("report_id", "validator_id"),)

    id = Column(String(36), primary_key=True)
    report_id = Column(String(50), ForeignKey("citizen_reports.id"), nullable=False, index=True)
    validator_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    validator_role = Column(String(16), nullable=False)
    action = Column(String(40), nullable=False)
    reason = Column(Text, nullable=True)
    created_at_utc = Column(String(50), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "validator_id": self.validator_id,
            "validator_role": self.validator_role,
            "action": self.action,
            "reason": self.reason,
            "created_at_utc": self.created_at_utc,
        }


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(60), nullable=False, index=True)
    target_report_id = Column(String(50), nullable=True, index=True)
    details_json = Column(Text, nullable=False, default="{}")
    created_at_utc = Column(String(50), nullable=False, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "action": self.action,
            "target_report_id": self.target_report_id,
            "details": json.loads(self.details_json),
            "created_at_utc": self.created_at_utc,
        }


class AlertSettingModel(Base):
    __tablename__ = "alert_settings"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    radius_m = Column(Float, nullable=False, default=3000)
    updated_at_utc = Column(String(50), nullable=False)


class CitizenReportModel(Base):
    """Model tabel SQLite untuk laporan masyarakat."""

    __tablename__ = "citizen_reports"

    id = Column(String(50), primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    province = Column(String(100), nullable=True, index=True)
    observed_at_utc = Column(String(50), nullable=False)
    location_method = Column(String(16), nullable=True)
    accuracy_m = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    photo_filename = Column(String(255), nullable=True)
    photo_url = Column(String(255), nullable=True)
    reporter_name = Column(String(100), nullable=True)
    reporter_contact = Column(String(100), nullable=True)
    reporter_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default=ReportStatus.PENDING.value, index=True)
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
            "status": self.status,
            "verification_notes": self.verification_notes,
            "rejection_reason": self.rejection_reason,
            "is_duplicate_suspect": bool(self.is_duplicate_suspect),
            "duplicate_of_id": self.duplicate_of_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }
        if not public:
            data["reporter_name"] = self.reporter_name
            data["reporter_contact"] = self.reporter_contact
            data["reporter_id"] = self.reporter_id
            data["location_method"] = self.location_method
            data["accuracy_m"] = self.accuracy_m
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
        self._migrate_report_owner_column()
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def _migrate_report_owner_column(self) -> None:
        columns = {
            column["name"]
            for column in inspect(self.engine).get_columns("citizen_reports")
        }
        if "reporter_id" not in columns:
            with self.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE citizen_reports ADD COLUMN reporter_id VARCHAR(36)")
                )
        migrations = {
            "location_method": "VARCHAR(16)",
            "accuracy_m": "FLOAT",
        }
        for column_name, column_type in migrations.items():
            if column_name not in columns:
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            f"ALTER TABLE citizen_reports ADD COLUMN {column_name} {column_type}"
                        )
                    )
        legacy_statuses = {
            "PENDING": ReportStatus.PENDING.value,
            "IN_REVIEW": ReportStatus.IN_REVIEW.value,
            "VERIFIED": ReportStatus.VERIFIED.value,
            "REJECTED": ReportStatus.REJECTED.value,
        }
        with self.engine.begin() as connection:
            for old_status, new_status in legacy_statuses.items():
                connection.execute(
                    text(
                        "UPDATE citizen_reports SET status = :new_status "
                        "WHERE status = :old_status"
                    ),
                    {"old_status": old_status, "new_status": new_status},
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
        location_method: Optional[str] = None,
        accuracy_m: Optional[float] = None,
        province: Optional[str] = None,
        photo_filename: Optional[str] = None,
        photo_url: Optional[str] = None,
        reporter_name: Optional[str] = None,
        reporter_contact: Optional[str] = None,
        reporter_id: Optional[str] = None,
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
            reporter_id=reporter_id,
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
        reporter_id: Optional[str] = None,
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
            if reporter_id:
                query = query.filter(CitizenReportModel.reporter_id == reporter_id)
            elif not status:
                query = query.filter(
                    CitizenReportModel.status != ReportStatus.REJECTED.value
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

    def validate_report_by_citizen(
        self, report_id: str, validator_id: str
    ) -> Optional[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            report = session.query(CitizenReportModel).filter_by(id=report_id).first()
            if not report:
                return None
            if report.reporter_id == validator_id:
                raise ValueError("Pemilik laporan tidak dapat memvalidasi laporannya sendiri.")
            if report.status != ReportStatus.PENDING.value:
                raise ValueError("Laporan ini tidak lagi menunggu validasi warga.")

            validation = ReportValidationModel(
                id=str(uuid.uuid4()),
                report_id=report_id,
                validator_id=validator_id,
                validator_role="warga",
                action="validasi_warga",
                created_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            session.add(validation)
            report.status = ReportStatus.CITIZEN_VALIDATED.value
            report.updated_at_utc = datetime.now(timezone.utc).isoformat()
            session.commit()
            session.refresh(report)
            return report.to_dict(public=False)
        except IntegrityError as exc:
            session.rollback()
            raise ValueError("Anda sudah memvalidasi laporan ini.") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_report_validations(self, report_id: str) -> List[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            records = (
                session.query(ReportValidationModel)
                .filter_by(report_id=report_id)
                .order_by(ReportValidationModel.created_at_utc)
                .all()
            )
            return [record.to_dict() for record in records]
        finally:
            session.close()

    def get_nearby_reports(
        self, latitude: float, longitude: float, radius_km: float
    ) -> List[Tuple[Dict[str, Any], float]]:
        session = self.SessionLocal()
        try:
            reports = (
                session.query(CitizenReportModel)
                .filter(CitizenReportModel.status != ReportStatus.REJECTED.value)
                .order_by(desc(CitizenReportModel.created_at_utc))
                .all()
            )
            nearby = []
            for report in reports:
                distance = self._calculate_haversine_km(
                    latitude, longitude, report.latitude, report.longitude
                )
                if distance <= radius_km:
                    nearby.append((report.to_dict(public=True), distance))
            return nearby
        finally:
            session.close()

    def write_audit_log(
        self,
        action: str,
        actor_user_id: Optional[str] = None,
        target_report_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        session = self.SessionLocal()
        try:
            event = AuditLogModel(
                id=str(uuid.uuid4()),
                actor_user_id=actor_user_id,
                action=action,
                target_report_id=target_report_id,
                details_json=json.dumps(details or {}, separators=(",", ":")),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            session.add(event)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_report_audit_logs(self, report_id: str) -> List[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            events = (
                session.query(AuditLogModel)
                .filter_by(target_report_id=report_id)
                .order_by(AuditLogModel.created_at_utc)
                .all()
            )
            return [event.to_dict() for event in events]
        finally:
            session.close()

    def get_alert_setting(self, user_id: str) -> Dict[str, Any]:
        session = self.SessionLocal()
        try:
            setting = session.query(AlertSettingModel).filter_by(user_id=user_id).first()
            if not setting:
                return {"enabled": False, "radius_m": 3000, "updated_at_utc": None}
            return {
                "enabled": bool(setting.enabled),
                "radius_m": int(setting.radius_m),
                "updated_at_utc": setting.updated_at_utc,
            }
        finally:
            session.close()

    def save_alert_setting(
        self, user_id: str, enabled: bool, radius_m: int
    ) -> Dict[str, Any]:
        session = self.SessionLocal()
        try:
            setting = session.query(AlertSettingModel).filter_by(user_id=user_id).first()
            now = datetime.now(timezone.utc).isoformat()
            if setting is None:
                setting = AlertSettingModel(
                    user_id=user_id,
                    enabled=enabled,
                    radius_m=radius_m,
                    updated_at_utc=now,
                )
                session.add(setting)
            else:
                setting.enabled = enabled
                setting.radius_m = radius_m
                setting.updated_at_utc = now
            session.commit()
            return {
                "enabled": bool(setting.enabled),
                "radius_m": int(setting.radius_m),
                "updated_at_utc": setting.updated_at_utc,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Singleton repository instance
reports_repo = CitizenReportsRepository()
