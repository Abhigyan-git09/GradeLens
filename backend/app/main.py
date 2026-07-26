"""GradeLens FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    grade_changes_router,
    health_router,
    intelligence_router,
    predictions_router,
    recommendations_router,
    stretch_router,
)
from app.runtime import initialize_runtime
from app.security import RequestSafetyMiddleware, WRITE_KEY_HEADER

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize deterministic runtime dependencies before serving traffic."""
    app.state.ready = False
    app.state.startup_error = None
    app.state.runtime = {}
    try:
        app.state.runtime = initialize_runtime()
        app.state.ready = True
        logger.info(
            "GradeLens ready: environment=%s events=%s model_mode=%s",
            app.state.runtime["environment"],
            app.state.runtime["event_count"],
            app.state.runtime["model_mode"],
        )
    except Exception as exc:
        app.state.startup_error = str(exc)
        logger.exception("GradeLens startup validation failed")
        if settings.STRICT_STARTUP:
            raise

    yield


app = FastAPI(
    title="GradeLens API",
    description=(
        "Explainable, constrained grade-change risk and recommendation API."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_middleware(RequestSafetyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", WRITE_KEY_HEADER],
)

app.include_router(health_router)
app.include_router(grade_changes_router)
app.include_router(predictions_router)
app.include_router(recommendations_router)
app.include_router(stretch_router)
app.include_router(intelligence_router)
