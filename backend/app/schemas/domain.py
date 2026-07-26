from pydantic import BaseModel, ConfigDict
from typing import Any, Optional, List
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
    caliper_actual: float
    caliper_setpoint: float
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
    decision_threshold: float
    spec_deviation_pct: float

class TrajectoryHorizonSchema(BaseModel):
    seconds: float
    predicted_bw: float
    predicted_setpoint: float
    lower_bound: float
    upper_bound: float

class TrajectoryPredictionSchema(BaseModel):
    horizons: List[TrajectoryHorizonSchema]
    model_mode: str

class SimulationRequestSchema(BaseModel):
    event_id: str
    timestamp: datetime
    parameter_name: str
    proposed_value: float

class SimulationResultSchema(BaseModel):
    parameter_name: str
    current_value: float
    proposed_value: float
    feasible: bool
    constraint_message: str
    risk_before: float
    risk_after: float
    stabilization_before: float
    stabilization_after: float
    off_spec_seconds_before: float
    off_spec_seconds_after: float
    avoided_off_spec_seconds: float
    confidence: float
    baseline_trajectory: TrajectoryPredictionSchema
    counterfactual_trajectory: TrajectoryPredictionSchema
    evidence_tags: List[EvidenceTagSchema] = []

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


class VariableDefinitionSchema(BaseModel):
    tag: str
    display_name: str
    unit: str
    role: str
    source: str


class OutcomeSummarySchema(BaseModel):
    outcome: str
    event_count: int
    avg_stabilization_seconds: float
    avg_off_spec_seconds: float
    avg_max_deviation_pct: float


class TrajectoryProfilePointSchema(BaseModel):
    outcome: str
    progress_pct: int
    mean_deviation_pct: float
    p10_deviation_pct: float
    p90_deviation_pct: float


class FeatureImportanceSchema(BaseModel):
    feature: str
    importance: float


class RelationshipSummarySchema(BaseModel):
    source_parameter: str
    target_parameter: str
    strength: float
    lag_seconds: int
    is_interaction: bool
    occurrences: int
    source: str


class DataOverviewSchema(BaseModel):
    provenance: dict[str, Any]
    outcome_counts: dict[str, int]
    data_quality: dict[str, float | int]
    variables: List[VariableDefinitionSchema]
    split: dict[str, int | str | bool]
    model_metrics: dict[str, Any]
    outcome_summary: List[OutcomeSummarySchema]
    trajectory_profiles: List[TrajectoryProfilePointSchema]
    feature_importance: List[FeatureImportanceSchema]
    relationships: List[RelationshipSummarySchema]
    processing_steps: List[dict[str, str]]


class RecipeConstraintSchema(BaseModel):
    grade_id: str
    parameter: str
    min_val: float
    max_val: float
    optimal_val: float
    max_ramp_rate: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DataValidationRequestSchema(BaseModel):
    file_name: str
    columns: List[str]
    rows: List[dict[str, Any]]


class DataValidationResponseSchema(BaseModel):
    valid: bool
    file_name: str
    row_count: int
    coverage_pct: float
    mapped_columns: dict[str, str]
    missing_columns: List[str]
    warnings: List[str]
    parse_errors: List[str]
    data_quality: dict[str, float | int]
    preview: List[dict[str, Any]]
    sandbox_note: str


class ScenarioAdjustmentSchema(BaseModel):
    parameter_name: str
    proposed_value: float


class ScenarioRequestSchema(BaseModel):
    event_id: str
    timestamp: datetime
    adjustments: List[ScenarioAdjustmentSchema]


class ScenarioAdjustmentResultSchema(BaseModel):
    parameter_name: str
    current_value: float
    proposed_value: float
    feasible: bool
    constraint_message: str
    evidence_source: str


class ScenarioResultSchema(BaseModel):
    event_id: str
    timestamp: datetime
    feasible: bool
    scenario_mode: str
    adjustments: List[ScenarioAdjustmentResultSchema]
    risk_before: float
    risk_after: float
    stabilization_before: float
    stabilization_after: float
    off_spec_seconds_before: float
    off_spec_seconds_after: float
    avoided_off_spec_seconds: float
    confidence: float
    baseline_trajectory: TrajectoryPredictionSchema
    counterfactual_trajectory: TrajectoryPredictionSchema
    evidence_tags: List[EvidenceTagSchema]
    guardrail: str


class ExplanationRequestSchema(BaseModel):
    event_id: str
    timestamp: datetime
    recommendation_id: Optional[str] = None
    prefer_llm: bool = False


class ExplanationResponseSchema(BaseModel):
    mode: str
    model: Optional[str] = None
    headline: str
    what_is_happening: str
    why: str
    suggested_response: str
    operator_checks: List[str]
    evidence: List[EvidenceTagSchema]
    guardrail: str
