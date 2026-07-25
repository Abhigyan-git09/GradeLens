import os
import joblib
import numpy as np
from typing import Dict, Any

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

class StabilizationService:
    def __init__(self):
        self.model_path = os.path.join(MODEL_DIR, "stabilization_knn.joblib")
        self.model = None
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_trained = True

    def estimate_stabilization(self, features: Dict[str, float]) -> dict:
        """Estimate remaining stabilization time using k-NN."""
        X = np.array([[
            features["bw_deviation"],
            abs(features["bw_slope"]),
            abs(features["stock_flow_ramp"])
        ]])

        if not self.is_trained:
            # Fallback degraded logic
            fallback_time = max(0.0, abs(features["bw_deviation"]) * 100.0)
            return {
                "estimated_seconds": fallback_time,
                "similar_events_used": 0,
                "model_mode": "degraded"
            }

        # Predict time directly from KNN Regressor
        est_time = float(self.model.predict(X)[0])
        
        return {
            "estimated_seconds": max(0.0, round(est_time, 1)),
            "similar_events_used": 3,
            "model_mode": "trained"
        }

stabilization_service = StabilizationService()
