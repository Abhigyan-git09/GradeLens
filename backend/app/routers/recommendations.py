from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from datetime import UTC, datetime

from app.database import get_db
from app.schemas.domain import (
    RecommendationSchema,
    OperatorFeedbackSchema,
    SimulationRequestSchema,
    SimulationResultSchema,
)
from app.models.domain import Recommendation, OperatorFeedback
from app.services.recommendation_engine import recommendation_engine
from app.services.counterfactual_service import counterfactual_service
from app.security import require_write_access

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/opportunities", response_model=list[SimulationResultSchema])
def get_opportunities(
    event_id: str,
    timestamp: datetime,
    db: Session = Depends(get_db),
):
    return counterfactual_service.rank_opportunities(
        event_id, timestamp, db
    )

@router.post("/simulate", response_model=SimulationResultSchema)
def simulate_recommendation(
    request: SimulationRequestSchema,
    db: Session = Depends(get_db),
):
    result = counterfactual_service.simulate(
        request.event_id,
        request.timestamp,
        request.parameter_name,
        request.proposed_value,
        db,
    )
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Unable to simulate this parameter at the selected time.",
        )
    return result

@router.post(
    "/generate",
    response_model=RecommendationSchema,
    dependencies=[Depends(require_write_access)],
)
def generate_recommendation(event_id: str = Body(..., embed=True), timestamp: str = Body(None, embed=True), db: Session = Depends(get_db)):
    rec = recommendation_engine.generate(event_id, db, timestamp)
    if not rec:
        raise HTTPException(status_code=400, detail="Could not generate recommendation or not enough data.")
    return rec

@router.post(
    "/{id}/accept",
    response_model=OperatorFeedbackSchema,
    dependencies=[Depends(require_write_access)],
)
def accept_recommendation(id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    existing_feedback = db.query(OperatorFeedback).filter(OperatorFeedback.recommendation_id == id).first()
    if existing_feedback:
        raise HTTPException(status_code=409, detail="Feedback already processed")
        
    rec.status = "accepted"
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="accept",
        operator_selected_value=rec.recommended_value,
        timestamp=datetime.now(UTC).replace(tzinfo=None)
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@router.post(
    "/{id}/reject",
    response_model=OperatorFeedbackSchema,
    dependencies=[Depends(require_write_access)],
)
def reject_recommendation(id: str, reason: str = Body(..., embed=True), db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    existing_feedback = db.query(OperatorFeedback).filter(OperatorFeedback.recommendation_id == id).first()
    if existing_feedback:
        raise HTTPException(status_code=409, detail="Feedback already processed")
        
    rec.status = "rejected"
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="reject",
        rejection_reason=reason,
        timestamp=datetime.now(UTC).replace(tzinfo=None)
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@router.post(
    "/{id}/modify",
    response_model=OperatorFeedbackSchema,
    dependencies=[Depends(require_write_access)],
)
def modify_recommendation(id: str, value: float = Body(..., embed=True), db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    existing_feedback = db.query(OperatorFeedback).filter(OperatorFeedback.recommendation_id == id).first()
    if existing_feedback:
        raise HTTPException(status_code=409, detail="Feedback already processed")
    simulation = counterfactual_service.simulate(
        rec.event_id,
        rec.timestamp,
        rec.parameter_name,
        value,
        db,
    )
    if not simulation or not simulation["feasible"]:
        raise HTTPException(
            status_code=422,
            detail=(
                simulation["constraint_message"]
                if simulation
                else "Modified value could not be validated."
            ),
        )
        
    rec.status = "modified"
    rec.recommended_value = value
    rec.risk_after = simulation["risk_after"]
    rec.stabilization_after = simulation["stabilization_after"]
    feedback = OperatorFeedback(
        recommendation_id=id,
        response="modify",
        operator_selected_value=value,
        timestamp=datetime.now(UTC).replace(tzinfo=None)
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
