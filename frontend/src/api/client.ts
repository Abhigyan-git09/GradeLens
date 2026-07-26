import axios from 'axios';
import type {
  GradeChangeEvent,
  TimeseriesPoint,
  RiskPrediction,
  TrajectoryPrediction,
  StabilizationPrediction,
  RootCause,
  Recommendation,
  OperatorFeedback,
  HealthStatus,
  AuditEntry,
  DiscoveredRelationship,
  SimulationResult,
  DataOverview,
  DataValidationResult,
  RecipeConstraint,
  ScenarioResult,
  GroundedExplanation,
} from '../types';

export interface SnapshotResponse {
  event: GradeChangeEvent;
  timeseries: TimeseriesPoint[];
  current_features?: Record<string, number>;
  risk?: RiskPrediction;
  trajectory?: TrajectoryPrediction;
  stabilization?: StabilizationPrediction;
  root_causes: RootCause[];
  recommendation?: Recommendation;
  correlations: DiscoveredRelationship[];
}

// In dev, Vite proxy handles /api → localhost:8000
// In production, the container proxy serves the same /api contract.
const BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  withCredentials: false,
  headers: { 'Content-Type': 'application/json' },
});

// ---- Health ----
export const getHealth = () =>
  api.get<HealthStatus>('/health').then((r) => r.data);

// ---- Grade Changes ----
export const getGradeChanges = () =>
  api.get<GradeChangeEvent[]>('/grade-changes').then((r) => r.data);

export const getGradeChange = (eventId: string) =>
  api.get<GradeChangeEvent>(`/grade-changes/${eventId}`).then((r) => r.data);

export const getTimeseries = (eventId: string) =>
  api.get<TimeseriesPoint[]>(`/grade-changes/${eventId}/timeseries`).then((r) => r.data);

// ---- Snapshot ----
export const getSnapshot = (eventId: string, timestamp: string) =>
  api.get<SnapshotResponse>(`/grade-changes/${eventId}/snapshot`, { params: { timestamp } }).then((r) => r.data);



// ---- Recommendations ----
export const getRecommendations = (eventId: string) =>
  api.get<Recommendation[]>(`/grade-changes/${eventId}/recommendations`).then((r) => r.data);

export const generateRecommendation = (data: { event_id: string; timestamp: string }) =>
  api.post<Recommendation>('/recommendations/generate', data).then((r) => r.data);

export const simulateRecommendation = (data: {
  event_id: string;
  timestamp: string;
  parameter_name: string;
  proposed_value: number;
}) => api.post<SimulationResult>('/recommendations/simulate', data).then((r) => r.data);

export const getRecommendationOpportunities = (
  eventId: string,
  timestamp: string,
) => api.get<SimulationResult[]>('/recommendations/opportunities', {
  params: { event_id: eventId, timestamp },
}).then((r) => r.data);

export const acceptRecommendation = (id: string) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/accept`).then((r) => r.data);

export const rejectRecommendation = (id: string, reason: string) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/reject`, { reason }).then((r) => r.data);

export const modifyRecommendation = (id: string, value: number) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/modify`, { value }).then((r) => r.data);

// ---- Correlations (stretch) ----
export const getCorrelations = (eventId: string, timestamp?: string) =>
  api.get<DiscoveredRelationship[]>('/correlations', {
    params: { event_id: eventId, timestamp },
  }).then((r) => r.data);

// ---- Audit ----
export const getAuditLog = () =>
  api.get<AuditEntry[]>('/audit/recommendations').then((r) => r.data);

// ---- Data, Evidence & Scenario Intelligence ----
export const getDataOverview = () =>
  api.get<DataOverview>('/intelligence/data/overview').then((r) => r.data);

export const getRecipeConstraints = (gradeId: string) =>
  api.get<RecipeConstraint[]>(`/intelligence/recipes/${gradeId}`).then((r) => r.data);

export const validateDataset = (data: {
  file_name: string;
  columns: string[];
  rows: Record<string, unknown>[];
}) => api.post<DataValidationResult>('/intelligence/data/validate', data).then((r) => r.data);

export const runScenario = (data: {
  event_id: string;
  timestamp: string;
  adjustments: { parameter_name: string; proposed_value: number }[];
}) => api.post<ScenarioResult>('/intelligence/scenarios/run', data).then((r) => r.data);

export const explainState = (data: {
  event_id: string;
  timestamp: string;
  recommendation_id?: string;
  prefer_llm?: boolean;
}) => api.post<GroundedExplanation>('/intelligence/explain', data).then((r) => r.data);

export default api;
