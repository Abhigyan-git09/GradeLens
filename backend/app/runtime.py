"""Deterministic startup and readiness checks for GradeLens."""

from __future__ import annotations

import hashlib
import json
import logging
from secrets import compare_digest
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, engine, init_db
from app.models.domain import GradeChangeEvent
from ml.feature_service import FEATURE_NAMES
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service
from ml.trajectory_forecast import trajectory_forecaster_service

logger = logging.getLogger(__name__)


def required_artifact_names() -> list[str]:
    """Return every model artifact required for trained-mode operation."""
    return [
        "risk_model.joblib",
        "stabilization_knn.joblib",
        *(f"trajectory_{horizon}s.joblib" for horizon in settings.PREDICTION_HORIZONS),
        "metrics.json",
        "artifact_manifest.json",
    ]


def inspect_model_artifacts() -> dict[str, Any]:
    """Inspect file presence and feature-schema compatibility."""
    missing = [
        name
        for name in required_artifact_names()
        if not (settings.MODEL_DIR / name).is_file()
    ]
    metrics: dict[str, Any] | None = None
    metrics_error: str | None = None
    metrics_path = settings.MODEL_DIR / "metrics.json"
    if metrics_path.is_file():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            metrics_error = f"metrics.json is unreadable: {exc}"

    feature_count = (
        metrics.get("dataset", {}).get("feature_count")
        if metrics
        else None
    )
    schema_matches = feature_count == len(FEATURE_NAMES)
    if metrics is not None and not schema_matches:
        metrics_error = (
            "Model feature schema mismatch: "
            f"artifact={feature_count}, runtime={len(FEATURE_NAMES)}"
        )

    manifest_error: str | None = None
    manifest_path = settings.MODEL_DIR / "artifact_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("feature_names") != FEATURE_NAMES:
                manifest_error = "Artifact feature names do not match runtime."
            else:
                expected_hashes = manifest.get("sha256", {})
                expected_names = set(required_artifact_names()) - {
                    "artifact_manifest.json"
                }
                if set(expected_hashes) != expected_names:
                    manifest_error = (
                        "Artifact manifest does not cover the required files."
                    )
                else:
                    for name, expected_hash in expected_hashes.items():
                        path = settings.MODEL_DIR / name
                        if not path.is_file():
                            manifest_error = (
                                f"Manifest artifact is missing: {name}"
                            )
                            break
                        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                        if not compare_digest(actual_hash, str(expected_hash)):
                            manifest_error = (
                                f"Artifact checksum validation failed: {name}"
                            )
                            break
        except (OSError, json.JSONDecodeError) as exc:
            manifest_error = f"artifact_manifest.json is unreadable: {exc}"

    return {
        "ready": (
            not missing
            and metrics_error is None
            and manifest_error is None
            and schema_matches
        ),
        "missing": missing,
        "metrics_error": metrics_error,
        "manifest_error": manifest_error,
        "feature_count": feature_count,
        "runtime_feature_count": len(FEATURE_NAMES),
        "metrics": metrics,
    }


def model_services_ready() -> bool:
    """Return whether every in-memory inference service loaded successfully."""
    from app.services.rootcause_service import rootcause_service

    return bool(
        risk_predictor_service.is_trained
        and trajectory_forecaster_service.is_trained
        and stabilization_service.is_trained
        and rootcause_service.model is not None
    )


def reload_model_services() -> None:
    """Reload all packaged artifacts into their inference services."""
    from app.services.rootcause_service import rootcause_service

    risk_predictor_service.reload_model()
    trajectory_forecaster_service.reload_models()
    stabilization_service.reload_model()
    rootcause_service.reload_model()


def database_is_ready() -> bool:
    """Perform a minimal database connectivity check."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database readiness check failed")
        return False
    finally:
        db.close()


def initialize_runtime() -> dict[str, Any]:
    """Initialize storage, seed optional demo data, and load artifacts.

    Model training is never implicit in production unless explicitly enabled.
    Any failure is surfaced to the application lifespan, where strict mode can
    prevent a misleading partially-ready deployment.
    """
    if (
        settings.ENVIRONMENT == "production"
        and len(settings.WRITE_API_KEY) < 32
    ):
        raise RuntimeError(
            "GRADELENS_WRITE_API_KEY must contain at least 32 characters "
            "in production."
        )

    init_db()
    db = SessionLocal()
    try:
        event_count = db.query(GradeChangeEvent).count()
        if event_count == 0:
            if not settings.SEED_DEMO_DATA_IF_EMPTY:
                raise RuntimeError(
                    "Database is empty and demo-data seeding is disabled."
                )
            logger.info("Seeding the empty database with demonstration data")
            from scripts.bootstrap import generate_synthetic_data

            generate_synthetic_data(db)
            event_count = db.query(GradeChangeEvent).count()
    finally:
        db.close()

    artifact_status = inspect_model_artifacts()
    trained_during_startup = False
    if not artifact_status["ready"]:
        if not settings.TRAIN_MODELS_ON_STARTUP:
            details = (
                artifact_status["metrics_error"]
                or artifact_status["manifest_error"]
                or ("missing " + ", ".join(artifact_status["missing"]))
            )
            raise RuntimeError(
                "Required packaged model artifacts are unavailable: "
                f"{details}"
            )
        logger.warning(
            "Artifacts are unavailable or incompatible; training is enabled"
        )
        from scripts.bootstrap import train_models

        db = SessionLocal()
        try:
            train_models(db)
            trained_during_startup = True
        finally:
            db.close()
        artifact_status = inspect_model_artifacts()

    reload_model_services()
    if not artifact_status["ready"] or not model_services_ready():
        raise RuntimeError(
            "Model artifacts exist but one or more inference services "
            "could not load them."
        )
    if not database_is_ready():
        raise RuntimeError("Database connectivity check failed.")

    return {
        "ready": True,
        "environment": settings.ENVIRONMENT,
        "event_count": event_count,
        "model_mode": "trained",
        "trained_during_startup": trained_during_startup,
        "database_dialect": engine.dialect.name,
    }
