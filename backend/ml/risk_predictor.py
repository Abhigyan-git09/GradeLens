import os
import joblib
import numpy as np
import lightgbm as lgb
from typing import Dict, Optional, Any
from ml.feature_service import FEATURE_NAMES

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

class RiskPredictor:
    def __init__(self):
        self.model_path = os.path.join(MODEL_DIR, "risk_model.joblib")
        self.model = None
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
            except Exception:
                self.is_trained = False

    def predict_risk(self, features: Dict[str, float]) -> dict:
        """Predict probability of off-spec within next 120s."""
        X = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

        if not self.is_trained:
            # Fallback degraded mode
            prob = min(0.99, max(0.01, abs(features.get("bw_deviation", 0)) / 2.5))
            direction = "upper" if features.get("bw_deviation", 0) > 0 else "lower"
            return {
                "probability": round(prob, 3),
                "direction": direction,
                "time_to_violation_seconds": round(120.0 * (1.0 - prob), 1) if prob > 0.5 else None,
                "risk_level": "critical" if prob > 0.75 else "high" if prob > 0.5 else "moderate" if prob > 0.25 else "low",
                "model_mode": "degraded"
            }

        prob = float(self.model.predict_proba(X)[0][1])
        prob = min(0.99, max(0.01, prob))

        direction = "upper" if features.get("bw_deviation", 0) > 0 or features.get("bw_slope", 0) > 0.05 else "lower"
        if abs(features.get("bw_deviation", 0)) < 0.2 and abs(features.get("bw_slope", 0)) < 0.02:
            direction = "none"

        risk_level = "low"
        if prob > 0.75: risk_level = "critical"
        elif prob > 0.50: risk_level = "high"
        elif prob > 0.25: risk_level = "moderate"

        time_to_violation = round(max(30.0, 300.0 * (1.0 - prob)), 1) if prob > 0.5 else None

        return {
            "probability": round(prob, 3),
            "direction": direction,
            "time_to_violation_seconds": time_to_violation,
            "risk_level": risk_level,
            "model_mode": "trained"
        }

risk_predictor_service = RiskPredictor()
