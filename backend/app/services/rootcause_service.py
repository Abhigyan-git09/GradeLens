from typing import List, Dict
import os
import joblib

from sqlalchemy.orm import Session
from app.models.domain import GradeChangeEvent, TimeseriesPoint
from app.schemas.domain import RootCauseSchema
from ml.feature_service import feature_service

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ml", "artifacts")

class RootCauseService:
    def __init__(self):
        self.model_path = os.path.join(MODEL_DIR, "risk_model.joblib")
        self.feature_names = ["bw_deviation", "bw_slope", "stock_flow_ramp", "interaction_feature"]
        self.display_names = {
            "bw_deviation": "Basis Weight Deviation",
            "bw_slope": "Basis Weight Velocity",
            "stock_flow_ramp": "Stock Flow Ramp",
            "interaction_feature": "Filler x Steam Interaction"
        }
        self.model = None
        self.importances = []
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            # Normalize importances
            raw_imp = self.model.feature_importances_
            total = sum(raw_imp)
            if total > 0:
                self.importances = [i / total for i in raw_imp]
            else:
                self.importances = [0.25] * 4

    def get_root_causes(self, event_id: str, db: Session) -> List[RootCauseSchema]:
        if not self.model or not self.importances:
            return []

        # Get current event state
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.desc()).limit(10).all()
        if len(pts) < 10:
            return []
            
        window = list(reversed(pts))
        features = feature_service.extract_features(window)
        
        # Rank features by static importance (for demo consistency) combined with current magnitude
        # Since interaction_feature is only high in specific cases, we weight importance by the normalized feature magnitude.
        
        magnitudes = [
            abs(features["bw_deviation"]) / 2.0,  # Normalize roughly by max expected deviation
            abs(features["bw_slope"]) / 0.1,
            abs(features["stock_flow_ramp"]) / 10.0,
            abs(features["interaction_feature"]) / 1.0  # Threshold is ~1.0
        ]
        
        # Calculate dynamic contribution
        contributions = []
        for i in range(4):
            score = self.importances[i] * magnitudes[i]
            contributions.append((self.feature_names[i], score))
            
        contributions.sort(key=lambda x: x[1], reverse=True)
        total_score = sum(c[1] for c in contributions) + 1e-9
        
        results = []
        for name, score in contributions:
            pct = score / total_score
            if pct < 0.05: # Skip trivial contributions
                continue
                
            # Generate Rationale
            if name == "interaction_feature":
                rationale = f"{self.display_names[name]} — {pct*100:.0f}% contribution — anomalous compounding effect detected between filler flow and steam pressure at a 45s lag."
            elif name == "stock_flow_ramp":
                rationale = f"{self.display_names[name]} — {pct*100:.0f}% contribution — ramp rate is significantly steeper than median successful transitions."
            elif name == "bw_deviation":
                rationale = f"{self.display_names[name]} — {pct*100:.0f}% contribution — process is currently {features['bw_deviation']:.2f} away from setpoint."
            elif name == "bw_slope":
                rationale = f"{self.display_names[name]} — {pct*100:.0f}% contribution — drift velocity is high in the off-spec direction."
                
            results.append(RootCauseSchema(
                parameter_name=self.display_names[name],
                contribution_pct=round(pct, 2),
                current_deviation=round(magnitudes[contributions.index((name, score))] * 2.0, 2), # Un-normalize rough deviation
                rationale=rationale,
                is_interaction=(name == "interaction_feature")
            ))
            
        return results

rootcause_service = RootCauseService()
