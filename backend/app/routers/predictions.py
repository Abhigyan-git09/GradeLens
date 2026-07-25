from fastapi import APIRouter, Depends
from typing import List, Dict

from app.schemas.domain import RiskPredictionSchema, TrajectoryPredictionSchema

router = APIRouter(prefix="/predictions", tags=["Predictions"])

@router.post("/risk", response_model=RiskPredictionSchema)
def predict_risk(features: Dict):
    # To be fully wired; currently returns stub for schema
    from ml.risk_predictor import risk_predictor_service
    return risk_predictor_service.predict_risk(features)

@router.post("/trajectory", response_model=TrajectoryPredictionSchema)
def predict_trajectory(features: Dict):
    from ml.trajectory_forecast import trajectory_forecaster_service
    return trajectory_forecaster_service.forecast(features)
