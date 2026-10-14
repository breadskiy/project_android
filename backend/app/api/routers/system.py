"""Service endpoints: root, health, liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.errors import error_body
from app.config import settings
from app.core.security import utcnow
from app.db.pool import aping, pool_stats
from app.schemas.common import ErrorResponse, HealthResponse, ReadinessResponse

router = APIRouter(tags=["system"])


@router.get("/", summary="Информация об API")
async def root() -> dict[str, str]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Состояние сервиса и базы данных",
)
async def health() -> HealthResponse:
    try:
        db_ok = await aping()
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="ok" if db_ok else "unavailable",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        ai_suggestions=settings.AI_SUGGESTIONS_ENABLED,
        llm_configured=settings.llm_configured,
        time=utcnow(),
    )


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"model": ErrorResponse, "description": "База данных недоступна"}},
)
async def readiness() -> JSONResponse:
    """503 while the database is unreachable, so orchestrators hold traffic."""
    try:
        ready = await aping()
    except Exception:
        ready = False

    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_body("service_unavailable", "База данных недоступна"),
        )
    return JSONResponse(content={"status": "ready", "pool": pool_stats()})
