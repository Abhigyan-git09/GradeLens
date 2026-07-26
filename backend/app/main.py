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
    intelligence_router,
)
from ml.feature_service import FEATURE_NAMES
from ml.risk_predictor import risk_predictor_service
from ml.trajectory_forecast import trajectory_forecaster_service
from ml.stabilization_service import stabilization_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB tables and ensure model directory exists."""
    init_db()
    settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    import json
    import os
    
    # Auto-seed if database is empty or models are missing
    from scripts.bootstrap import generate_synthetic_data, train_models, ARTIFACTS_DIR
    from app.database import SessionLocal
    from app.models.domain import GradeChangeEvent
    
    db = SessionLocal()
    try:
        events = db.query(GradeChangeEvent).count()
        metrics_path = os.path.join(ARTIFACTS_DIR, "metrics.json")
        artifacts_exist = (
            os.path.exists(os.path.join(ARTIFACTS_DIR, "risk_model.joblib"))
            and all(
                os.path.exists(
                    os.path.join(ARTIFACTS_DIR, f"trajectory_{h}s.joblib")
                )
                for h in settings.PREDICTION_HORIZONS
            )
            and os.path.exists(
                os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib")
            )
            and os.path.exists(metrics_path)
        )
        feature_schema_matches = False
        if artifacts_exist:
            with open(metrics_path, encoding="utf-8") as metrics_file:
                metrics = json.load(metrics_file)
            feature_schema_matches = (
                metrics.get("dataset", {}).get("feature_count")
                == len(FEATURE_NAMES)
            )
        
        if events == 0 or not artifacts_exist or not feature_schema_matches:
            print("Auto-seeding database and training models on startup...")
            generate_synthetic_data(db, force_reset=events > 0)
            train_models(db)
            print("Auto-seed complete.")
        risk_predictor_service.reload_model()
        trajectory_forecaster_service.reload_models()
        stabilization_service.reload_model()
        from app.services.rootcause_service import rootcause_service
        rootcause_service.reload_model()
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
app.include_router(intelligence_router)

# Stub routers will be added as we build each phase:
# app.include_router(grade_changes.router)
# app.include_router(predictions.router)
# app.include_router(recommendations.router)
# app.include_router(correlations.router)
# app.include_router(audit.router)
