from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.schemas.hotspot import HotspotListResponse, Hotspot
from app.services.firms import get_hotspots_data

router = APIRouter()


@router.get("/", response_model=HotspotListResponse)
def get_hotspots(
    start_date: Optional[str] = Query(None, description="Tanggal mulai observasi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Tanggal selesai observasi (YYYY-MM-DD)"),
    mode: str = Query("auto", description="Mode data: 'auto', 'live', atau 'snapshot'"),
    day_range: int = Query(2, ge=1, le=10, description="Rentang hari deteksi FIRMS (1-10)"),
    confidence: Optional[str] = Query(None, description="Filter tingkat confidence: 'low', 'nominal', 'high'"),
    limit: int = Query(3000, ge=1, le=10000, description="Maksimum jumlah titik yang dikembalikan"),
):
    """
    Mengambil data deteksi hotspot (anomali termal satelit VIIRS).
    Otomatis fallback ke snapshot lokal 7 hari jika API FIRMS mengalami kendala.
    """
    resolved_mode, records, sync_time, err_msg = get_hotspots_data(
        mode=mode,
        day_range=day_range,
    )

    # Filter tanggal jika disediakan
    filtered = records
    if start_date:
        filtered = [h for h in filtered if h.acq_date >= start_date]
    if end_date:
        filtered = [h for h in filtered if h.acq_date <= end_date]
    if confidence:
        filtered = [h for h in filtered if h.confidence == confidence]

    # Batasi jumlah record untuk responsivitas UI peta
    paged_records = filtered[:limit]

    return HotspotListResponse(
        mode=resolved_mode,
        count=len(filtered),
        last_sync_utc=sync_time,
        records=paged_records,
        message=err_msg,
    )


@router.get("/{hotspot_id}")
def get_hotspot_detail(hotspot_id: str):
    """
    Mengambil detail spesifik satu titik anomali termal beserta provenance sumber.
    """
    _, records, sync_time, _ = get_hotspots_data(mode="auto", day_range=3)
    for h in records:
        if h.id == hotspot_id:
            return {
                "hotspot": h,
                "sync_time_utc": sync_time,
                "disclaimer": "Anomali termal adalah indikasi sensor satelit untuk ditinjau lapangan, bukan konfirmasi pasti kebakaran.",
            }

    raise HTTPException(status_code=404, detail="Titik anomali termal tidak ditemukan.")
