import json
import joblib
import numpy as np
import lightgbm as lgb
from typing import Dict, Optional, Any
from app.config import settings
from ml.feature_service import FEATURE_NAMES

class RiskPredictor:
    def __init__(self):
        self.model_path = settings.MODEL_DIR / "risk_model.joblib"
        self.metrics_path = settings.MODEL_DIR / "metrics.json"
        self.model = None
        self.is_trained = False
        self.decision_threshold = settings.RISK_THRESHOLD
        self._load_model()

    def _load_model(self):
        self.model = None
        self.is_trained = False
        self.decision_threshold = settings.RISK_THRESHOLD
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                if self.metrics_path.exists():
                    metrics = json.loads(
                        self.metrics_path.read_text(encoding="utf-8")
                    )
                    artifact_threshold = metrics.get("risk", {}).get(
                        "decision_threshold"
                    )
                    if isinstance(artifact_threshold, (int, float)):
                        self.decision_threshold = min(
                            1.0, max(0.0, float(artifact_threshold))
                        )
                self.is_trained = True
            except Exception:
                self.is_trained = False

    def reload_model(self):
        """Reload a model created during application startup."""
        self._load_model()

    def predict_risk(self, features: Dict[str, float]) -> dict:
        """Predict probability of off-spec within next 120s."""
        X = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

        if not self.is_trained:
            # Fallback degraded mode
            prob = min(
                0.99,
                max(0.01, abs(features.get("bw_deviation_pct", 0)) / 2.5),
            )
            direction = "upper" if features.get("bw_deviation", 0) > 0 else "lower"
            return {
                "probability": round(prob, 3),
                "direction": direction,
                "time_to_violation_seconds": self._time_to_limit(features),
                "risk_level": "critical" if prob > 0.75 else "high" if prob > 0.5 else "moderate" if prob > 0.25 else "low",
                "model_mode": "degraded",
                "decision_threshold": self.decision_threshold,
                "spec_deviation_pct": settings.SPEC_DEVIATION_PCT,
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

        time_to_violation = self._time_to_limit(features) if prob > 0.5 else None

        return {
            "probability": round(prob, 3),
            "direction": direction,
            "time_to_violation_seconds": time_to_violation,
            "risk_level": risk_level,
            "model_mode": "trained",
            "decision_threshold": self.decision_threshold,
            "spec_deviation_pct": settings.SPEC_DEVIATION_PCT,
        }

    @staticmethod
    def _time_to_limit(features: Dict[str, float]) -> Optional[float]:
        """Physics-based linear estimate, used only when the slope approaches a limit."""
        setpoint = abs(features.get("current_setpoint", 0.0))
        if setpoint <= 0:
            return None
        deviation = features.get("bw_deviation", 0.0)
        relative_slope = (
            features.get("bw_slope", 0.0)
            - features.get("setpoint_slope", 0.0)
        )
        limit = setpoint * 0.025
        if relative_slope > 1e-6:
            seconds = (limit - deviation) / relative_slope
        elif relative_slope < -1e-6:
            seconds = (-limit - deviation) / relative_slope
        else:
            return None
        return round(max(0.0, seconds), 1) if 0 <= seconds <= 300 else None

risk_predictor_service = RiskPredictor()
