"""
GradeLens — FastAPI Application Entry Point.

An explainable advisory layer that predicts Basis Weight spec risk
during automatic grade changes in paper manufacturing.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB tables and ensure model directory exists."""
    init_db()
    settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="GradeLens API",
    description=(
        "Grade Change Intelligence — predicts Basis Weight spec risk, "
        "explains root causes, and recommends corrective setpoints."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)

# Stub routers will be added as we build each phase:
# app.include_router(grade_changes.router)
# app.include_router(predictions.router)
# app.include_router(recommendations.router)
# app.include_router(correlations.router)
# app.include_router(audit.router)
