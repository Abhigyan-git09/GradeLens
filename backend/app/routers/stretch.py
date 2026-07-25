from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict

from app.database import get_db
from app.schemas.domain import DiscoveredRelationshipSchema
from app.models.domain import Recommendation, OperatorFeedback

router = APIRouter(tags=["Stretch & Audit"])

@router.post("/simulation/setpoints")
def simulate_setpoints(setpoints: Dict):
    # Stretch goal
    return {"status": "not_implemented"}

@router.get("/correlations", response_model=List[DiscoveredRelationshipSchema])
def get_correlations(db: Session = Depends(get_db)):
    from app.services.correlation_service import correlation_service
    from app.models.domain import DiscoveredRelationship
    
    # Run discovery on the Demo Event (Recoverable)
    correlation_service.discover_relationships("EVT-003-RECOVERABLE", db)
    
    return db.query(DiscoveredRelationship).all()

@router.get("/audit/recommendations")
def get_audit_log(db: Session = Depends(get_db)):
    feedbacks = db.query(OperatorFeedback).order_by(OperatorFeedback.timestamp.desc()).all()
    result = []
    for fb in feedbacks:
        rec = db.query(Recommendation).filter(Recommendation.recommendation_id == fb.recommendation_id).first()
        result.append({
            "feedback_id": fb.feedback_id,
            "recommendation_id": fb.recommendation_id,
            "response": fb.response,
            "operator_selected_value": fb.operator_selected_value,
            "rejection_reason": fb.rejection_reason,
            "timestamp": fb.timestamp,
            "recommendation": {
                "parameter_name": rec.parameter_name if rec else "N/A",
                "recommended_value": rec.recommended_value if rec else None,
                "recommendation_id": fb.recommendation_id,
            }
        })
    return result
