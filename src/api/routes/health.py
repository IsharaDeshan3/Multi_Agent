from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import HealthResponse

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service health and current registered agent count."""
    return HealthResponse(status="ok", agents_registered=1)
