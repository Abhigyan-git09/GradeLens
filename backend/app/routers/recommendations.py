from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.schemas.domain import RecommendationSchema, OperatorFeedbackSchema
from app.models.domain import Recommendation, OperatorFeedback
from app.services.recommendation_engine import recommendation_engine

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.post("/generate", response_model=RecommendationSchema)
def generate_recommendation(event_id: str = Body(..., embed=True), db: Session = Depends(get_db)):
    rec = recommendation_engine.generate(event_id, db)
    if not rec:
        raise HTTPException(status_code=400, detail="Could not generate recommendation or not enough data.")
    return rec

@router.post("/{id}/accept", response_model=OperatorFeedbackSchema)
def accept_recommendation(id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    rec.status = "accepted"
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="accept",
        operator_selected_value=rec.recommended_value,
        timestamp=datetime.utcnow()
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@router.post("/{id}/reject", response_model=OperatorFeedbackSchema)
def reject_recommendation(id: str, reason: str = Body(..., embed=True), db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    rec.status = "rejected"
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="reject",
        rejection_reason=reason,
        timestamp=datetime.utcnow()
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@router.post("/{id}/modify", response_model=OperatorFeedbackSchema)
def modify_recommendation(id: str, value: float = Body(..., embed=True), db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    rec.status = "modified"
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="modify",
        operator_selected_value=value,
        timestamp=datetime.utcnow()
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
