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
from app.routers import (
    health_router,
    grade_changes_router,
    predictions_router,
    recommendations_router,
    stretch_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB tables and ensure model directory exists."""
    init_db()
    settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    import sys
    import os
    from pathlib import Path
    
    # Auto-seed if database is empty or models are missing
    from scripts.bootstrap import generate_synthetic_data, train_models, ARTIFACTS_DIR
    from app.database import SessionLocal
    from app.models.domain import GradeChangeEvent
    
    db = SessionLocal()
    try:
        events = db.query(GradeChangeEvent).count()
        artifacts_exist = (
            os.path.exists(os.path.join(ARTIFACTS_DIR, "risk_model.txt")) and
            os.path.exists(os.path.join(ARTIFACTS_DIR, "trajectory_30s.joblib")) and
            os.path.exists(os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib"))
        )
        
        if events == 0 or not artifacts_exist:
            print("Auto-seeding database and training models on startup...")
            generate_synthetic_data(db, force_reset=False)
            train_models(db)
            print("Auto-seed complete.")
    except Exception as e:
        print(f"Error during auto-seed: {e}")
    finally:
        db.close()

    yield


app = FastAPI(
    title="GradeLens API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(grade_changes_router)
app.include_router(predictions_router)
app.include_router(recommendations_router)
app.include_router(stretch_router)

# Stub routers will be added as we build each phase:
# app.include_router(grade_changes.router)
# app.include_router(predictions.router)
# app.include_router(recommendations.router)
# app.include_router(correlations.router)
# app.include_router(audit.router)
