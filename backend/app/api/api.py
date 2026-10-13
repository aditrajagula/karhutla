from fastapi import APIRouter
from app.api.endpoints import hotspots, boundaries, status

api_router = APIRouter()
api_router.include_router(hotspots.router, prefix="/hotspots", tags=["Hotspots"])
api_router.include_router(boundaries.router, prefix="/boundaries", tags=["Boundaries"])
api_router.include_router(status.router, prefix="/status", tags=["Provenance & Status"])
