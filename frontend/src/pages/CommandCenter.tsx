import { motion } from 'framer-motion'
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
} from 'lucide-react'

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
  // Mock data for visual demonstration — will be replaced with live API data in Phase 8
  const mockRootCauses = [
    { parameter: 'Stock Flow', contribution: 38, rationale: 'Ramp rate is 27% above the median successful trajectory', isInteraction: false },
    { parameter: 'Filler × Steam Interaction', contribution: 24, rationale: 'Compound effect between filler-flow ramp and steam-pressure slope at 45s lag', isInteraction: true },
    { parameter: 'Machine Speed', contribution: 18, rationale: 'Delayed response — 12s behind expected coordination window', isInteraction: false },
    { parameter: 'Steam Pressure', contribution: 12, rationale: 'Slope trending negative while moisture demand increasing', isInteraction: false },
  ]

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
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 rounded-full bg-chart-recommended" /> Recommended
              </span>
            </div>
          </div>
          {/* Chart placeholder — will be Recharts in Phase 8 */}
          <div className="flex-1 flex items-center justify-center relative overflow-hidden rounded-lg bg-panel-bg/50">
            {/* Grid lines */}
            <div className="absolute inset-0 opacity-[0.04]"
              style={{
                backgroundImage: `
                  linear-gradient(rgba(226,232,240,1) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(226,232,240,1) 1px, transparent 1px)
                `,
                backgroundSize: '60px 50px'
              }}
            />
            {/* Limit bands */}
            <div className="absolute top-[15%] left-0 right-0 h-[10%] bg-chart-limit-band border-t border-b border-chart-limit-line/30" />
            <div className="absolute bottom-[15%] left-0 right-0 h-[10%] bg-chart-limit-band border-t border-b border-chart-limit-line/30" />

            <div className="text-center space-y-2 z-10">
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <Activity className="w-10 h-10 text-accent/30 mx-auto" strokeWidth={1.5} />
              </motion.div>
              <p className="text-sm text-text-secondary font-medium">Chart renders with live data</p>
              <p className="text-[0.6875rem] text-text-muted">Phase 8 — Recharts integration</p>
            </div>
          </div>
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
                    animate={{ strokeDashoffset: 2 * Math.PI * 50 * (1 - 0.67) }}
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
                  <span className="data-value text-2xl font-bold text-status-warning">67%</span>
                  <span className="text-[0.625rem] text-text-muted font-medium uppercase tracking-wider">Risk</span>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <TrendingUp className="w-3 h-3 text-status-warning" /> Direction
                </span>
                <span className="data-value text-xs font-medium text-status-warning">Upper Limit ↑</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted flex items-center gap-1.5">
                  <Clock className="w-3 h-3 text-status-critical" /> Time to Violation
                </span>
                <span className="data-value text-xs font-semibold text-status-critical">~84s</span>
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
              <span className="data-value text-lg font-semibold">~4.2</span>
              <span className="text-xs text-text-muted font-medium">min remaining</span>
            </div>
            <p className="text-[0.6875rem] text-text-muted">
              Based on 4 similar transitions (k-NN)
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
          <MetricCard icon={Layers} label="Basis Weight" value="62.8" unit="g/m²" setpoint="64.0" deviation="+1.9%" status="warning" />
          <MetricCard icon={Droplets} label="Stock Flow" value="847" unit="L/min" setpoint="820" deviation="+3.3%" status="warning" />
          <MetricCard icon={Wind} label="Filler Flow" value="126" unit="L/min" setpoint="130" deviation="-3.1%" status="stable" />
          <MetricCard icon={Flame} label="Steam Press" value="4.12" unit="bar" setpoint="4.20" deviation="-1.9%" status="stable" />
          <MetricCard icon={Gauge} label="Machine Spd" value="623" unit="m/min" setpoint="640" deviation="-2.7%" status="warning" />
          <MetricCard icon={Droplets} label="Moisture" value="6.8" unit="%" setpoint="7.0" deviation="-2.9%" status="stable" />
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
            {mockRootCauses.map((cause, i) => (
              <RootCauseItem
                key={cause.parameter}
                rank={i + 1}
                parameter={cause.parameter}
                contribution={cause.contribution}
                rationale={cause.rationale}
                isInteraction={cause.isInteraction}
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
            <span className="text-[0.625rem] font-medium text-accent bg-accent/8 px-2 py-0.5 rounded-full border border-accent/15">
              Confidence: 82%
            </span>
          </div>

          {/* Main Recommendation */}
          <div className="bg-panel-bg/60 rounded-xl p-4 mb-4 border border-panel-border/50">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-status-stable/10 flex items-center justify-center">
                <TrendingDown className="w-4 h-4 text-status-stable" />
              </div>
              <div>
                <p className="text-sm font-semibold">Reduce Stock Flow Setpoint</p>
                <p className="text-[0.6875rem] text-text-muted">Adjust ramping to prevent overshoot</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Current</p>
                <p className="data-value text-base font-semibold">847</p>
                <p className="text-[0.625rem] text-text-muted">L/min</p>
              </div>
              <div className="bg-status-stable/5 rounded-lg p-3 text-center border border-status-stable/15">
                <p className="text-[0.625rem] text-status-stable mb-1 uppercase tracking-wider font-medium">Recommended</p>
                <p className="data-value text-base font-bold text-status-stable">812</p>
                <p className="text-[0.625rem] text-text-muted">L/min</p>
              </div>
              <div className="bg-panel-surface/50 rounded-lg p-3 text-center">
                <p className="text-[0.625rem] text-text-muted mb-1 uppercase tracking-wider">Ramp Rate</p>
                <p className="data-value text-base font-semibold">-5.8</p>
                <p className="text-[0.625rem] text-text-muted">L/min/s</p>
              </div>
            </div>

            {/* Before / After Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                <span className="text-[0.6875rem] text-text-muted">Risk</span>
                <div className="flex items-center gap-2">
                  <span className="data-value text-xs text-status-warning">67%</span>
                  <ChevronRight className="w-3 h-3 text-text-muted" />
                  <span className="data-value text-xs text-status-stable font-semibold">23%</span>
                </div>
              </div>
              <div className="flex items-center justify-between bg-panel-surface/30 rounded-lg px-3 py-2">
                <span className="text-[0.6875rem] text-text-muted">Stabilization</span>
                <div className="flex items-center gap-2">
                  <span className="data-value text-xs text-text-secondary">4.2m</span>
                  <ChevronRight className="w-3 h-3 text-text-muted" />
                  <span className="data-value text-xs text-status-stable font-semibold">2.1m</span>
                </div>
              </div>
            </div>
          </div>

          {/* Evidence Tags */}
          <div className="mb-5">
            <p className="text-[0.625rem] text-text-muted uppercase tracking-wider font-medium mb-2">Evidence Sources</p>
            <div className="flex flex-wrap gap-1.5">
              {['Risk Model', 'Trajectory Forecast', 'Recipe Constraint', 'Historical Success', 'Process Correlation', 'Safety Check'].map((tag) => (
                <span key={tag} className="evidence-tag">{tag}</span>
              ))}
            </div>
          </div>

          {/* Action Buttons — Accept / Reject / Modify */}
          <div className="flex items-center gap-2">
            <button className="btn btn-primary flex-1">
              Accept Recommendation
            </button>
            <button className="btn btn-danger">
              Reject
            </button>
            <button className="btn btn-outline">
              Modify
            </button>
          </div>
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
            </tbody>
          </table>
        </div>
      </motion.div>
    </motion.div>
  )
}
