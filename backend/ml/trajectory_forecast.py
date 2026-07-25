import os
import joblib
import numpy as np
from typing import Dict, List, Any
from ml.feature_service import FEATURE_NAMES

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

# Trajectory models use all 7 features
TRAJ_FEATURE_NAMES = FEATURE_NAMES

class TrajectoryForecaster:
    def __init__(self):
        self.horizons = [30, 60, 120]
        self.models = {}
        self.is_trained = False
        self._load_models()

    def _load_models(self):
        trained_count = 0
        for h in self.horizons:
            path = os.path.join(MODEL_DIR, f"trajectory_{h}s.joblib")
            if os.path.exists(path):
                try:
                    self.models[h] = joblib.load(path)
                    trained_count += 1
                except Exception:
                    pass
        if trained_count == len(self.horizons):
            self.is_trained = True

    def forecast(self, features: Dict[str, float]) -> dict:
        """Forecast future basis weight at discrete horizons."""
        results = []
        current_bw = features.get("current_bw", 64.0)

        X = np.array([[features.get(f, 0.0) for f in TRAJ_FEATURE_NAMES]])

        for h in self.horizons:
            if self.is_trained and h in self.models:
                delta = float(self.models[h].predict(X)[0])
            else:
                # Degraded fallback: linear extrapolation based on slope
                delta = features.get("bw_slope", 0.0) * h
                delta = delta * (0.8 if h > 60 else 1.0)

            pred_bw = current_bw + delta
            uncertainty = 0.2 + (h / 100.0) * 0.4

            results.append({
                "seconds": h,
                "predicted_bw": round(pred_bw, 2),
                "lower_bound": round(pred_bw - uncertainty, 2),
                "upper_bound": round(pred_bw + uncertainty, 2)
            })

        return {
            "horizons": results,
            "model_mode": "trained" if self.is_trained else "degraded"
        }

trajectory_forecaster_service = TrajectoryForecaster()
