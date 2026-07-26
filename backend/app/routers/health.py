"""Health check endpoint."""

import json

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
    stabilization_model_exists = (
        model_dir / "stabilization_knn.joblib"
    ).exists()

    if (
        risk_model_exists
        and trajectory_models_exist
        and stabilization_model_exists
    ):
        model_mode = "trained"
    elif (
        risk_model_exists
        or trajectory_models_exist
        or stabilization_model_exists
    ):
        model_mode = "partial"
    else:
        model_mode = "degraded"

    metrics = None
    metrics_path = model_dir / "metrics.json"
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metrics = None
    return {
        "status": "healthy",
        "model_mode": model_mode,
        "version": "0.1.0",
        "project": "GradeLens",
        "metrics": metrics,
    }
