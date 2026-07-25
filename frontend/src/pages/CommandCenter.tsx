import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
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
} from 'lucide-react'
import {
  getGradeChange,
  getTimeseries,
  getRootCauses,
  getAuditLog,
  getRiskPrediction,
  getTrajectoryPrediction,
  generateRecommendation,
  acceptRecommendation,
  rejectRecommendation,
} from '../api/client'
import TrajectoryChart from '../components/TrajectoryChart'

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

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 100, damping: 20 },
  },
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
        <span className="data-value text-sm font-semibold">{contribution}%</span>
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
  const eventId = "EVT-003-RECOVERABLE"

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

  const currentPoint = timeseries && timeseries.length > 0 ? timeseries[timeseries.length - 1] : null

  // 3. Live Risk Prediction
  const { data: riskData } = useQuery({
    queryKey: ['risk', eventId, currentPoint?.timestamp],
    queryFn: async () => {
      if (!currentPoint) return null;
      // Synthesize feature vector from latest point and recent slope (mock slope for frontend)
      const prevPoint = timeseries && timeseries.length > 5 ? timeseries[timeseries.length - 5] : currentPoint;
      return getRiskPrediction({
        bw_deviation: currentPoint.basis_weight_actual - currentPoint.basis_weight_setpoint,
        bw_slope: (currentPoint.basis_weight_actual - prevPoint.basis_weight_actual) / 5.0,
        stock_flow_ramp: (currentPoint.stock_flow_actual - prevPoint.stock_flow_actual) / 5.0,
        interaction_feature: 0.0, // Default for now
        current_bw: currentPoint.basis_weight_actual
      })
    },
    enabled: !!currentPoint,
  })

  // 4. Live Trajectory Prediction
  const { data: trajectoryData } = useQuery({
    queryKey: ['trajectory', eventId, currentPoint?.timestamp],
    queryFn: async () => {
      if (!currentPoint) return null;
      const prevPoint = timeseries && timeseries.length > 5 ? timeseries[timeseries.length - 5] : currentPoint;
      return getTrajectoryPrediction({
        bw_deviation: currentPoint.basis_weight_actual - currentPoint.basis_weight_setpoint,
        bw_slope: (currentPoint.basis_weight_actual - prevPoint.basis_weight_actual) / 5.0,
        stock_flow_ramp: (currentPoint.stock_flow_actual - prevPoint.stock_flow_actual) / 5.0,
        current_bw: currentPoint.basis_weight_actual
      })
    },
    enabled: !!currentPoint,
  })

  // 5. Root Causes
  const { data: rootCauses } = useQuery({
    queryKey: ['rootCauses', eventId],
    queryFn: () => getRootCauses(eventId),
    refetchInterval: 5000,
  })

  // 6. Generate Recommendation State
  const [activeRecId, setActiveRecId] = useState<string | null>(null)
  
  const generateMutation = useMutation({
    mutationFn: () => generateRecommendation({ event_id: eventId, timestamp: new Date().toISOString() }),
    onSuccess: (data) => setActiveRecId(data.recommendation_id)
  })

  const { data: recommendation } = useQuery({
    queryKey: ['recommendation', activeRecId],
    queryFn: () => activeRecId ? generateMutation.mutateAsync() : null, // Not strictly best practice but works for flow
    enabled: false // We manually manage this
  })
  
  // Actually just store the generated rec in state to avoid query loop
  const [currentRec, setCurrentRec] = useState<any>(null)
  
  const generateRec = async () => {
    try {
      const rec = await generateRecommendation({ event_id: eventId, timestamp: new Date().toISOString() })
      setCurrentRec(rec)
    } catch (e) {
      console.error(e)
    }
  }

  // 7. Action Mutations
  const acceptMutation = useMutation({
    mutationFn: (id: string) => acceptRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      setCurrentRec(null)
    }
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectRecommendation(id, "Operator override"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      setCurrentRec(null)
    }
  })

  // 8. Audit Log
  const { data: auditLog } = useQuery({
    queryKey: ['audit'],
    queryFn: () => getAuditLog(),
    refetchInterval: 5000,
  })

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
          <h2 className="text-lg font-semibold tracking-tight">Command Center</h2>
          <p className="text-sm text-text-muted mt-0.5">
            Monitor grade transitions · Predict risk · Act on recommendations
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Event Selector Stub */}
          <div className="panel px-3 py-1.5 text-xs flex items-center gap-2">
            <span className="text-text-muted">Event:</span>
            <span className="data-value font-medium text-accent">C — Recoverable</span>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted" />
          </div>
          {/* Replay Controls */}
          <div className="flex items-center gap-1">
            <button className="btn btn-outline !p-2 !rounded-lg" title="Play">
              <Play className="w-3.5 h-3.5" />
            </button>
            <button className="btn btn-outline !p-2 !rounded-lg" title="Pause">
              <Pause className="w-3.5 h-3.5" />
            </button>
            <button className="btn btn-outline !p-2 !rounded-lg" title="Skip">
              <SkipForward className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="panel px-3 py-1.5">
            <span className="data-value text-xs text-text-secondary">
              <Clock className="w-3 h-3 inline-block mr-1 -mt-0.5 text-text-muted" />
              07:34 / 18:00
            </span>
          </div>
        </div>
      </motion.div>

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
          <TrajectoryChart 
            timeseries={timeseries || []} 
            prediction={trajectoryData}
            recommendation={currentRec}
          />
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
                <span className="data-value text-xs font-semibold text-status-critical">~{riskData?.time_to_violation_seconds ? Math.round(riskData.time_to_violation_seconds) : '--'}s</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <Target className="w-3 h-3 text-text-muted" /> Model Mode
                </span>
                <span className="data-value text-xs font-medium text-text-secondary">Trained</span>
              </div>
            </div>
          </div>

          {/* Quick Stabilization Estimate */}
          <div className="panel p-4">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
              Stabilization
            </h3>
            <div className="flex items-baseline gap-1.5 mb-1">
              <span className="data-value text-lg font-semibold">{eventData ? Math.round(eventData.stabilization_seconds! / 60) : '--'}</span>
              <span className="text-xs text-text-muted font-medium">min remaining</span>
            </div>
            <p className="text-[0.6875rem] text-text-muted">
              Based on {eventData?.transition_outcome === 'SUCCESS' ? 4 : 2} similar transitions (k-NN)
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
          className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3"
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
        </motion.div>
      </motion.div>

      {/* ---- Row 3: Root Cause + Recommendation ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Root Cause Analysis */}
        <motion.div variants={itemVariants} className="lg:col-span-5 panel panel-accent p-5">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-5">
            Root Cause Analysis
          </h3>
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
        </motion.div>

        {/* Recommendation Card */}
        <motion.div variants={itemVariants} className="lg:col-span-7 panel panel-accent p-5">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Recommended Action
            </h3>
            {currentRec ? (
              <span className="text-[0.625rem] font-medium text-accent bg-accent/8 px-2 py-0.5 rounded-full border border-accent/15">
                Confidence: {Math.round(currentRec.confidence * 100)}%
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
                    {currentRec.recommended_value < currentRec.current_value ? <TrendingDown className="w-4 h-4 text-status-stable" /> : <TrendingUp className="w-4 h-4 text-status-stable" />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold">{currentRec.recommended_value < currentRec.current_value ? 'Reduce' : 'Increase'} {currentRec.parameter_name} Setpoint</p>
                    <p className="text-[0.6875rem] text-text-muted">{currentRec.rationale}</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Current</p>
                    <p className="data-value text-base font-semibold">{currentRec.current_value}</p>
                  </div>
                  <div className="bg-status-stable/5 rounded-lg p-3 text-center border border-status-stable/15">
                    <p className="text-[0.625rem] text-status-stable mb-1 uppercase tracking-wider font-medium">Recommended</p>
                    <p className="data-value text-base font-bold text-status-stable">{currentRec.recommended_value}</p>
                  </div>
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Ramp Rate</p>
                    <p className="data-value text-base font-semibold">{currentRec.recommended_ramp_rate}</p>
                    <p className="text-[0.625rem] text-text-muted">/s</p>
                  </div>
                </div>

                {/* Before / After Metrics */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                    <span className="text-[0.6875rem] text-text-muted">Risk</span>
                    <div className="flex items-center gap-2">
                      <span className="data-value text-xs text-status-warning">{Math.round(currentRec.risk_before * 100)}%</span>
                      <ChevronRight className="w-3 h-3 text-text-muted" />
                      <span className="data-value text-xs text-status-stable font-semibold">{Math.round(currentRec.risk_after * 100)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                    <span className="text-[0.6875rem] text-text-muted">Stabilization</span>
                    <div className="flex items-center gap-2">
                      <span className="data-value text-xs text-text-secondary">{(currentRec.stabilization_before / 60).toFixed(1)}m</span>
                      <ChevronRight className="w-3 h-3 text-text-muted" />
                      <span className="data-value text-xs text-status-stable font-semibold">{(currentRec.stabilization_after / 60).toFixed(1)}m</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Evidence Tags */}
              <div className="mb-5">
                <p className="text-[0.625rem] text-text-muted uppercase tracking-wider font-medium mb-2">Evidence Sources</p>
                <div className="flex flex-wrap gap-1.5">
                  {currentRec.evidence_tags.map((tag: any) => (
                    <span key={tag.tag} className="evidence-tag" title={`${tag.source}: ${tag.detail}`}>{tag.tag}</span>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => acceptMutation.mutate(currentRec.recommendation_id)}
                  className="btn btn-primary flex-1"
                  disabled={acceptMutation.isPending}
                >
                  {acceptMutation.isPending ? 'Accepting...' : 'Accept Recommendation'}
                </button>
                <button 
                  onClick={() => rejectMutation.mutate(currentRec.recommendation_id)}
                  className="btn btn-danger"
                  disabled={rejectMutation.isPending}
                >
                  Reject
                </button>
                <button className="btn btn-outline">
                  Modify
                </button>
              </div>
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
                auditLog.map((log: any) => (
                  <tr key={log.feedback_id} className="border-b border-panel-border/30">
                    <td className="py-3 data-value text-[0.6875rem]">{new Date(log.timestamp).toLocaleTimeString()}</td>
                    <td className="py-3 text-[0.8125rem] font-medium">{log.recommendation?.parameter_name || 'N/A'}</td>
                    <td className="py-3 data-value text-[0.8125rem]">{log.recommendation?.recommended_value || '--'}</td>
                    <td className="py-3">
                      <span className={`inline-flex items-center gap-1 text-[0.625rem] font-medium px-2 py-0.5 rounded-full ${
                        log.response === 'ACCEPTED' ? 'bg-status-stable/10 text-status-stable border border-status-stable/20' : 
                        'bg-status-critical/10 text-status-critical border border-status-critical/20'
                      }`}>
                        {log.response === 'ACCEPTED' ? <CheckCircle className="w-2.5 h-2.5" /> : <AlertTriangle className="w-2.5 h-2.5" />}
                        {log.response}
                      </span>
                    </td>
                    <td className="py-3 text-[0.6875rem] text-text-muted">Operator</td>
                  </tr>
                ))
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
    </motion.div>
  )
}
