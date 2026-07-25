/* TypeScript type definitions for GradeLens */

// ---- Grade Change Event ----
export interface GradeChangeEvent {
  event_id: string;
  machine_id: string;
  source_grade: string;
  target_grade: string;
  recipe_id: string;
  start_time: string;
  end_time: string;
  bw_old_target: number;
  bw_new_target: number;
  stabilization_seconds: number | null;
  off_spec_seconds: number | null;
  max_deviation_pct: number | null;
  transition_outcome: 'success' | 'failure' | 'in_progress';
}

// ---- Process Timeseries ----
export interface TimeseriesPoint {
  timestamp: string;
  event_id: string;
  basis_weight_actual: number;
  basis_weight_setpoint: number;
  stock_flow_actual: number;
  stock_flow_setpoint: number;
  filler_flow_actual: number;
  filler_flow_setpoint: number;
  steam_pressure_actual: number;
  steam_pressure_setpoint: number;
  machine_speed_actual: number;
  machine_speed_setpoint: number;
  moisture_actual: number;
  moisture_setpoint: number;
  ash_actual: number;
  ash_setpoint: number;
  active_alarm_count: number;
  scanner_quality_score: number;
}

// ---- Risk Prediction ----
export interface RiskPrediction {
  probability: number;
  direction: 'upper' | 'lower' | 'none';
  time_to_violation_seconds: number | null;
  model_mode: 'trained' | 'degraded' | 'demo';
  risk_level: 'low' | 'moderate' | 'high' | 'critical';
}

// ---- Trajectory Prediction ----
export interface TrajectoryPrediction {
  horizons: {
    seconds: number;
    predicted_bw: number;
    lower_bound: number;
    upper_bound: number;
  }[];
  model_mode: 'trained' | 'degraded' | 'demo';
}

// ---- Root Cause ----
export interface RootCause {
  parameter_name: string;
  contribution_pct: number;
  current_deviation: number;
  rationale: string;
  is_interaction: boolean;
}

// ---- Recommendation ----
export interface Recommendation {
  recommendation_id: string;
  event_id: string;
  timestamp: string;
  parameter_name: string;
  current_value: number;
  recommended_value: number;
  recommended_ramp_rate: number;
  risk_before: number;
  risk_after: number;
  stabilization_before: number;
  stabilization_after: number;
  confidence: number;
  rationale: string;
  evidence_tags: EvidenceTag[];
  status: 'pending' | 'accepted' | 'rejected' | 'modified';
}

// ---- Evidence Tag ----
export interface EvidenceTag {
  tag: string;
  source: string;
  detail: string;
}

// ---- Operator Feedback ----
export interface OperatorFeedback {
  feedback_id: string;
  recommendation_id: string;
  response: 'accept' | 'reject' | 'modify';
  operator_selected_value: number | null;
  rejection_reason: string | null;
  timestamp: string;
}

// ---- Discovered Relationship ----
export interface DiscoveredRelationship {
  source_parameter: string;
  target_parameter: string;
  strength: number;
  lag_seconds: number;
  is_interaction: boolean;
  is_newly_discovered: boolean;
  sample_note: string;
}

// ---- Health Check ----
export interface HealthStatus {
  status: string;
  model_mode: 'trained' | 'degraded' | 'partial';
  version: string;
  project: string;
}

// ---- Audit Entry ----
export interface AuditEntry {
  recommendation: Recommendation;
  feedback: OperatorFeedback | null;
}
