"""Health check endpoint."""

from pathlib import Path

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """
    Health check with model mode indicator.
    Returns 'trained' if model artifacts exist, 'degraded' otherwise.
    """
    model_dir = settings.MODEL_DIR
    risk_model_exists = (model_dir / "risk_model.joblib").exists()
    trajectory_models_exist = all(
        (model_dir / f"trajectory_{h}s.joblib").exists()
        for h in settings.PREDICTION_HORIZONS
    )

    if risk_model_exists and trajectory_models_exist:
        model_mode = "trained"
    elif risk_model_exists or trajectory_models_exist:
        model_mode = "partial"
    else:
        model_mode = "degraded"

    return {
        "status": "healthy",
        "model_mode": model_mode,
        "version": "0.1.0",
        "project": "GradeLens",
    }
