import os
import joblib
import numpy as np
import lightgbm as lgb
from typing import Dict, Optional, Any

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

class RiskPredictor:
    def __init__(self):
        self.model_path = os.path.join(MODEL_DIR, "risk_model.joblib")
        self.model = None
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_trained = True

    def predict_risk(self, features: Dict[str, float]) -> dict:
        """Predict probability of off-spec within next 120s."""
        # Feature array: [bw_deviation, bw_slope, stock_flow_ramp, interaction_feature]
        X = np.array([[
            features["bw_deviation"], 
            features["bw_slope"], 
            features["stock_flow_ramp"], 
            features["interaction_feature"]
        ]])
        
        if not self.is_trained:
            # Fallback degraded mode
            prob = min(0.99, max(0.01, abs(features["bw_deviation"]) / 2.5))
            direction = "upper" if features["bw_deviation"] > 0 else "lower"
            return {
                "probability": prob,
                "direction": direction,
                "time_to_violation_seconds": 120.0 if prob > 0.5 else None,
                "risk_level": "high" if prob > 0.75 else "moderate" if prob > 0.4 else "low",
                "model_mode": "degraded"
            }
            
        prob = float(self.model.predict_proba(X)[0][1])
        prob = min(0.99, max(0.01, prob))
        
        direction = "upper" if features["bw_deviation"] > 0 or features["bw_slope"] > 0.05 else "lower"
        if abs(features["bw_deviation"]) < 0.2 and abs(features["bw_slope"]) < 0.02:
            direction = "none"
            
        risk_level = "low"
        if prob > 0.75: risk_level = "critical"
        elif prob > 0.50: risk_level = "high"
        elif prob > 0.25: risk_level = "moderate"
        
        time_to_violation = max(30.0, 300.0 * (1.0 - prob)) if prob > 0.5 else None
        
        return {
            "probability": prob,
            "direction": direction,
            "time_to_violation_seconds": time_to_violation,
            "risk_level": risk_level,
            "model_mode": "trained"
        }

risk_predictor_service = RiskPredictor()
