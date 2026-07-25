from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class EvidenceTagSchema(BaseModel):
    tag: str
    source: str
    detail: str

    model_config = ConfigDict(from_attributes=True)

class OperatorFeedbackSchema(BaseModel):
    feedback_id: str
    recommendation_id: str
    response: str
    operator_selected_value: Optional[float] = None
    rejection_reason: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class RecommendationSchema(BaseModel):
    recommendation_id: str
    event_id: str
    timestamp: datetime
    parameter_name: str
    current_value: float
    recommended_value: float
    recommended_ramp_rate: float
    risk_before: float
    risk_after: float
    stabilization_before: float
    stabilization_after: float
    confidence: float
    rationale: str
    status: str
    evidence_tags: List[EvidenceTagSchema] = []

    model_config = ConfigDict(from_attributes=True)

class TimeseriesPointSchema(BaseModel):
    timestamp: datetime
    event_id: str
    basis_weight_actual: float
    basis_weight_setpoint: float
    stock_flow_actual: float
    stock_flow_setpoint: float
    filler_flow_actual: float
    filler_flow_setpoint: float
    steam_pressure_actual: float
    steam_pressure_setpoint: float
    machine_speed_actual: float
    machine_speed_setpoint: float
    moisture_actual: float
    moisture_setpoint: float
    ash_actual: float
    ash_setpoint: float
    active_alarm_count: int
    scanner_quality_score: float

    model_config = ConfigDict(from_attributes=True)

class GradeChangeEventSchema(BaseModel):
    event_id: str
    machine_id: str
    source_grade: str
    target_grade: str
    recipe_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    bw_old_target: float
    bw_new_target: float
    stabilization_seconds: Optional[float] = None
    off_spec_seconds: Optional[float] = None
    max_deviation_pct: Optional[float] = None
    transition_outcome: str

    model_config = ConfigDict(from_attributes=True)

class RootCauseSchema(BaseModel):
    parameter_name: str
    contribution_pct: float
    current_deviation: float
    rationale: str
    is_interaction: bool

class RiskPredictionSchema(BaseModel):
    probability: float
    direction: str
    time_to_violation_seconds: Optional[float]
    model_mode: str
    risk_level: str

class TrajectoryHorizonSchema(BaseModel):
    seconds: float
    predicted_bw: float
    lower_bound: float
    upper_bound: float

class TrajectoryPredictionSchema(BaseModel):
    horizons: List[TrajectoryHorizonSchema]
    model_mode: str

class StabilizationPredictionSchema(BaseModel):
    estimated_seconds: float
    similar_events_used: int
    model_mode: str

class DiscoveredRelationshipSchema(BaseModel):
    event_id: str
    source_parameter: str
    target_parameter: str
    strength: float
    lag_seconds: int
    is_interaction: bool
    is_newly_discovered: bool
    sample_note: str

    model_config = ConfigDict(from_attributes=True)

class SnapshotResponseSchema(BaseModel):
    event: GradeChangeEventSchema
    timeseries: List[TimeseriesPointSchema]
    current_features: Optional[dict] = None
    risk: Optional[RiskPredictionSchema] = None
    trajectory: Optional[TrajectoryPredictionSchema] = None
    stabilization: Optional[StabilizationPredictionSchema] = None
    root_causes: List[RootCauseSchema] = []
    recommendation: Optional[RecommendationSchema] = None
    correlations: List[DiscoveredRelationshipSchema] = []
