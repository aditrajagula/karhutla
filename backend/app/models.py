"""
Model Data dan Skema Serialisasi (Pydantic).
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HotspotRecord(BaseModel):
    """
    Representasi satu rekaman anomali termal / hotspot tervalidasi.
    Atribut opsional yang kosong bernilai None (tanpa nilai tebakan).
    """
    latitude: float = Field(..., description="Latitude dalam rentang -90 hingga 90")
    longitude: float = Field(..., description="Longitude dalam rentang -180 hingga 180")
    acq_date: str = Field(..., description="Tanggal observasi satelit YYYY-MM-DD")
    acq_time: str = Field(..., description="Waktu observasi satelit HHMM UTC")
    observation_time_utc: str = Field(..., description="Timestamp standar ISO-8601 UTC")
    satellite: Optional[str] = Field(None, description="Kode identitas satelit (misal 20, 21, N)")
    instrument: Optional[str] = Field(None, description="Sensor satelit (misal VIIRS)")
    confidence: Optional[str] = Field(None, description="Tingkat kepercayaan mentah (l/n/h)")
    version: Optional[str] = Field(None, description="Versi algoritma/NRT")
    bright_ti4: Optional[float] = Field(None, description="Brightness temperature I-4 (Kelvin)")
    bright_ti5: Optional[float] = Field(None, description="Brightness temperature I-5 (Kelvin)")
    frp: Optional[float] = Field(None, description="Fire Radiative Power (MW)")
    daynight: Optional[str] = Field(None, description="Deteksi siang (D) atau malam (N)")
    province: Optional[str] = Field(None, description="Konteks nama provinsi hasil filter poligon")

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Konversi rekaman menjadi GeoJSON Feature standar (RFC 7946)."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                "observation_time_utc": self.observation_time_utc,
                "acq_date": self.acq_date,
                "acq_time": self.acq_time,
                "satellite": self.satellite,
                "instrument": self.instrument,
                "confidence": self.confidence,
                "version": self.version,
                "bright_ti4": self.bright_ti4,
                "bright_ti5": self.bright_ti5,
                "frp": self.frp,
                "daynight": self.daynight,
                "province": self.province
            }
        }


class RejectionStats(BaseModel):
    """Statistik audit kualitas dan penolakan rekaman."""
    total_initial_records: int = 0
    total_valid_records: int = 0
    total_rejected_records: int = 0
    reasons: Dict[str, int] = Field(default_factory=dict)


class ProvenanceMeta(BaseModel):
    """Metadata asal-usul data dan pembedaan dimensi waktu."""
    data_source: str = Field(..., description="NASA_FIRMS_API atau LOCAL_TEAM_SNAPSHOT")
    status: str = Field("NO_DATA_AVAILABLE", description="LIVE_API, FALLBACK_LOCAL_SNAPSHOT, atau NO_DATA_AVAILABLE")
    sensor_product: str = Field(..., description="Produk sensor, misal VJ114IMGTDL_NRT")
    is_snapshot: bool = Field(..., description="True jika data berasal dari snapshot lokal")
    snapshot_type: Optional[str] = Field(None, description="TEAM_LOCAL_CAPTURE atau NONE")
    fetched_at_utc: Optional[str] = Field(None, description="Waktu pengambilan data dari sumber")
    processed_at_utc: str = Field(..., description="Waktu pemrosesan pipeline")
    observation_date_range: Dict[str, Optional[str]] = Field(default_factory=dict)
    query_parameters: Dict[str, Any] = Field(default_factory=dict)
    audit_stats: RejectionStats = Field(default_factory=RejectionStats)
    status_message: str = Field(..., description="Penjelasan status untuk antarmuka pengguna")


class SnapshotManifest(BaseModel):
    """Manifest integritas dan provenance untuk snapshot lokal tim."""
    snapshot_filename: str
    snapshot_type: str = "TEAM_LOCAL_CAPTURE"
    label: str = "Snapshot Hasil Pengambilan Mandiri Tim (Bukan Benchmark Panitia)"
    fetched_at_utc: str
    source: str
    sensor_product: str
    observation_date_range: Dict[str, Optional[str]]
    query_parameters: Dict[str, Any]
    record_count: int
    checksum_sha256: str
