from typing import List, Optional
from pydantic import BaseModel, Field


class Hotspot(BaseModel):
    id: str
    latitude: float
    longitude: float
    acq_date: str
    acq_time: str
    satellite: str
    instrument: str
    confidence: str
    frp: Optional[float] = None
    daynight: str = Field(default="D")
    source_provenance: str


class HotspotListResponse(BaseModel):
    mode: str
    count: int
    last_sync_utc: Optional[str] = None
    records: List[Hotspot]
    message: Optional[str] = None

