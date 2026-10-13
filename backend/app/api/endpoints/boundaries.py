from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()


@router.get("/")
def get_boundaries(
    category: str = Query("administrative", description="Kategori layer: 'administrative', 'peatland', atau 'forest'"),
    province_id: Optional[str] = Query(None, description="Filter provinsi tertentu"),
):
    """
    Mengambil layer poligon geospasial (batas administratif, gambut, atau tutupan hutan).
    Layer hutan dan gambut berfungsi sebagai konteks kedekatan spasial, bukan bukti deforestasi otomatis.
    """
    return {
        "category": category,
        "type": "FeatureCollection",
        "features": [],
        "message": "Endpoint siap untuk integrasi layer spasial PostGIS",
    }
