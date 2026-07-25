from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.domain import GradeChangeEvent, TimeseriesPoint
from app.schemas.domain import GradeChangeEventSchema, TimeseriesPointSchema, RootCauseSchema, RecommendationSchema

router = APIRouter(prefix="/grade-changes", tags=["Grade Changes"])

@router.get("", response_model=List[GradeChangeEventSchema])
def list_grade_changes(db: Session = Depends(get_db)):
    return db.query(GradeChangeEvent).all()

@router.get("/{event_id}", response_model=GradeChangeEventSchema)
def get_grade_change(event_id: str, db: Session = Depends(get_db)):
    event = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.get("/{event_id}/timeseries", response_model=List[TimeseriesPointSchema])
def get_timeseries(event_id: str, db: Session = Depends(get_db)):
    return db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.asc()).all()

@router.get("/{event_id}/root-causes", response_model=List[RootCauseSchema])
def get_root_causes(event_id: str, db: Session = Depends(get_db)):
    from app.services.rootcause_service import rootcause_service
    return rootcause_service.get_root_causes(event_id, db)

@router.get("/{event_id}/recommendations", response_model=List[RecommendationSchema])
def get_recommendations(event_id: str, db: Session = Depends(get_db)):
    # Fetch from DB
    from app.models.domain import Recommendation
    return db.query(Recommendation).filter(Recommendation.event_id == event_id).all()
