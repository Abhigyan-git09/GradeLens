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
  caliper_actual: number;
  caliper_setpoint: number;
  active_alarm_count: number;
  scanner_quality_score: number;
}

// ---- Risk Prediction ----
export interface RiskPrediction {
  probability: number;
  direction: 'upper' | 'lower' | 'none';
  time_to_violation_seconds: number | null;
  model_mode: 'trained' | 'degraded' | 'demo' | 'hybrid';
  risk_level: 'low' | 'moderate' | 'high' | 'critical';
}

// ---- Trajectory Prediction ----
export interface TrajectoryPrediction {
  horizons: {
    seconds: number;
    predicted_bw: number;
    predicted_setpoint: number;
    lower_bound: number;
    upper_bound: number;
  }[];
  model_mode: 'trained' | 'degraded' | 'demo' | 'hybrid';
}

// ---- Stabilization Prediction ----
export interface StabilizationPrediction {
  estimated_seconds: number;
  similar_events_used: number;
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

export interface SimulationResult {
  parameter_name: string;
  current_value: number;
  proposed_value: number;
  feasible: boolean;
  constraint_message: string;
  risk_before: number;
  risk_after: number;
  stabilization_before: number;
  stabilization_after: number;
  off_spec_seconds_before: number;
  off_spec_seconds_after: number;
  avoided_off_spec_seconds: number;
  confidence: number;
  baseline_trajectory: TrajectoryPrediction;
  counterfactual_trajectory: TrajectoryPrediction;
  evidence_tags: EvidenceTag[];
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
  ready?: boolean;
  model_mode: 'trained' | 'degraded' | 'partial';
  database_ready?: boolean;
  version: string;
  project: string;
  environment?: 'development' | 'test' | 'production';
  metrics?: DataOverview['model_metrics'] | null;
}

// ---- Audit Entry ----
export interface AuditEntry {
  feedback_id: string;
  recommendation_id: string;
  response: string;
  operator_selected_value: number | null;
  rejection_reason: string | null;
  timestamp: string;
  recommendation: {
    parameter_name: string;
    recommended_value: number | null;
    recommendation_id: string;
  };
}

// ---- Data & Model Evidence ----
export interface VariableDefinition {
  tag: string;
  display_name: string;
  unit: string;
  role: string;
  source: string;
}

export interface OutcomeSummary {
  outcome: string;
  event_count: number;
  avg_stabilization_seconds: number;
  avg_off_spec_seconds: number;
  avg_max_deviation_pct: number;
}

export interface TrajectoryProfilePoint {
  outcome: string;
  progress_pct: number;
  mean_deviation_pct: number;
  p10_deviation_pct: number;
  p90_deviation_pct: number;
}

export interface DataOverview {
  provenance: {
    source_type: string;
    dataset_label: string;
    storage: string;
    generated_by: string;
    synthetic: boolean;
    deterministic_seed: number;
    sample_interval_seconds: number;
    event_count: number;
    point_count: number;
    start_time: string;
    end_time: string;
    machines: string[];
    grades: string[];
    grade_pairs: string[];
    site_data_status: string;
  };
  outcome_counts: Record<string, number>;
  data_quality: {
    missing_cells: number;
    completeness_pct: number;
    avg_scanner_quality: number;
    alarm_point_pct: number;
  };
  variables: VariableDefinition[];
  split: {
    strategy: string;
    training_pool_events: number;
    train_events: number;
    validation_events: number;
    test_events: number;
    curated_demo_events: number;
    demo_events_excluded: boolean;
    future_window_leakage_prevented: boolean;
  };
  model_metrics: {
    dataset?: Record<string, number | string>;
    risk?: {
      windows?: number;
      positive_windows?: number;
      accuracy?: number;
      precision?: number;
      recall?: number;
      roc_auc?: number | null;
      pr_auc?: number | null;
      brier_score?: number;
      decision_threshold?: number;
      threshold_source?: string;
      positive_windows_already_off_spec_fraction?: number;
      validation?: {
        windows: number;
        positive_windows: number;
        selected_threshold: number;
        precision_at_threshold: number;
      };
      pre_breach_30s?: {
        windows: number;
        positive_windows: number;
        accuracy: number;
        precision: number;
        recall: number;
        roc_auc: number | null;
        pr_auc: number | null;
        brier_score: number;
      };
      event_level?: {
        test_events: number;
        failure_events: number;
        detected_failure_events: number;
        missed_failure_events: number;
        false_alert_success_events: number;
        median_warning_seconds: number | null;
        minimum_warning_seconds: number | null;
      };
    };
    trajectory_mae_gsm?: Record<string, number>;
    stabilization_validation_mae_seconds?: number;
    stabilization_regressor_weight?: number;
    stabilization_mae_seconds?: number;
  };
  outcome_summary: OutcomeSummary[];
  trajectory_profiles: TrajectoryProfilePoint[];
  feature_importance: { feature: string; importance: number }[];
  relationships: {
    source_parameter: string;
    target_parameter: string;
    strength: number;
    lag_seconds: number;
    is_interaction: boolean;
    occurrences: number;
    source: string;
  }[];
  processing_steps: { stage: string; detail: string }[];
}

export interface RecipeConstraint {
  grade_id: string;
  parameter: string;
  min_val: number;
  max_val: number;
  optimal_val: number;
  max_ramp_rate: number | null;
}

export interface DataValidationResult {
  valid: boolean;
  file_name: string;
  row_count: number;
  coverage_pct: number;
  mapped_columns: Record<string, string>;
  missing_columns: string[];
  warnings: string[];
  parse_errors: string[];
  data_quality: {
    numeric_completeness_pct: number;
    validated_rows: number;
    required_feature_window_rows: number;
  };
  preview: Record<string, unknown>[];
  sandbox_note: string;
}

export interface ScenarioResult {
  event_id: string;
  timestamp: string;
  feasible: boolean;
  scenario_mode: string;
  adjustments: {
    parameter_name: string;
    current_value: number;
    proposed_value: number;
    feasible: boolean;
    constraint_message: string;
    evidence_source: string;
  }[];
  risk_before: number;
  risk_after: number;
  stabilization_before: number;
  stabilization_after: number;
  off_spec_seconds_before: number;
  off_spec_seconds_after: number;
  avoided_off_spec_seconds: number;
  confidence: number;
  baseline_trajectory: TrajectoryPrediction;
  counterfactual_trajectory: TrajectoryPrediction;
  evidence_tags: EvidenceTag[];
  guardrail: string;
}

export interface GroundedExplanation {
  mode: 'grounded-template' | 'grounded-template-fallback' | 'openai-grounded';
  model: string | null;
  headline: string;
  what_is_happening: string;
  why: string;
  suggested_response: string;
  operator_checks: string[];
  evidence: EvidenceTag[];
  guardrail: string;
}
