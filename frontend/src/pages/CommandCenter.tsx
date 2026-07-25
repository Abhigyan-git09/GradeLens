import { useState, useEffect } from 'react'
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
} from 'lucide-react'
import {
  getGradeChange,
  getTimeseries,
  getAuditLog,
  getSnapshot,
  generateRecommendation,
  acceptRecommendation,
  rejectRecommendation,
  modifyRecommendation,
  getCorrelations,
} from '../api/client'
import TrajectoryChart from '../components/TrajectoryChart'
import InfluenceGraph from '../components/InfluenceGraph'

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
  const currentFeatures = snapshot?.current_features;




  
  // Actually just store the generated rec in state to avoid query loop
  const [currentRec, setCurrentRec] = useState<any>(null)
  
  const generateRec = async () => {
    try {
      if (!currentPoint) return;
      const rec = await generateRecommendation({ event_id: eventId, timestamp: currentPoint.timestamp })
      setCurrentRec(rec)
      setSimulatedValue({ parameter: rec.parameter_name, value: rec.recommended_value })
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
      setSimulatedValue(null)
    }
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectRecommendation(id, "Operator override"),
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
    queryKey: ['correlations', eventId],
    queryFn: () => getCorrelations(eventId),
    enabled: !!eventId,
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
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight">Command Center</h2>
            <span className="text-[0.6rem] uppercase tracking-widest font-semibold px-2 py-0.5 rounded-full border border-status-stable/30 bg-status-stable/10 text-status-stable flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-status-stable animate-pulse" />
              Model Health: Active
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
            timeseries={visibleTimeseries} 
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
              {stabilizationData?.similar_events_used !== undefined ? `Based on ${stabilizationData.similar_events_used} similar transitions (k-NN)` : 'Based on similar transitions (k-NN)'}
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
                    {simulatedValue !== null && simulatedValue.value < currentRec.current_value ? <TrendingDown className="w-4 h-4 text-status-stable" /> : <TrendingUp className="w-4 h-4 text-status-stable" />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold">{simulatedValue !== null && simulatedValue.value < currentRec.current_value ? 'Reduce' : 'Increase'} {currentRec.parameter_name} Setpoint</p>
                    <p className="text-[0.6875rem] text-text-muted">{currentRec.rationale}</p>
                    <p className="text-[0.625rem] text-status-stable mt-1.5 font-medium bg-status-stable/10 border border-status-stable/20 px-2 py-0.5 rounded inline-block shadow-sm">
                      <TrendingDown className="w-2.5 h-2.5 inline mr-1" />
                      Business Impact: Prevents ~$4,500/hr in off-spec waste
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Current</p>
                    <p className="data-value text-base font-semibold">{currentRec.current_value.toFixed(1)}</p>
                  </div>
                  <div className="bg-status-stable/5 rounded-lg p-3 text-center border border-status-stable/15 relative">
                    <p className="text-[0.625rem] text-status-stable mb-1 uppercase tracking-wider font-medium">Recommended</p>
                    <p className="data-value text-base font-bold text-status-stable">{simulatedValue?.value.toFixed(1)}</p>
                  </div>
                  <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                    <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Sim Ramp</p>
                    <p className="data-value text-base font-semibold">
                      {simulatedValue !== null && currentPoint ? ((simulatedValue.value - (simulatedValue.parameter === 'Stock Flow' ? currentPoint.stock_flow_actual : currentPoint.machine_speed_actual)) / 15.0).toFixed(1) : currentRec.recommended_ramp_rate}
                    </p>
                    <p className="text-[0.625rem] text-text-muted">/s</p>
                  </div>
                </div>
                
                {/* Simulator Slider */}
                <div className="mb-5 px-1">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[0.6875rem] text-text-muted font-medium">Setpoint Simulator Override</span>
                    <span className="text-[0.625rem] text-accent">Live Inference Active</span>
                  </div>
                  <input 
                    type="range" 
                    min={currentRec.current_value * 0.9} 
                    max={currentRec.current_value * 1.1} 
                    value={simulatedValue?.value ?? currentRec.recommended_value}
                    onChange={(e) => setSimulatedValue({ parameter: currentRec.parameter_name, value: Number(e.target.value) })}
                    className="w-full accent-accent h-1.5 bg-panel-surface rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-[0.625rem] text-text-muted mt-1">
                    <span>-10%</span>
                    <span>Engine Default: {currentRec.recommended_value}</span>
                    <span>+10%</span>
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
                <button
                  onClick={() => modifyMutation.mutate({ id: currentRec.recommendation_id, value: simulatedValue?.value ?? currentRec.recommended_value })}
                  className="btn btn-outline"
                  disabled={modifyMutation.isPending}
                >
                  {modifyMutation.isPending ? 'Modifying...' : 'Modify'}
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
                    <td className="py-3 data-value text-[0.8125rem]">{log.recommendation?.recommended_value != null ? log.recommendation.recommended_value.toFixed(1) : '--'}</td>
                    <td className="py-3">
                      <span className={`inline-flex items-center gap-1 text-[0.625rem] font-medium px-2 py-0.5 rounded-full ${
                        log.response === 'accept' ? 'bg-status-stable/10 text-status-stable border border-status-stable/20' : 
                        'bg-status-critical/10 text-status-critical border border-status-critical/20'
                      }`}>
                        {log.response === 'accept' ? <CheckCircle className="w-2.5 h-2.5" /> : <AlertTriangle className="w-2.5 h-2.5" />}
                        {log.response === 'accept' ? 'Accepted' : log.response === 'reject' ? 'Rejected' : log.response === 'modify' ? 'Modified' : log.response}
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
        <InfluenceGraph correlations={correlations || []} />
      </motion.div>
    </motion.div>
  )
}
