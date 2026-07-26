import { lazy, Suspense, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  Gauge,
  Droplets,
  Wind,
  Flame,
  Zap,
  Layers,
  Target,
  Play,
  Pause,
  SkipForward,
  ChevronRight,
  CheckCircle,
  BrainCircuit,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import {
  getGradeChange,
  getTimeseries,
  getAuditLog,
  getSnapshot,
  generateRecommendation,
  simulateRecommendation,
  getRecommendationOpportunities,
  acceptRecommendation,
  rejectRecommendation,
  modifyRecommendation,
  getCorrelations,
  explainState,
} from '../api/client'
import type { GroundedExplanation, Recommendation } from '../types'
const TrajectoryChart = lazy(() => import('../components/TrajectoryChart'))
const InfluenceGraph = lazy(() => import('../components/InfluenceGraph'))

/* =====================================================
   Animation Variants — staggered cascade reveals
   ===================================================== */

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
}

const itemVariants: any = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 300, damping: 24 }
  }
}

/* =====================================================
   Sub-Components
   ===================================================== */

function MetricCard({
  icon: Icon,
  label,
  value,
  unit,
  setpoint,
  deviation,
  status = 'stable',
}: {
  icon: React.ElementType
  label: string
  value: string
  unit: string
  setpoint?: string
  deviation?: string
  status?: 'stable' | 'warning' | 'critical'
}) {
  const statusConfig = {
    stable: { border: 'border-status-stable/20', glow: '', dot: 'bg-status-stable' },
    warning: { border: 'border-status-warning/25', glow: 'status-glow-warning', dot: 'bg-status-warning' },
    critical: { border: 'border-status-critical/30', glow: 'status-glow-critical', dot: 'bg-status-critical' },
  }[status]

  return (
    <motion.div
      variants={itemVariants}
      className={`panel p-4 ${statusConfig.glow} hover:border-panel-border transition-all`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-panel-elevated flex items-center justify-center">
            <Icon className="w-3.5 h-3.5 text-text-secondary" />
          </div>
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{label}</span>
        </div>
        <span className={`w-2 h-2 rounded-full ${statusConfig.dot} live-indicator`} />
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="data-value text-xl font-semibold">{value}</span>
        <span className="text-xs text-text-muted font-medium">{unit}</span>
      </div>
      {(setpoint || deviation) && (
        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-panel-border/50">
          {setpoint && (
            <span className="text-[0.6875rem] text-text-muted">
              SP: <span className="data-value text-text-secondary">{setpoint}</span>
            </span>
          )}
          {deviation && (
            <span className={`text-[0.6875rem] data-value font-medium ${
              status === 'critical' ? 'text-status-critical' :
              status === 'warning' ? 'text-status-warning' : 'text-status-stable'
            }`}>
              {deviation}
            </span>
          )}
        </div>
      )}
    </motion.div>
  )
}

function RootCauseItem({
  rank,
  parameter,
  contribution,
  rationale,
  isInteraction = false,
  delay = 0,
}: {
  rank: number
  parameter: string
  contribution: number
  rationale: string
  isInteraction?: boolean
  delay?: number
}) {
  const barColor = contribution > 25
    ? 'risk-fill-high'
    : contribution > 15
      ? 'risk-fill-moderate'
      : 'risk-fill-low'

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, type: 'spring', stiffness: 100, damping: 20 }}
      className="group"
    >
      <div className="flex items-center gap-3 mb-1.5">
        <span className="data-value text-[0.6875rem] text-text-muted w-4 text-right">#{rank}</span>
        <div className="flex-1 flex items-center gap-2">
          <span className="text-sm font-medium">{parameter}</span>
          {isInteraction && (
            <span className="evidence-tag !px-1.5 !py-0.5 !text-[0.625rem] text-accent border-accent/25 bg-accent/5">
              <Zap className="w-2.5 h-2.5" /> Compound
            </span>
          )}
        </div>
        <span className="data-value text-sm font-semibold">{contribution.toFixed(1)}%</span>
      </div>
      <div className="ml-7">
        <div className="risk-bar-bg h-1.5 mb-1.5">
          <motion.div
            className={`risk-bar-fill ${barColor}`}
            initial={{ width: 0 }}
            animate={{ width: `${contribution}%` }}
            transition={{ delay: delay + 0.2, duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
          />
        </div>
        <p className="text-[0.6875rem] text-text-muted leading-relaxed group-hover:text-text-secondary transition-colors">
          {rationale}
        </p>
      </div>
    </motion.div>
  )
}

/* =====================================================
   Command Center — Main Dashboard (Single Page)
   ===================================================== */

