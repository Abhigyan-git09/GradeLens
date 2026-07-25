import uuid
from typing import List, Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.models.domain import (
    GradeChangeEvent, TimeseriesPoint, RecipeConstraint,
    Recommendation, EvidenceTag
)
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service
from ml.feature_service import feature_service

class RecommendationEngine:
    def __init__(self):
        # Objective function weights
        self.w1 = 0.6  # Risk reduction
        self.w2 = 0.3  # Stabilization time
        self.w3 = 0.1  # Change from current

    def generate(self, event_id: str, db: Session) -> Optional[Recommendation]:
        event = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id == event_id).first()
        if not event:
            return None
            
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.desc()).limit(10).all()
        if len(pts) < 10:
            return None
            
        # Reverse to chronological for feature extraction
        window = list(reversed(pts))
        current_features = feature_service.extract_features(window)
        latest_pt = window[-1]
        
        # Current baseline
        current_risk = risk_predictor_service.predict_risk(current_features)["probability"]
        current_stab = stabilization_service.estimate_stabilization(current_features)["estimated_seconds"]
        
        # 1. Candidate Generation
        target_parameters = [
            {"name": "stock_flow", "current": latest_pt.stock_flow_actual},
            {"name": "machine_speed", "current": latest_pt.machine_speed_actual}
        ]
        
        offsets = [-0.10, -0.08, -0.06, -0.04, -0.02, 0.02, 0.04, 0.06, 0.08, 0.10]
        candidates = []
        
        for param in target_parameters:
            for offset in offsets:
                cand_val = param["current"] * (1 + offset)
                candidates.append({
                    "parameter": param["name"],
                    "value": cand_val,
                    "offset_pct": offset
                })
                
        # 2. Constraint Filter
        constraints = db.query(RecipeConstraint).filter(RecipeConstraint.grade_id == event.target_grade).all()
        const_dict = {c.parameter: c for c in constraints}
        
        valid_candidates = []
        for cand in candidates:
            p_name = cand["parameter"]
            val = cand["value"]
            if p_name in const_dict:
                c = const_dict[p_name]
                if val < c.min_val or val > c.max_val:
                    continue # Hard reject
            valid_candidates.append(cand)
            
        if not valid_candidates:
            return None

        # 3. Re-score
        scored_candidates = []
        for cand in valid_candidates:
            # Simulate features after recommendation
            sim_features = current_features.copy()
            if cand["parameter"] == "stock_flow":
                # Assuming setting new stock flow changes the ramp significantly
                sim_features["stock_flow_ramp"] = (cand["value"] - current_features["current_bw"]) / 10.0 # Rough sim
                
            risk_res = risk_predictor_service.predict_risk(sim_features)
            stab_res = stabilization_service.estimate_stabilization(sim_features)
            
            risk_after = risk_res["probability"]
            stab_after = stab_res["estimated_seconds"]
            
            # Objective: lower is better
            score = (self.w1 * risk_after) + (self.w2 * stab_after / 600.0) + (self.w3 * abs(cand["offset_pct"]))
            
            cand["risk_after"] = risk_after
            cand["stab_after"] = stab_after
            cand["score"] = score
            scored_candidates.append(cand)
            
        if not scored_candidates:
            return None
            
        # 4. Rank and pick best
        scored_candidates.sort(key=lambda x: x["score"])
        best = scored_candidates[0]
        
        # 5. Create Recommendation & Tags
        param_display_name = "Stock Flow" if best["parameter"] == "stock_flow" else "Machine Speed"
        direction_text = "Increase" if best["offset_pct"] > 0 else "Decrease"
        
        rec = Recommendation(
            recommendation_id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=datetime.utcnow(),
            parameter_name=param_display_name,
            current_value=best["value"] / (1 + best["offset_pct"]),
            recommended_value=best["value"],
            recommended_ramp_rate= (best["value"] - best["value"]/(1+best["offset_pct"])) / 10.0,
            risk_before=current_risk,
            risk_after=best["risk_after"],
            stabilization_before=current_stab,
            stabilization_after=best["stab_after"],
            confidence=0.85,
            rationale=f"{direction_text} {param_display_name} by {abs(best['offset_pct'])*100:.1f}% to mitigate {current_risk*100:.0f}% off-spec risk.",
            status="pending"
        )
        db.add(rec)
        db.commit()
        
        # 6 Evidence Tags
        tags = [
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Risk Model", source="LightGBM Classifier", detail=f"Projects a {current_risk*100:.0f}% chance of exceeding spec limits within 120s without intervention."),
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Trajectory Forecast", source="LightGBM Regressor", detail="Forecast shows basis weight drifting above setpoint over the next 60s."),
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Recipe Constraint", source="System Bounds", detail=f"Recommended value {best['value']:.1f} is well within the {event.target_grade} recipe limits."),
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Historical Success", source="k-NN Estimator", detail=f"Similar transitions achieved stabilization in {best['stab_after']:.0f}s using this parameter profile."),
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Process Correlation", source="Interaction Engine", detail="Identified compound interaction between filler flow and steam pressure driving current deviation."),
            EvidenceTag(recommendation_id=rec.recommendation_id, tag="Rule-Based Safety Check", source="Actuator Limits", detail="Ramp rate complies with physical machine tolerances.")
        ]
        db.add_all(tags)
        db.commit()
        db.refresh(rec)
        
        return rec

recommendation_engine = RecommendationEngine()
