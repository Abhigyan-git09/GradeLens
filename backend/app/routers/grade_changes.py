from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.domain import GradeChangeEvent, TimeseriesPoint, Recommendation
from app.schemas.domain import (
    GradeChangeEventSchema, 
    TimeseriesPointSchema, 
    RootCauseSchema, 
    RecommendationSchema,
    SnapshotResponseSchema,
    RiskPredictionSchema,
    TrajectoryPredictionSchema,
    StabilizationPredictionSchema,
)
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service
from ml.trajectory_forecast import trajectory_forecaster_service
from ml.stabilization_service import stabilization_service

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
def get_root_causes(event_id: str, timestamp: str = None, db: Session = Depends(get_db)):
    from app.services.rootcause_service import rootcause_service
    return rootcause_service.get_root_causes(event_id, db, timestamp=timestamp)

@router.get("/{event_id}/recommendations", response_model=List[RecommendationSchema])
def get_recommendations(event_id: str, db: Session = Depends(get_db)):
    # Fetch from DB
    return db.query(Recommendation).filter(Recommendation.event_id == event_id).all()

@router.get("/{event_id}/snapshot", response_model=SnapshotResponseSchema)
def get_snapshot(event_id: str, timestamp: datetime = Query(...), db: Session = Depends(get_db)):
    """
    Returns a unified snapshot of the event up to the given timestamp,
    preventing any future-data leakage.
    """
    event = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    pts = db.query(TimeseriesPoint).filter(
        TimeseriesPoint.event_id == event_id,
        TimeseriesPoint.timestamp <= timestamp
    ).order_by(TimeseriesPoint.timestamp.asc()).all()

    snapshot = SnapshotResponseSchema(
        event=GradeChangeEventSchema.model_validate(event),
        timeseries=[TimeseriesPointSchema.model_validate(p) for p in pts],
        root_causes=[],
        correlations=[]
    )

    if len(pts) >= 12:
        # Recompute features
        features = feature_service.extract_features(pts[-12:])
        snapshot.current_features = features
        
        # Risk
        snapshot.risk = RiskPredictionSchema(
            **risk_predictor_service.predict_risk(features)
        )
        
        # Trajectory
        snapshot.trajectory = TrajectoryPredictionSchema(
            **trajectory_forecaster_service.forecast(features)
        )
        current_deviation_pct = abs(
            features.get("bw_deviation_pct", 0.0)
        )
        if snapshot.risk and current_deviation_pct >= 2.5:
            snapshot.risk.time_to_violation_seconds = 0.0
        elif snapshot.risk and snapshot.risk.probability >= 0.5:
            crossing = next(
                (
                    horizon.seconds
                    for horizon in snapshot.trajectory.horizons
                    if horizon.predicted_setpoint
                    and abs(
                        horizon.predicted_bw
                        - horizon.predicted_setpoint
                    )
                    / horizon.predicted_setpoint
                    * 100.0
                    >= 2.5
                ),
                None,
            )
            snapshot.risk.time_to_violation_seconds = crossing
        
        # Stabilization
        snapshot.stabilization = StabilizationPredictionSchema(
            **stabilization_service.estimate_stabilization(features)
        )
        
        # Root causes
        from app.services.rootcause_service import rootcause_service
        # Pass features directly so it doesn't need to refetch and leak future data
        snapshot.root_causes = rootcause_service.get_root_causes(event_id, db, features=features)  
        if len(pts) >= 30:
            from app.services.correlation_service import correlation_service
            snapshot.correlations = correlation_service.discover_relationships(
                event_id, db, timestamp=timestamp
            )
        
    # Recommendations: find the latest recommendation generated AT OR BEFORE this timestamp
    # Note: recommendations might not have timestamps attached correctly in some versions, 
    # but let's filter by timestamp if available.
    recs = db.query(Recommendation).filter(
        Recommendation.event_id == event_id,
        Recommendation.timestamp <= timestamp
    ).order_by(Recommendation.timestamp.desc()).all()
    
    if recs:
        snapshot.recommendation = RecommendationSchema.model_validate(recs[0])
        
    return snapshot