export default function CommandCenter() {
  const queryClient = useQueryClient()
  const [eventId, setEventId] = useState("EVT-003-RECOVERABLE")

  // 1. Fetch Event Info
  const { data: eventData } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getGradeChange(eventId),
    refetchInterval: 5000,
  })

  // 2. Fetch Timeseries Data
  const { data: timeseries } = useQuery({
    queryKey: ['timeseries', eventId],
    queryFn: () => getTimeseries(eventId),
    refetchInterval: 2000,
  })

  // Playback State
  const [playbackIndex, setPlaybackIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);

  // If eventId changes, reset playback
  useEffect(() => {
    setPlaybackIndex(-1);
    setIsPlaying(false);
  }, [eventId]);

  // Playback tick
  useEffect(() => {
    if (!isPlaying || !timeseries) return;
    const interval = setInterval(() => {
      setPlaybackIndex(prev => {
        const next = prev === -1 ? 0 : prev + 1;
        if (next >= timeseries.length) {
          setIsPlaying(false);
          return -1;
        }
        return next;
      });
    }, 500); // 500ms per tick for faster playback
    return () => clearInterval(interval);
  }, [isPlaying, timeseries]);

  const currentIndex = playbackIndex === -1 && timeseries ? timeseries.length - 1 : playbackIndex;
  const currentPoint = timeseries && currentIndex >= 0 && currentIndex < timeseries.length ? timeseries[currentIndex] : null;
  const visibleTimeseries = timeseries ? timeseries.slice(0, currentIndex + 1) : [];

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return `${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  };

  // Simulator State
  const [simulatedValue, setSimulatedValue] = useState<{ parameter: string, value: number } | null>(null)

  // 3. Unified Snapshot (Replaces individual ML queries)
  const { data: snapshot } = useQuery({
    queryKey: ['snapshot', eventId, currentPoint?.timestamp],
    queryFn: async () => {
      if (!currentPoint) return null;
      return getSnapshot(eventId, currentPoint.timestamp);
    },
    enabled: !!currentPoint,
  })

  // Extract from snapshot
  const riskData = snapshot?.risk;
  const trajectoryData = snapshot?.trajectory;
  const stabilizationData = snapshot?.stabilization;
  const rootCauses = snapshot?.root_causes;
  // Actually just store the generated rec in state to avoid query loop
  const [currentRec, setCurrentRec] = useState<Recommendation | null>(null)
  const [isRejecting, setIsRejecting] = useState(false)
  const [rejectionReason, setRejectionReason] = useState('')
  const [explanation, setExplanation] = useState<GroundedExplanation | null>(null)
  const [isExplaining, setIsExplaining] = useState(false)
  const [explanationError, setExplanationError] = useState('')
  const [preferLlm, setPreferLlm] = useState(false)

  // Recommendations are specific to one event/timestamp. Never carry an
  // operator action across to a different grade-change replay.
  useEffect(() => {
    setCurrentRec(null)
    setSimulatedValue(null)
    setIsRejecting(false)
    setRejectionReason('')
    setExplanation(null)
    setExplanationError('')
  }, [eventId, currentPoint?.timestamp])
  
  const generateRec = async () => {
    try {
      if (!currentPoint) return;
      const rec = await generateRecommendation({ event_id: eventId, timestamp: currentPoint.timestamp })
      setCurrentRec(rec)
      setExplanation(null)
      setSimulatedValue(
        rec.parameter_name === 'No intervention'
          ? null
          : { parameter: rec.parameter_name, value: rec.recommended_value }
      )
    } catch (e) {
      console.error(e)
    }
  }

  const explainCurrentState = async () => {
    if (!currentPoint) return
    setIsExplaining(true)
    setExplanationError('')
    try {
      const result = await explainState({
        event_id: eventId,
        timestamp: currentPoint.timestamp,
        recommendation_id: currentRec?.recommendation_id,
        prefer_llm: preferLlm,
      })
      setExplanation(result)
    } catch {
      setExplanationError('The selected point needs a complete 60-second history window before it can be explained.')
    } finally {
      setIsExplaining(false)
    }
  }

  const [debouncedSimulation, setDebouncedSimulation] = useState(simulatedValue)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSimulation(simulatedValue), 250)
    return () => window.clearTimeout(timer)
  }, [simulatedValue])

  const { data: simulation, isFetching: isSimulating } = useQuery({
    queryKey: [
      'simulation',
      eventId,
      currentPoint?.timestamp,
      debouncedSimulation?.parameter,
      debouncedSimulation?.value,
    ],
    queryFn: () => simulateRecommendation({
      event_id: eventId,
      timestamp: currentPoint!.timestamp,
      parameter_name: debouncedSimulation!.parameter,
      proposed_value: debouncedSimulation!.value,
    }),
    enabled: !!currentPoint && !!debouncedSimulation && currentRec?.parameter_name !== 'No intervention',
    staleTime: 10_000,
  })

  // 7. Action Mutations
  const acceptMutation = useMutation({
    mutationFn: (id: string) => acceptRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      setCurrentRec(null)
      setSimulatedValue(null)
      setIsRejecting(false)
      setRejectionReason('')
    }
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectRecommendation(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      setCurrentRec(null)
      setSimulatedValue(null)
    }
  })

  const modifyMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: number }) => modifyRecommendation(id, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      setCurrentRec(null)
      setSimulatedValue(null)
    }
  })

  // 8. Audit Log
  const { data: auditLog } = useQuery({
    queryKey: ['audit'],
    queryFn: () => getAuditLog(),
    refetchInterval: 5000,
  })
  
  // 9. Correlations for Influence Graph
  const { data: correlations } = useQuery({
    queryKey: ['correlations', eventId, currentPoint?.timestamp],
    queryFn: () => getCorrelations(eventId, currentPoint?.timestamp),
    enabled: !!eventId && !!currentPoint,
  })

  const { data: opportunities } = useQuery({
    queryKey: ['opportunities', eventId, currentPoint?.timestamp],
    queryFn: () => getRecommendationOpportunities(
      eventId,
      currentPoint!.timestamp,
    ),
    enabled: !!currentPoint && !isPlaying && (riskData?.probability ?? 0) >= 0.5,
    staleTime: 10_000,
  })

  const hasCorrectiveAction = currentRec?.parameter_name !== 'No intervention'
  const hasOperatorOverride = !!(
    currentRec
    && simulatedValue
    && Math.abs(simulatedValue.value - currentRec.recommended_value) > 0.001
  )
  const riskBefore = simulation?.risk_before ?? currentRec?.risk_before ?? 0
  const riskAfter = simulation?.risk_after ?? currentRec?.risk_after ?? 0
  const stabilizationBefore = simulation?.stabilization_before ?? currentRec?.stabilization_before ?? 0
  const stabilizationAfter = simulation?.stabilization_after ?? currentRec?.stabilization_after ?? 0
  const evidenceTags = simulation?.evidence_tags ?? currentRec?.evidence_tags ?? []
  const isCurrentlyOffSpec = currentPoint
    ? Math.abs(currentPoint.basis_weight_actual - currentPoint.basis_weight_setpoint)
      / currentPoint.basis_weight_setpoint > 0.025
    : false
  const violationTiming = riskData?.time_to_violation_seconds != null
    ? `~${Math.round(riskData.time_to_violation_seconds)}s`
    : isCurrentlyOffSpec
      ? 'Limit exceeded'
      : 'Not imminent'
  const specDeviationPct = riskData?.spec_deviation_pct ?? 2.5
  const decisionThreshold = riskData?.decision_threshold ?? 0.6
  const currentDeviationPct = currentPoint && currentPoint.basis_weight_setpoint
    ? Math.abs(
      currentPoint.basis_weight_actual - currentPoint.basis_weight_setpoint,
    ) / Math.abs(currentPoint.basis_weight_setpoint) * 100
    : 0
  const specificationMarginPct = specDeviationPct - currentDeviationPct
  const lowerSpecificationLimit = currentPoint
    ? currentPoint.basis_weight_setpoint * (1 - specDeviationPct / 100)
    : 0
  const upperSpecificationLimit = currentPoint
    ? currentPoint.basis_weight_setpoint * (1 + specDeviationPct / 100)
    : 0
  const noActionIsSafe = !hasCorrectiveAction
    && !isCurrentlyOffSpec
    && riskBefore < decisionThreshold
  const forecastEnvelope = (trajectoryData?.horizons ?? []).map((horizon) => {
    const deviationPct = Math.abs(
      horizon.predicted_bw - horizon.predicted_setpoint,
    ) / Math.max(Math.abs(horizon.predicted_setpoint), 1e-6) * 100
    return {
      ...horizon,
      deviationPct,
      withinSpecification: deviationPct <= specDeviationPct,
    }
  })
  const peakForecastDeviationPct = forecastEnvelope.length > 0
    ? Math.max(...forecastEnvelope.map((horizon) => horizon.deviationPct))
    : currentDeviationPct
  const forecastStaysInsideSpecification = forecastEnvelope.every(
    (horizon) => horizon.withinSpecification,
  )

  return (
    <motion.div
      className="p-5 md:p-8 space-y-5"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* ---- Page Header with Replay Controls ---- */}
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight">Command Center</h2>
            <span className={`text-[0.6rem] uppercase tracking-widest font-semibold px-2 py-0.5 rounded-full border flex items-center gap-1.5 ${
              riskData?.model_mode === 'trained'
                ? 'border-status-stable/30 bg-status-stable/10 text-status-stable'
                : 'border-status-warning/30 bg-status-warning/10 text-status-warning'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${
                riskData?.model_mode === 'trained' ? 'bg-status-stable' : 'bg-status-warning'
              }`} />
              {riskData?.model_mode === 'trained' ? 'Models Validated' : 'Model Status Pending'}
            </span>
          </div>
          <p className="text-sm text-text-muted mt-0.5">
            Monitor grade transitions · Predict risk · Act on recommendations
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Functional Event Selector */}
          <div className="panel px-3 py-1.5 text-xs flex items-center gap-2">
            <span className="text-text-muted">Event:</span>
            <select 
              value={eventId} 
              onChange={(e) => setEventId(e.target.value)}
              className="bg-transparent text-accent font-medium outline-none cursor-pointer appearance-none"
            >
              <option className="bg-surface" value="EVT-001-SUCCESS">A — Success</option>
              <option className="bg-surface" value="EVT-002-FAILURE">B — Failure</option>
              <option className="bg-surface" value="EVT-003-RECOVERABLE">C — Recoverable</option>
            </select>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted pointer-events-none" />
          </div>
          {/* Replay Controls */}
          <div className="flex items-center gap-1">
            <button 
              className={`btn btn-outline !p-2 !rounded-lg ${isPlaying ? 'bg-panel-hover' : ''}`} 
              title="Play"
              onClick={() => setIsPlaying(true)}
            >
              <Play className="w-3.5 h-3.5" />
            </button>
            <button 
              className={`btn btn-outline !p-2 !rounded-lg ${!isPlaying && playbackIndex !== -1 ? 'bg-panel-hover' : ''}`} 
              title="Pause"
              onClick={() => setIsPlaying(false)}
            >
              <Pause className="w-3.5 h-3.5" />
            </button>
            <button 
              className="btn btn-outline !p-2 !rounded-lg" 
              title="Skip"
              onClick={() => { setIsPlaying(false); setPlaybackIndex(-1); }}
            >
              <SkipForward className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="panel px-3 py-1.5 min-w-[110px] text-center">
            <span className="data-value text-xs text-text-secondary">
              <Clock className="w-3 h-3 inline-block mr-1 -mt-0.5 text-text-muted" />
              {currentPoint ? formatTime(currentPoint.timestamp) : '--:--'} / {timeseries && timeseries.length > 0 ? formatTime(timeseries[timeseries.length - 1].timestamp) : '--:--'}
            </span>
          </div>
        </div>
      </motion.div>

      {timeseries && timeseries.length > 0 && (
        <motion.div
          variants={itemVariants}
          className="panel px-4 py-2.5 flex items-center gap-3"
        >
          <span className="text-[0.625rem] uppercase tracking-wider font-medium text-text-muted whitespace-nowrap">
            Replay position
          </span>
          <input
            type="range"
            min={0}
            max={timeseries.length - 1}
            step={1}
            value={currentIndex}
            aria-label="Transition replay position"
            onChange={(event) => {
              setIsPlaying(false)
              setPlaybackIndex(Number(event.target.value))
            }}
            className="w-full accent-accent h-1.5 bg-panel-surface rounded-lg appearance-none cursor-pointer"
          />
          <input
            type="number"
            min={0}
            max={timeseries.length - 1}
            step={1}
            value={currentIndex}
            aria-label="Transition replay sample"
            onChange={(event) => {
              const requestedIndex = Number(event.target.value)
              if (!Number.isFinite(requestedIndex)) return
              setIsPlaying(false)
              setPlaybackIndex(Math.max(0, Math.min(timeseries.length - 1, Math.round(requestedIndex))))
            }}
            className="w-16 rounded border border-panel-border bg-panel-bg px-2 py-1 text-right data-value text-[0.625rem] text-text-secondary outline-none focus:border-accent"
          />
          <span className="data-value text-[0.625rem] text-text-muted tabular-nums whitespace-nowrap">
            {currentIndex + 1} / {timeseries.length}
          </span>
        </motion.div>
      )}

      {/* ---- Row 1: Trajectory Chart + Risk Panel ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Signature Element: Trajectory Chart — spans 8 columns */}
        <motion.div
          variants={itemVariants}
          className="lg:col-span-8 panel panel-accent p-5 min-h-[420px] flex flex-col"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold tracking-tight">Basis Weight Trajectory</h3>
              <p className="text-[0.6875rem] text-text-muted mt-0.5">
                Actual · Setpoint · ±2.5% Limits · Forecast
              </p>
            </div>
            <div className="flex items-center gap-4 text-[0.6875rem]">
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 rounded-full bg-chart-actual" /> Actual
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 rounded-full bg-chart-setpoint" style={{background: 'repeating-linear-gradient(90deg, #818cf8 0px, #818cf8 4px, transparent 4px, transparent 8px)'}} /> Setpoint
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 rounded-full bg-chart-forecast" style={{background: 'repeating-linear-gradient(90deg, #60a5fa 0px, #60a5fa 3px, transparent 3px, transparent 6px)'}} /> Forecast
              </span>
              {currentRec && (
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 rounded-full bg-chart-recommended" /> Recommended
                </span>
              )}
            </div>
          </div>
          <Suspense fallback={<div className="flex-1 skeleton" />}>
            <TrajectoryChart
              timeseries={visibleTimeseries}
              prediction={trajectoryData}
              counterfactual={simulation?.counterfactual_trajectory}
            />
          </Suspense>
        </motion.div>

        {/* Risk Panel — spans 4 columns */}
        <motion.div variants={itemVariants} className="lg:col-span-4 space-y-4">
          {/* Risk Score */}
          <div className="panel panel-accent p-5 status-glow-warning">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">
              Off-Spec Risk
            </h3>
            <div className="text-center mb-4">
              <div className="relative inline-flex items-center justify-center">
                {/* Circular indicator mock */}
                <svg className="w-28 h-28 -rotate-90" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(38,47,61,0.6)" strokeWidth="8" />
                  <motion.circle
                    cx="60" cy="60" r="50" fill="none"
                    stroke="url(#riskGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 50}
                    initial={{ strokeDashoffset: 2 * Math.PI * 50 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 50 * (1 - (riskData?.probability || 0)) }}
                    transition={{ duration: 1.2, ease: [0.34, 1.56, 0.64, 1], delay: 0.5 }}
                  />
                  <defs>
                    <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#fbbf24" />
                      <stop offset="100%" stopColor="#f87171" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="data-value text-2xl font-bold text-status-warning">
                    {riskData ? Math.round(riskData.probability * 100) : '--'}%
                  </span>
                  <span className="text-[0.625rem] text-text-muted font-medium uppercase tracking-wider">Risk</span>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <TrendingUp className="w-3 h-3 text-status-warning" /> Direction
                </span>
                <span className="data-value text-xs font-medium text-status-warning">{riskData?.direction || '--'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <Clock className="w-3 h-3 text-status-critical" /> Time to Violation
                </span>
                <span className={`data-value text-xs font-semibold ${
                  isCurrentlyOffSpec || riskData?.time_to_violation_seconds != null
                    ? 'text-status-critical'
                    : 'text-text-muted'
                }`}>
                  {violationTiming}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <Target className="w-3 h-3 text-text-muted" /> Model Mode
                </span>
                <span className={`data-value text-xs font-medium ${riskData?.model_mode === 'degraded' ? 'text-status-warning' : 'text-text-secondary'}`}>
                  {riskData?.model_mode === 'trained' ? 'Trained' : riskData?.model_mode === 'degraded' ? 'Degraded' : riskData?.model_mode || '--'}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Stabilization Estimate */}
          <div className="panel p-4">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
              Stabilization
            </h3>
            <div className="flex items-baseline gap-1.5 mb-1">
              {stabilizationData?.estimated_seconds !== undefined ? (
                <>
                  <span className="data-value text-lg font-semibold">{Math.round(stabilizationData.estimated_seconds / 60)}</span>
                  <span className="text-xs text-text-muted font-medium">min remaining</span>
                </>
              ) : eventData?.stabilization_seconds ? (
                <>
                  <span className="data-value text-lg font-semibold">{Math.round(eventData.stabilization_seconds / 60)}</span>
                  <span className="text-xs text-text-muted font-medium">min remaining</span>
                </>
              ) : (
                <span className="text-sm text-text-muted">Estimating...</span>
              )}
            </div>
            <p className="text-[0.6875rem] text-text-muted">
              {stabilizationData?.similar_events_used
                ? `Validated hybrid using ${stabilizationData.similar_events_used} comparable historical windows`
                : 'Chronologically validated model trained on grade-change history'}
            </p>
          </div>
        </motion.div>
      </div>

      {/* ---- Row 2: Parameter Overview ---- */}
      <motion.div variants={itemVariants}>
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 px-1">
          Process Parameters
        </h3>
        <motion.div
          className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <MetricCard icon={Layers} label="Basis Weight" value={currentPoint?.basis_weight_actual.toFixed(1) || '--'} unit="g/m²" setpoint={currentPoint?.basis_weight_setpoint.toFixed(1)} deviation={currentPoint ? `${((currentPoint.basis_weight_actual - currentPoint.basis_weight_setpoint)/currentPoint.basis_weight_setpoint * 100).toFixed(1)}%` : undefined} status="warning" />
          <MetricCard icon={Droplets} label="Stock Flow" value={currentPoint?.stock_flow_actual.toFixed(0) || '--'} unit="L/min" setpoint={currentPoint?.stock_flow_setpoint.toFixed(0)} deviation={currentPoint ? `${((currentPoint.stock_flow_actual - currentPoint.stock_flow_setpoint)/currentPoint.stock_flow_setpoint * 100).toFixed(1)}%` : undefined} status="warning" />
          <MetricCard icon={Wind} label="Filler Flow" value={currentPoint?.filler_flow_actual.toFixed(0) || '--'} unit="L/min" setpoint={currentPoint?.filler_flow_setpoint.toFixed(0)} deviation={currentPoint ? `${((currentPoint.filler_flow_actual - currentPoint.filler_flow_setpoint)/currentPoint.filler_flow_setpoint * 100).toFixed(1)}%` : undefined} status="stable" />
          <MetricCard icon={Flame} label="Steam Press" value={currentPoint?.steam_pressure_actual.toFixed(2) || '--'} unit="bar" setpoint={currentPoint?.steam_pressure_setpoint.toFixed(2)} deviation={currentPoint ? `${((currentPoint.steam_pressure_actual - currentPoint.steam_pressure_setpoint)/currentPoint.steam_pressure_setpoint * 100).toFixed(1)}%` : undefined} status="stable" />
          <MetricCard icon={Gauge} label="Machine Spd" value={currentPoint?.machine_speed_actual.toFixed(0) || '--'} unit="m/min" setpoint={currentPoint?.machine_speed_setpoint.toFixed(0)} deviation={currentPoint ? `${((currentPoint.machine_speed_actual - currentPoint.machine_speed_setpoint)/currentPoint.machine_speed_setpoint * 100).toFixed(1)}%` : undefined} status="warning" />
          <MetricCard icon={Droplets} label="Moisture" value={currentPoint?.moisture_actual.toFixed(1) || '--'} unit="%" setpoint={currentPoint?.moisture_setpoint.toFixed(1)} deviation={currentPoint ? `${((currentPoint.moisture_actual - currentPoint.moisture_setpoint)/currentPoint.moisture_setpoint * 100).toFixed(1)}%` : undefined} status="stable" />
          <MetricCard icon={Layers} label="Ash" value={currentPoint?.ash_actual.toFixed(1) || '--'} unit="%" setpoint={currentPoint?.ash_setpoint.toFixed(1)} deviation={currentPoint ? `${((currentPoint.ash_actual - currentPoint.ash_setpoint)/currentPoint.ash_setpoint * 100).toFixed(1)}%` : undefined} status="stable" />
          <MetricCard icon={Gauge} label="Caliper" value={currentPoint?.caliper_actual.toFixed(1) || '--'} unit="µm" setpoint={currentPoint?.caliper_setpoint.toFixed(1)} deviation={currentPoint ? `${((currentPoint.caliper_actual - currentPoint.caliper_setpoint)/currentPoint.caliper_setpoint * 100).toFixed(1)}%` : undefined} status="stable" />
        </motion.div>
      </motion.div>

      {/* ---- Grounded Operator Explanation ---- */}
      <motion.section variants={itemVariants} className="panel panel-accent p-5">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-status-predicted/10">
              <BrainCircuit className="h-5 w-5 text-status-predicted" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Operator Explanation</h3>
              <p className="mt-1 text-[0.6875rem] text-text-muted">
                Plain-language rendering of the current risk, local drivers, historical relationships, and constrained action.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-[0.6875rem] text-text-secondary">
              <input
                type="checkbox"
                checked={preferLlm}
                onChange={(event) => setPreferLlm(event.target.checked)}
                className="accent-accent"
              />
              Use configured LLM renderer
            </label>
            <button
              type="button"
              onClick={explainCurrentState}
              disabled={!currentPoint || isExplaining}
              className="btn btn-outline !px-3 !py-1.5 !text-[0.6875rem] disabled:opacity-45"
            >
              {explanation ? <RefreshCw className="h-3.5 w-3.5" /> : <BrainCircuit className="h-3.5 w-3.5" />}
              {isExplaining ? 'Explaining…' : explanation ? 'Refresh explanation' : 'Explain current state'}
            </button>
          </div>
        </div>

        {explanationError && (
          <p className="mt-4 rounded border border-status-critical/20 bg-status-critical/5 p-3 text-xs text-status-critical">
            {explanationError}
          </p>
        )}

        {explanation ? (
          <div className="mt-5">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-status-predicted/20 bg-status-predicted/5 p-4">
              <p className="text-base font-semibold">{explanation.headline}</p>
              <span className="evidence-tag text-status-predicted">
                {explanation.mode === 'openai-grounded'
                  ? `OpenAI grounded · ${explanation.model}`
                  : explanation.mode === 'grounded-template-fallback'
                    ? 'Verified template · LLM fallback'
                    : 'Verified deterministic template'}
              </span>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              {[
                ['What is happening', explanation.what_is_happening],
                ['Why the model thinks so', explanation.why],
                ['Suggested response', explanation.suggested_response],
              ].map(([label, text]) => (
                <div key={label} className="rounded border border-panel-border/50 bg-panel-bg/35 p-4">
                  <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-accent">{label}</p>
                  <p className="mt-2 text-xs leading-5 text-text-secondary">{text}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
              <div className="rounded border border-panel-border/50 bg-panel-bg/35 p-4">
                <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">Verify before acting</p>
                <div className="mt-2 space-y-2">
                  {explanation.operator_checks.map((check) => (
                    <p key={check} className="flex gap-2 text-[0.6875rem] leading-5 text-text-secondary">
                      <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-stable" />
                      {check}
                    </p>
                  ))}
                </div>
              </div>
              <div className="rounded border border-panel-border/50 bg-panel-bg/35 p-4">
                <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">Grounding sources</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {explanation.evidence.map((item, index) => (
                    <span
                      key={`${item.tag}-${index}`}
                      className="evidence-tag"
                      title={`${item.source}: ${item.detail}`}
                    >
                      {item.tag}
                    </span>
                  ))}
                </div>
                <p className="mt-3 flex gap-2 text-[0.625rem] leading-5 text-status-warning">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {explanation.guardrail}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded border border-dashed border-panel-border bg-panel-bg/30 p-5 text-center">
            <p className="text-xs text-text-secondary">
              Click “Explain current state” at any replay point. The deterministic mode works offline; the optional LLM only rewrites the same structured facts.
            </p>
          </div>
        )}
      </motion.section>

      {/* ---- Row 3: Root Cause + Recommendation ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Root Cause Analysis */}
        <motion.div variants={itemVariants} className="lg:col-span-5 panel panel-accent p-5">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
            Root Cause Analysis
          </h3>
          <p className="mb-5 mt-1 text-[0.6875rem] leading-5 text-text-muted">
            {riskData?.risk_level === 'low'
              ? `Relative attribution within a low-risk forecast (${Math.round(riskData.probability * 100)}% total risk); percentages are not absolute process impact.`
              : 'Percentages show each parameter’s share of the ranked local model attribution, not causal effect size.'}
          </p>
          <div className="space-y-5">
            {rootCauses?.map((cause, i) => (
              <RootCauseItem
                key={cause.parameter_name}
                rank={i + 1}
                parameter={cause.parameter_name}
                contribution={cause.contribution_pct * 100}
                rationale={cause.rationale}
                isInteraction={cause.is_interaction}
                delay={i * 0.12}
              />
            ))}
          </div>
          {opportunities && opportunities.length > 0 && (
            <div className="mt-6 pt-4 border-t border-panel-border/50">
              <p className="text-[0.625rem] text-text-muted uppercase tracking-wider font-medium mb-3">
                Stabilization Levers
              </p>
              <div className="space-y-2">
                {opportunities.slice(0, 3).map((item) => (
                  <div key={item.parameter_name} className="flex items-center justify-between text-xs bg-panel-bg/40 px-3 py-2 rounded border border-panel-border/40">
                    <span className="font-medium">{item.parameter_name}</span>
                    <span className="data-value text-status-stable">
                      −{Math.max(0, item.stabilization_before - item.stabilization_after).toFixed(0)}s · risk {Math.round(item.risk_after * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Recommendation Card */}
        <motion.div variants={itemVariants} className="lg:col-span-7 panel panel-accent p-5">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Recommended Action
            </h3>
            {currentRec ? (
              <span
                className="text-[0.625rem] font-medium text-accent bg-accent/8 px-2 py-0.5 rounded-full border border-accent/15"
                title="Composite data quality and model evidence score; not a calibrated probability."
              >
                Evidence confidence: {Math.round((simulation?.confidence ?? currentRec.confidence) * 100)}%
              </span>
            ) : (
              <button onClick={generateRec} className="btn btn-primary !py-1 !text-[0.6875rem]">
                <Zap className="w-3 h-3 mr-1" />
                Generate
              </button>
            )}
          </div>

          {/* Main Recommendation */}
          {currentRec ? (
            <>
              <div className="bg-panel-bg/60 rounded-xl p-4 mb-4 border border-panel-border/50">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-status-stable/10 flex items-center justify-center">
                    {!hasCorrectiveAction ? <CheckCircle className="w-4 h-4 text-status-stable" /> : simulatedValue !== null && simulatedValue.value < currentRec.current_value ? <TrendingDown className="w-4 h-4 text-status-stable" /> : <TrendingUp className="w-4 h-4 text-status-stable" />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold">
                      {!hasCorrectiveAction
                        ? noActionIsSafe
                          ? 'Operating Envelope Stable'
                          : 'Hold Setpoints — Operator Review'
                        : `${simulatedValue !== null && simulatedValue.value < currentRec.current_value ? 'Reduce' : 'Increase'} ${currentRec.parameter_name} Setpoint`}
                    </p>
                    <p className="mt-0.5 text-[0.6875rem] leading-5 text-text-muted">
                      {currentRec.rationale}
                    </p>
                    {simulation && simulation.avoided_off_spec_seconds >= 10 && (
                      <p className="text-[0.625rem] text-status-stable mt-1.5 font-medium bg-status-stable/10 border border-status-stable/20 px-2 py-0.5 rounded inline-block shadow-sm">
                        <TrendingDown className="w-2.5 h-2.5 inline mr-1" />
                        Projected off-spec exposure reduced by {simulation.avoided_off_spec_seconds.toFixed(0)}s
                      </p>
                    )}
                    {simulation && simulation.avoided_off_spec_seconds < 10 && (
                      <p className="text-[0.625rem] text-status-stable mt-1.5 font-medium bg-status-stable/10 border border-status-stable/20 px-2 py-0.5 rounded inline-block shadow-sm">
                        <TrendingDown className="w-2.5 h-2.5 inline mr-1" />
                        Projected risk reduced by {Math.max(0, (simulation.risk_before - simulation.risk_after) * 100).toFixed(1)} points · stabilization improved by {Math.max(0, simulation.stabilization_before - simulation.stabilization_after).toFixed(0)}s
                      </p>
                    )}
                  </div>
                </div>

                {!hasCorrectiveAction && (
                  <>
                    <div className="mt-5 grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg border border-status-stable/15 bg-status-stable/[0.04] p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Target className="h-3.5 w-3.5 text-status-stable" />
                            <span className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">
                              Basis Weight Safety Margin
                            </span>
                          </div>
                          <span className={`data-value text-xs font-semibold ${
                            specificationMarginPct >= 0
                              ? 'text-status-stable'
                              : 'text-status-critical'
                          }`}>
                            {specificationMarginPct >= 0 ? '+' : ''}
                            {specificationMarginPct.toFixed(2)} pp
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <p className="text-[0.625rem] text-text-muted">Current deviation</p>
                            <p className="mt-1 data-value text-base font-semibold">
                              {currentDeviationPct.toFixed(2)}%
                            </p>
                          </div>
                          <div>
                            <p className="text-[0.625rem] text-text-muted">Configured limit</p>
                            <p className="mt-1 data-value text-base font-semibold">
                              ±{specDeviationPct.toFixed(1)}%
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 border-t border-panel-border/40 pt-3">
                          <p className="text-[0.625rem] text-text-muted">Permitted basis-weight band</p>
                          <p className="mt-1 data-value text-xs text-text-secondary">
                            {lowerSpecificationLimit.toFixed(2)}–{upperSpecificationLimit.toFixed(2)} g/m²
                          </p>
                        </div>
                      </div>

                      <div className="rounded-lg border border-accent/15 bg-accent/[0.035] p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Gauge className="h-3.5 w-3.5 text-accent" />
                            <span className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">
                              Intervention Trigger
                            </span>
                          </div>
                          <span className="data-value text-xs font-semibold text-accent">
                            {Math.round(riskBefore * 100)}% / {Math.round(decisionThreshold * 100)}%
                          </span>
                        </div>
                        <div
                          className="h-2 overflow-hidden rounded-full bg-panel-surface"
                          role="progressbar"
                          aria-label="Risk relative to intervention threshold"
                          aria-valuemin={0}
                          aria-valuemax={Math.round(decisionThreshold * 100)}
                          aria-valuenow={Math.round(riskBefore * 100)}
                        >
                          <div
                            className={`h-full rounded-full ${
                              riskBefore >= decisionThreshold
                                ? 'bg-status-critical'
                                : 'bg-status-stable'
                            }`}
                            style={{
                              width: `${Math.min(
                                100,
                                riskBefore / Math.max(decisionThreshold, 0.01) * 100,
                              )}%`,
                            }}
                          />
                        </div>
                        <p className="mt-3 text-[0.6875rem] leading-5 text-text-secondary">
                          Escalate when 120-second risk reaches{' '}
                          <span className="data-value font-semibold text-text-primary">
                            {Math.round(decisionThreshold * 100)}%
                          </span>{' '}
                          or projected deviation reaches{' '}
                          <span className="data-value font-semibold text-text-primary">
                            ±{specDeviationPct.toFixed(1)}%
                          </span>.
                        </p>
                        <div className="mt-3 flex items-center justify-between border-t border-panel-border/40 pt-3 text-[0.625rem]">
                          <span className="text-text-muted">Scanner quality</span>
                          <span className="data-value text-text-secondary">
                            {Math.round((currentPoint?.scanner_quality_score ?? 0) * 100)}%
                            {' · '}
                            {currentPoint?.active_alarm_count ?? 0} active alarm(s)
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 rounded-lg border border-panel-border/50 bg-panel-surface/25 p-4">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">
                            Forward Safety Check
                          </p>
                          <p className="mt-1 text-[0.6875rem] text-text-secondary">
                            Learned trajectory forecast compared with the active basis-weight specification.
                          </p>
                        </div>
                        <span className={`rounded-full border px-2 py-1 text-[0.625rem] font-medium ${
                          forecastStaysInsideSpecification
                            ? 'border-status-stable/20 bg-status-stable/10 text-status-stable'
                            : 'border-status-critical/20 bg-status-critical/10 text-status-critical'
                        }`}>
                          Peak projected deviation {peakForecastDeviationPct.toFixed(2)}%
                        </span>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-3">
                        {forecastEnvelope.map((horizon) => (
                          <div
                            key={horizon.seconds}
                            className="rounded-md border border-panel-border/40 bg-panel-bg/50 px-3 py-2.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="data-value text-xs font-semibold">
                                +{horizon.seconds}s
                              </span>
                              <span className={`text-[0.625rem] font-medium ${
                                horizon.withinSpecification
                                  ? 'text-status-stable'
                                  : 'text-status-critical'
                              }`}>
                                {horizon.withinSpecification ? 'Within limit' : 'Limit risk'}
                              </span>
                            </div>
                            <p className="mt-2 data-value text-sm">
                              {horizon.predicted_bw.toFixed(2)} g/m²
                            </p>
                            <p className="mt-1 text-[0.625rem] text-text-muted">
                              {horizon.deviationPct.toFixed(2)}% from projected setpoint
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className={`mt-3 flex items-start gap-2 rounded-lg border px-3 py-2.5 ${
                      noActionIsSafe
                        ? 'border-status-stable/15 bg-status-stable/[0.035]'
                        : 'border-status-warning/20 bg-status-warning/[0.04]'
                    }`}>
                      <ShieldCheck className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                        noActionIsSafe ? 'text-status-stable' : 'text-status-warning'
                      }`} />
                      <p className="text-[0.6875rem] leading-5 text-text-secondary">
                        <span className="font-semibold text-text-primary">
                          Monitoring plan:
                        </span>{' '}
                        Hold current setpoints and re-evaluate on every new scanner sample.
                        Escalate immediately if the risk trigger, specification limit, scanner-quality,
                        or alarm guardrail changes.
                      </p>
                    </div>
                  </>
                )}

                {hasCorrectiveAction && <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Current</p>
                    <p className="data-value text-base font-semibold">{currentRec.current_value.toFixed(1)}</p>
                  </div>
                  <div className="bg-status-stable/5 rounded-lg p-3 text-center border border-status-stable/15 relative">
                    <p className="text-[0.625rem] text-status-stable mb-1 uppercase tracking-wider font-medium">
                      {hasOperatorOverride ? 'Operator Override' : 'Recommended'}
                    </p>
                    <p className="data-value text-base font-bold text-status-stable">{simulatedValue?.value.toFixed(1)}</p>
                  </div>
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Sim Ramp</p>
                    <p className="data-value text-base font-semibold">
                      {simulatedValue !== null ? ((simulatedValue.value - currentRec.current_value) / 15.0).toFixed(2) : currentRec.recommended_ramp_rate.toFixed(2)}
                    </p>
                    <p className="text-[0.625rem] text-text-muted">/s</p>
                  </div>
                </div>}

                {/* Simulator Slider */}
                {hasCorrectiveAction && <div className="mb-5 px-1">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[0.6875rem] text-text-muted font-medium">Setpoint Simulator Override</span>
                    <span className="text-[0.625rem] text-accent">
                      {isSimulating ? 'Recalculating…' : simulation?.feasible ? 'Counterfactual Ready' : 'Checking Constraints'}
                    </span>
                  </div>
                  <input 
                    type="range" 
                    min={currentRec.current_value * 0.9} 
                    max={currentRec.current_value * 1.1} 
                    step="any"
                    aria-label={`${currentRec.parameter_name} simulated setpoint`}
                    value={simulatedValue?.value ?? currentRec.recommended_value}
                    onChange={(e) => setSimulatedValue({ parameter: currentRec.parameter_name, value: Number(e.target.value) })}
                    className="w-full accent-accent h-1.5 bg-panel-surface rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-[0.625rem] text-text-muted mt-1">
                    <span>-10%</span>
                    <span>Engine Default: {currentRec.recommended_value}</span>
                    <span>+10%</span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <label
                      htmlFor="simulated-setpoint-value"
                      className="text-[0.625rem] text-text-muted"
                    >
                      Precise override
                    </label>
                    <input
                      id="simulated-setpoint-value"
                      type="number"
                      min={currentRec.current_value * 0.9}
                      max={currentRec.current_value * 1.1}
                      step="any"
                      value={simulatedValue?.value ?? currentRec.recommended_value}
                      aria-label={`${currentRec.parameter_name} simulated setpoint value`}
                      onChange={(event) => {
                        if (event.target.value === '') return
                        setSimulatedValue({
                          parameter: currentRec.parameter_name,
                          value: Number(event.target.value),
                        })
                      }}
                      className="w-28 rounded border border-panel-border bg-panel-bg px-2 py-1 text-right data-value text-[0.6875rem] text-text-secondary outline-none focus:border-accent"
                    />
                    <span className="text-[0.625rem] text-text-muted">
                      Enter an exact operator setpoint
                    </span>
                  </div>
                  {simulation && (
                    <p className={`text-[0.625rem] mt-2 ${simulation.feasible ? 'text-status-stable' : 'text-status-critical'}`}>
                      {simulation.constraint_message}
                    </p>
                  )}
                </div>}

                {/* Before / After Metrics */}
                {hasCorrectiveAction && <div className={`grid ${simulation ? 'grid-cols-3' : 'grid-cols-2'} gap-3`}>
                  <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                    <span className="text-[0.6875rem] text-text-muted">Horizon Risk</span>
                    <div className="flex items-center gap-2">
                      <span className="data-value text-xs text-status-warning">{Math.round(riskBefore * 100)}%</span>
                      <ChevronRight className="w-3 h-3 text-text-muted" />
                      <span className="data-value text-xs text-status-stable font-semibold">{Math.round(riskAfter * 100)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                    <span className="text-[0.6875rem] text-text-muted">Stabilization</span>
                    <div className="flex items-center gap-2">
                      <span className="data-value text-xs text-text-secondary">{(stabilizationBefore / 60).toFixed(1)}m</span>
                      <ChevronRight className="w-3 h-3 text-text-muted" />
                      <span className="data-value text-xs text-status-stable font-semibold">{(stabilizationAfter / 60).toFixed(1)}m</span>
                    </div>
                  </div>
                  {simulation && (
                    <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                      <span className="text-[0.6875rem] text-text-muted">Off-spec</span>
                      <div className="flex items-center gap-2">
                        <span className="data-value text-xs text-status-warning">{simulation.off_spec_seconds_before.toFixed(0)}s</span>
                        <ChevronRight className="w-3 h-3 text-text-muted" />
                        <span className="data-value text-xs text-status-stable font-semibold">{simulation.off_spec_seconds_after.toFixed(0)}s</span>
                      </div>
                    </div>
                  )}
                </div>}
              </div>

              {/* Evidence Tags */}
              <div className="mb-5">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="text-[0.625rem] font-medium uppercase tracking-wider text-text-muted">
                    Evidence Sources
                  </p>
                  {!hasCorrectiveAction && (
                    <span className="text-[0.625rem] text-text-muted">
                      Every conclusion is traceable to its inference source
                    </span>
                  )}
                </div>
                {!hasCorrectiveAction ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {evidenceTags.map((tag) => (
                      <div
                        key={`${tag.tag}-${tag.source}`}
                        className="rounded-lg border border-panel-border/50 bg-panel-bg/40 p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="evidence-tag !px-1.5 !py-0.5 !text-[0.625rem]">
                            {tag.tag}
                          </span>
                          <span className="text-right text-[0.6rem] uppercase tracking-wide text-text-muted">
                            Source of inference
                          </span>
                        </div>
                        <p className="mt-2 text-[0.6875rem] font-medium leading-5 text-text-secondary">
                          {tag.source}
                        </p>
                        <p className="mt-1 text-[0.625rem] leading-5 text-text-muted">
                          {tag.detail}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {evidenceTags.map((tag) => (
                      <span
                        key={tag.tag}
                        className="evidence-tag"
                        title={`${tag.source}: ${tag.detail}`}
                      >
                        {tag.tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => acceptMutation.mutate(currentRec.recommendation_id)}
                  className="btn btn-primary flex-1"
                  disabled={acceptMutation.isPending}
                >
                  {acceptMutation.isPending
                    ? hasCorrectiveAction ? 'Accepting...' : 'Recording...'
                    : hasCorrectiveAction
                      ? 'Accept Recommendation'
                      : noActionIsSafe
                        ? 'Acknowledge & Monitor'
                        : 'Acknowledge Setpoint Hold'}
                </button>
                <button 
                  onClick={() => setIsRejecting(true)}
                  className="btn btn-danger"
                  disabled={rejectMutation.isPending}
                >
                  {hasCorrectiveAction ? 'Reject' : 'Flag for Review'}
                </button>
                {hasCorrectiveAction && (
                  <button
                    onClick={() => modifyMutation.mutate({ id: currentRec.recommendation_id, value: simulatedValue?.value ?? currentRec.recommended_value })}
                    className="btn btn-outline"
                    disabled={modifyMutation.isPending || simulation?.feasible === false}
                  >
                    {modifyMutation.isPending ? 'Modifying...' : 'Modify'}
                  </button>
                )}
              </div>
              {isRejecting && (
                <div className="mt-3 rounded-lg border border-status-critical/20 bg-status-critical/5 p-3">
                  <label
                    htmlFor="rejection-reason"
                    className="block text-[0.6875rem] font-medium text-text-secondary mb-2"
                  >
                    {hasCorrectiveAction
                      ? 'Rejection reason'
                      : 'Why should this state be reviewed?'}
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id="rejection-reason"
                      type="text"
                      value={rejectionReason}
                      placeholder={hasCorrectiveAction
                        ? 'Record why this action is not appropriate'
                        : 'Record the operator concern or conflicting field observation'}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      className="flex-1 rounded border border-panel-border bg-panel-bg px-3 py-2 text-xs text-text-primary outline-none focus:border-status-critical"
                    />
                    <button
                      onClick={() => rejectMutation.mutate({
                        id: currentRec.recommendation_id,
                        reason: rejectionReason.trim(),
                      })}
                      className="btn btn-danger whitespace-nowrap"
                      disabled={rejectMutation.isPending || !rejectionReason.trim()}
                    >
                      {rejectMutation.isPending
                        ? 'Recording...'
                        : hasCorrectiveAction
                          ? 'Confirm Rejection'
                          : 'Record Review Request'}
                    </button>
                    <button
                      onClick={() => {
                        setIsRejecting(false)
                        setRejectionReason('')
                      }}
                      className="btn btn-outline"
                      disabled={rejectMutation.isPending}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-panel-bg/60 rounded-xl p-8 border border-panel-border/50 text-center text-text-muted">
              Click Generate to analyze constraints and produce an action.
            </div>
          )}
        </motion.div>
      </div>

      {/* ---- Row 4: Audit Table ---- */}
      <motion.div variants={itemVariants} className="panel p-5">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">
          Decision Audit Log
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-panel-border/50">
                <th className="pb-3 text-left text-[0.6875rem] text-text-muted font-medium uppercase tracking-wider">Timestamp</th>
                <th className="pb-3 text-left text-[0.6875rem] text-text-muted font-medium uppercase tracking-wider">Parameter</th>
                <th className="pb-3 text-left text-[0.6875rem] text-text-muted font-medium uppercase tracking-wider">Value</th>
                <th className="pb-3 text-left text-[0.6875rem] text-text-muted font-medium uppercase tracking-wider">Response</th>
                <th className="pb-3 text-left text-[0.6875rem] text-text-muted font-medium uppercase tracking-wider">Source</th>
              </tr>
            </thead>
            <tbody>
              {auditLog && auditLog.length > 0 ? (
                auditLog.map((log: any) => {
                  const isNoActionDecision = log.recommendation?.parameter_name === 'No intervention'
                  const responseLabel = isNoActionDecision
                    ? log.response === 'accept'
                      ? 'Monitoring acknowledged'
                      : log.response === 'reject'
                        ? 'Review requested'
                        : 'Operator updated'
                    : log.response === 'accept'
                      ? 'Accepted'
                      : log.response === 'reject'
                        ? 'Rejected'
                        : log.response === 'modify'
                          ? 'Modified'
                          : log.response

                  return (
                    <tr key={log.feedback_id} className="border-b border-panel-border/30">
                      <td className="py-3 data-value text-[0.6875rem]">{new Date(log.timestamp).toLocaleTimeString()}</td>
                      <td className="py-3 text-[0.8125rem] font-medium">
                        {isNoActionDecision
                          ? 'Continue monitoring'
                          : log.recommendation?.parameter_name || 'N/A'}
                      </td>
                      <td className="py-3 data-value text-[0.8125rem]">
                        {isNoActionDecision
                          ? '—'
                          : log.recommendation?.recommended_value != null
                            ? log.recommendation.recommended_value.toFixed(1)
                            : '--'}
                      </td>
                      <td className="py-3">
                        <span className={`inline-flex items-center gap-1 text-[0.625rem] font-medium px-2 py-0.5 rounded-full ${
                          log.response === 'accept'
                            ? 'bg-status-stable/10 text-status-stable border border-status-stable/20'
                            : log.response === 'modify'
                              ? 'bg-accent/10 text-accent border border-accent/20'
                              : 'bg-status-critical/10 text-status-critical border border-status-critical/20'
                        }`}>
                          {log.response === 'accept' ? <CheckCircle className="w-2.5 h-2.5" /> : <AlertTriangle className="w-2.5 h-2.5" />}
                          {responseLabel}
                        </span>
                      </td>
                      <td className="py-3 text-[0.6875rem] text-text-muted">Operator</td>
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={5} className="py-10 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-10 h-10 rounded-full bg-panel-elevated flex items-center justify-center">
                        <AlertTriangle className="w-4 h-4 text-text-muted" />
                      </div>
                      <p className="text-sm text-text-muted">No recommendations acted on yet</p>
                      <p className="text-[0.6875rem] text-text-muted/60">
                        Decisions will appear here as operators accept, reject, or modify suggestions
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </motion.div>
      {/* ---- Row 5: Influence Graph ---- */}
      <motion.div variants={itemVariants} className="panel p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Parameter Influence Map
            </h3>
            <p className="text-[0.6875rem] text-text-muted mt-1">
              Which process parameters are driving Basis Weight — and whether the relationship is expected or novel
            </p>
          </div>
          <span className="evidence-tag bg-accent/10 border-accent/20 text-accent">{correlations?.length ?? 0} Relationships</span>
        </div>
        <Suspense fallback={<div className="h-[380px] skeleton" />}>
          <InfluenceGraph correlations={correlations || []} />
        </Suspense>
      </motion.div>
    </motion.div>
  )
}
