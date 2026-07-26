"""Liveness, readiness, and operational health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.runtime import (
    database_is_ready,
    inspect_model_artifacts,
    model_services_ready,
)

router = APIRouter(tags=["health"])


def _health_payload(request: Request) -> dict:
    artifacts = inspect_model_artifacts()
    database_ready = database_is_ready()
    services_ready = model_services_ready()
    startup_ready = bool(getattr(request.app.state, "ready", False))
    ready = (
        startup_ready
        and artifacts["ready"]
        and database_ready
        and services_ready
    )
    return {
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "model_mode": "trained" if services_ready else "degraded",
        "database_ready": database_ready,
        "version": settings.APP_VERSION,
        "project": "GradeLens",
        "environment": settings.ENVIRONMENT,
        "metrics": artifacts["metrics"],
    }


@router.get("/health")
def health_check(request: Request):
    """Compatibility health endpoint used by the dashboard."""
    return _health_payload(request)


@router.get("/health/live")
def liveness_check():
    """Return process liveness without checking downstream dependencies."""
    return {
        "status": "alive",
        "version": settings.APP_VERSION,
        "project": "GradeLens",
    }


@router.get("/health/ready")
def readiness_check(request: Request):
    """Return 503 until database and packaged models are ready."""
    payload = _health_payload(request)
    if not payload["ready"]:
        startup_error = getattr(request.app.state, "startup_error", None)
        if startup_error and settings.ENVIRONMENT != "production":
            payload["startup_error"] = startup_error
        return JSONResponse(status_code=503, content=payload)
    return payload
