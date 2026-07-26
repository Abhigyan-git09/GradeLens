import joblib
import numpy as np
from typing import Dict, Any
from app.config import settings
from ml.feature_service import FEATURE_NAMES

class StabilizationService:
    def __init__(self):
        self.model_path = settings.MODEL_DIR / "stabilization_knn.joblib"
        self.model = None
        self.neighbor_model = None
        self.neighbor_count = 0
        self.regressor_weight = 0.8
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        self.model = None
        self.neighbor_model = None
        self.neighbor_count = 0
        self.regressor_weight = 0.8
        self.is_trained = False
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
                if isinstance(artifact, dict):
                    self.model = artifact["regressor"]
                    self.neighbor_model = artifact.get("neighbors")
                    self.neighbor_count = int(
                        artifact.get("neighbor_count", 0)
                    )
                    self.regressor_weight = min(
                        1.0,
                        max(
                            0.0,
                            float(artifact.get("regressor_weight", 0.8)),
                        ),
                    )
                else:
                    self.model = artifact
                self.is_trained = True
            except Exception:
                pass

    def reload_model(self):
        self._load_model()

    def estimate_stabilization(self, features: Dict[str, float]) -> dict:
        """Estimate remaining stabilization time with a validated hybrid."""
        X = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

        if not self.is_trained:
            # Fallback degraded logic
            fallback_time = max(0.0, abs(features.get("bw_deviation", 0.0)) * 100.0)
            return {
                "estimated_seconds": fallback_time,
                "similar_events_used": 0,
                "model_mode": "degraded"
            }

        # Predict time directly from KNN Regressor
        est_time = float(self.model.predict(X)[0])
        if self.neighbor_model is not None:
            neighbor_time = float(self.neighbor_model.predict(X)[0])
            est_time = (
                self.regressor_weight * est_time
                + (1.0 - self.regressor_weight) * neighbor_time
            )
        
        return {
            "estimated_seconds": max(0.0, round(est_time, 1)),
            "similar_events_used": (
                self.neighbor_count if self.regressor_weight < 1.0 else 0
            ),
            "model_mode": "trained"
        }

stabilization_service = StabilizationService()
