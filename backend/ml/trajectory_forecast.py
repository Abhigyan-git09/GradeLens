import os
import joblib
import numpy as np
from typing import Dict, List, Any

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

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
                self.models[h] = joblib.load(path)
                trained_count += 1
        
        if trained_count == len(self.horizons):
            self.is_trained = True

    def forecast(self, features: Dict[str, float]) -> dict:
        """Forecast future basis weight at discrete horizons."""
        results = []
        current_bw = features.get("current_bw", 64.0)
        
        # X: [bw_deviation, bw_slope, stock_flow_ramp]
        X = np.array([[
            features["bw_deviation"],
            features["bw_slope"],
            features["stock_flow_ramp"]
        ]])

        for h in self.horizons:
            if self.is_trained and h in self.models:
                delta = float(self.models[h].predict(X)[0])
            else:
                # Degraded fallback: linear extrapolation based on slope
                delta = features["bw_slope"] * h
                # Dampen it over time
                delta = delta * (0.8 if h > 60 else 1.0)
                
            pred_bw = current_bw + delta
            
            # Uncertainty widens with time horizon
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
