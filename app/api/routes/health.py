from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", app=get_settings().app_name)


@router.get("/ready", response_model=HealthResponse)
def readiness_check() -> HealthResponse:
    return HealthResponse(status="ready", app=get_settings().app_name)
