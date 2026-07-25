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
} from '../types';

// In dev, Vite proxy handles /api → localhost:8000
// In prod, set VITE_API_URL to the Render backend URL
const BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: BASE_URL,
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

// ---- Predictions ----
export const getRiskPrediction = (data: Record<string, number>) =>
  api.post<RiskPrediction>('/predictions/risk', data).then((r) => r.data);

export const getTrajectoryPrediction = (data: Record<string, number>) =>
  api.post<TrajectoryPrediction>('/predictions/trajectory', data).then((r) => r.data);

export const getStabilizationPrediction = (data: Record<string, number>) =>
  api.post<StabilizationPrediction>('/predictions/stabilization', data).then((r) => r.data);

// ---- Root Causes ----
export const getRootCauses = (eventId: string) =>
  api.get<RootCause[]>(`/grade-changes/${eventId}/root-causes`).then((r) => r.data);

// ---- Recommendations ----
export const getRecommendations = (eventId: string) =>
  api.get<Recommendation[]>(`/grade-changes/${eventId}/recommendations`).then((r) => r.data);

export const generateRecommendation = (data: { event_id: string; timestamp: string }) =>
  api.post<Recommendation>('/recommendations/generate', data).then((r) => r.data);

export const acceptRecommendation = (id: string) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/accept`).then((r) => r.data);

export const rejectRecommendation = (id: string, reason: string) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/reject`, { reason }).then((r) => r.data);

export const modifyRecommendation = (id: string, value: number) =>
  api.post<OperatorFeedback>(`/recommendations/${id}/modify`, { value }).then((r) => r.data);

// ---- Correlations (stretch) ----
export const getCorrelations = (eventId: string) =>
  api.get<DiscoveredRelationship[]>('/correlations', { params: { event_id: eventId } }).then((r) => r.data);

// ---- Audit ----
export const getAuditLog = () =>
  api.get<AuditEntry[]>('/audit/recommendations').then((r) => r.data);

export default api;
