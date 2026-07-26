import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Database,
  FileSearch,
  FlaskConical,
  GitBranch,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getDataOverview } from '../api/client'

const chartTooltipStyle = {
  background: '#18181b',
  border: '1px solid #3f3f46',
  borderRadius: 4,
  color: '#f4f4f5',
  fontSize: 12,
}

function Stat({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="panel p-4">
      <p className="text-[0.625rem] uppercase tracking-[0.16em] text-text-muted">{label}</p>
      <p className="data-value mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-[0.6875rem] text-text-muted">{detail}</p>
    </div>
  )
}

export default function DataEvidence() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['data-overview'],
    queryFn: getDataOverview,
    staleTime: 5 * 60 * 1000,
  })

  const trajectoryData = useMemo(() => {
    if (!data) return []
    const rows = new Map<number, Record<string, number>>()
    for (const point of data.trajectory_profiles) {
      const row = rows.get(point.progress_pct) ?? { progress: point.progress_pct }
      row[point.outcome] = point.mean_deviation_pct
      rows.set(point.progress_pct, row)
    }
    return [...rows.values()].sort((a, b) => a.progress - b.progress)
  }, [data])

  if (isLoading) {
    return <div className="m-6 h-[70vh] panel skeleton" aria-label="Loading data evidence" />
  }
  if (error || !data) {
    return (
      <div className="m-6 panel p-8 text-center">
        <AlertTriangle className="mx-auto mb-3 h-7 w-7 text-status-critical" />
        <p className="font-medium">Data evidence could not be loaded.</p>
        <p className="mt-1 text-xs text-text-muted">Check the GradeLens backend connection.</p>
      </div>
    )
  }

  const metrics = data.model_metrics.risk ?? {}
  const earlyMetrics = metrics.pre_breach_30s
  const eventMetrics = metrics.event_level
  const outcomeChart = data.outcome_summary
    .filter((item) => item.outcome === 'success' || item.outcome === 'failure')
    .map((item) => ({
      outcome: item.outcome,
      stabilization: Math.round(item.avg_stabilization_seconds),
      offSpec: Math.round(item.avg_off_spec_seconds),
      deviation: Number(item.avg_max_deviation_pct.toFixed(2)),
    }))

  return (
    <div className="mx-auto max-w-[1720px] space-y-5 p-5 md:p-7">
      <section className="panel panel-accent overflow-hidden p-5 md:p-7">
        <div className="grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
          <div>
            <div className="mb-3 flex items-center gap-2 text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-accent">
              <FileSearch className="h-4 w-4" />
              Data & Model Evidence
            </div>
            <h2 className="max-w-3xl text-2xl font-semibold md:text-3xl">
              Trace every result from process tag to operator suggestion.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              This workspace makes the demo dataset, causal processing window, model split,
              validation metrics, correlations, and limitations visible. It is the evidence
              behind the Command Center—not a second set of hidden calculations.
            </p>
          </div>
          <div className="rounded border border-status-warning/25 bg-status-warning/5 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-status-warning">
              <FlaskConical className="h-4 w-4" />
              Demonstration data, clearly labeled
            </div>
            <p className="mt-2 text-xs leading-5 text-text-secondary">
              {data.provenance.site_data_status} The architecture is deployable, but current
              performance metrics are not evidence of site performance.
            </p>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="History"
          value={`${data.provenance.event_count} events`}
          detail={`${data.provenance.point_count.toLocaleString()} rows · ${data.provenance.sample_interval_seconds}s cadence`}
        />
        <Stat
          label="Completeness"
          value={`${data.data_quality.completeness_pct.toFixed(1)}%`}
          detail={`${data.data_quality.missing_cells} missing process cells`}
        />
        <Stat
          label="Scanner quality"
          value={data.data_quality.avg_scanner_quality.toFixed(3)}
          detail={`${data.data_quality.alarm_point_pct.toFixed(1)}% of samples carry active alarms`}
        />
        <Stat
          label="Grades"
          value={data.provenance.grades.join(' / ')}
          detail={`${data.provenance.grade_pairs.length} directed grade pairs · seed ${data.provenance.deterministic_seed}`}
        />
      </section>

      <section className="panel p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">How data becomes a suggestion</h3>
            <p className="mt-1 text-xs text-text-muted">
              Timestamp-safe at inference: no observation after the selected replay point is used.
            </p>
          </div>
          <span className="evidence-tag text-status-stable">
            <ShieldCheck className="h-3 w-3" /> No live writes
          </span>
        </div>
        <div className="grid gap-2 lg:grid-cols-6">
          {data.processing_steps.map((step, index) => (
            <div key={step.stage} className="relative rounded border border-panel-border/60 bg-panel-bg/45 p-3">
              <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-accent">{step.stage}</p>
              <p className="mt-2 text-[0.6875rem] leading-5 text-text-secondary">{step.detail}</p>
              {index < data.processing_steps.length - 1 && (
                <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-text-muted lg:block" />
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="panel p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold">Transition outcome EDA</h3>
            <p className="mt-1 text-xs text-text-muted">Average stabilization and off-spec exposure by event outcome.</p>
          </div>
          <div className="h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={outcomeChart}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="outcome" stroke="#71717a" tick={{ fontSize: 11 }} />
                <YAxis stroke="#71717a" tick={{ fontSize: 11 }} unit="s" />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar name="Stabilization (s)" dataKey="stabilization" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                <Bar name="Off-spec (s)" dataKey="offSpec" fill="#f97316" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold">Normalized grade-change trajectory</h3>
            <p className="mt-1 text-xs text-text-muted">
              Mean Basis Weight deviation across successful and failed transitions; ±2.5% is the specification boundary.
            </p>
          </div>
          <div className="h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trajectoryData}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="progress" stroke="#71717a" tick={{ fontSize: 11 }} unit="%" />
                <YAxis stroke="#71717a" tick={{ fontSize: 11 }} unit="%" domain={['auto', 'auto']} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <ReferenceLine y={2.5} stroke="#ef4444" strokeDasharray="5 5" />
                <ReferenceLine y={-2.5} stroke="#ef4444" strokeDasharray="5 5" />
                <Line type="monotone" dataKey="success" name="Successful events" stroke="#22c55e" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="failure" name="Failed events" stroke="#ef4444" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="panel p-5">
          <h3 className="text-sm font-semibold">Model validation</h3>
          <p className="mt-1 text-xs text-text-muted">
            Untouched chronological test events; primary warning metrics are measured at least 30 seconds before breach.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            {[
              ['Early ROC–AUC', earlyMetrics?.roc_auc],
              ['Early PR–AUC', earlyMetrics?.pr_auc],
              ['Early precision', earlyMetrics?.precision],
              ['Early recall', earlyMetrics?.recall],
              ['Early Brier', earlyMetrics?.brier_score],
              ['Stab. MAE', data.model_metrics.stabilization_mae_seconds, 's'],
            ].map(([label, value, unit]) => (
              <div key={String(label)} className="rounded border border-panel-border/50 bg-panel-bg/45 p-3">
                <p className="text-[0.625rem] uppercase tracking-wider text-text-muted">{label}</p>
                <p className="data-value mt-1 text-lg font-semibold">
                  {typeof value === 'number' ? (value > 1 ? value.toFixed(1) : value.toFixed(3)) : '--'}
                  <span className="ml-1 text-[0.625rem] text-text-muted">{unit}</span>
                </p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 rounded border border-accent/20 bg-accent/5 p-3 text-[0.6875rem] text-text-secondary">
            <p>
              <span className="block text-[0.625rem] uppercase tracking-wider text-text-muted">Alert threshold</span>
              <span className="data-value text-base text-accent">
                {typeof metrics.decision_threshold === 'number' ? metrics.decision_threshold.toFixed(2) : '--'}
              </span>
              <span className="ml-1 text-text-muted">selected on pre-breach validation F1</span>
            </p>
            <p>
              <span className="block text-[0.625rem] uppercase tracking-wider text-text-muted">Event detection</span>
              <span className="data-value text-base text-accent">
                {eventMetrics ? `${eventMetrics.detected_failure_events}/${eventMetrics.failure_events}` : '--'}
              </span>
              <span className="ml-1 text-text-muted">failed test transitions warned</span>
            </p>
            <p>
              <span className="block text-[0.625rem] uppercase tracking-wider text-text-muted">Median warning</span>
              <span className="data-value text-base">
                {eventMetrics?.median_warning_seconds != null ? `${eventMetrics.median_warning_seconds.toFixed(0)}s` : '--'}
              </span>
            </p>
            <p>
              <span className="block text-[0.625rem] uppercase tracking-wider text-text-muted">False-alert events</span>
              <span className="data-value text-base">
                {eventMetrics?.false_alert_success_events ?? '--'}
              </span>
              <span className="ml-1 text-text-muted">successful test transitions</span>
            </p>
          </div>
          <div className="mt-4 space-y-2 rounded border border-status-stable/20 bg-status-stable/5 p-3 text-[0.6875rem] text-text-secondary">
            <p className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-status-stable" /> {data.split.strategy}</p>
            <p className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-status-stable" /> {data.split.train_events}/{data.split.validation_events}/{data.split.test_events} train/validation/test events</p>
            <p className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-status-stable" /> {earlyMetrics?.windows ?? 0} genuinely pre-breach evaluation windows</p>
            <p className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-status-stable" /> Replay demo events excluded from training</p>
          </div>
          <p className="mt-3 text-[0.625rem] leading-5 text-text-muted">
            All-window scores are retained in the artifact for audit. {(metrics.positive_windows_already_off_spec_fraction ?? 0) * 100 > 0
              ? `${((metrics.positive_windows_already_off_spec_fraction ?? 0) * 100).toFixed(1)}% of positive test windows were already off-spec, so they are excluded from the early-warning headline metrics.`
              : 'No positive test windows were already off-spec.'}
            {' '}Synthetic performance is not calibrated site performance.
          </p>
        </div>

        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Risk model feature importance</h3>
              <p className="mt-1 text-xs text-text-muted">Global LightGBM importance; local explanations in Command Center use SHAP.</p>
            </div>
            <GitBranch className="h-5 w-5 text-status-predicted" />
          </div>
          <div className="h-[360px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={data.feature_importance.slice(0, 10).map((item) => ({
                  ...item,
                  label: item.feature.replaceAll('_', ' '),
                  pct: Number((item.importance * 100).toFixed(2)),
                }))}
                margin={{ left: 35 }}
              >
                <CartesianGrid stroke="#27272a" horizontal={false} />
                <XAxis type="number" stroke="#71717a" tick={{ fontSize: 10 }} unit="%" />
                <YAxis type="category" dataKey="label" width={125} stroke="#71717a" tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="pct" name="Importance" fill="#3b82f6" radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Exploratory relationships found</h3>
            <p className="mt-1 text-xs text-text-muted">
              Event-safe lag and interaction scan. Strong relationships are hypotheses for process review, not causal claims.
            </p>
          </div>
          <Sparkles className="h-5 w-5 text-accent" />
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.relationships.map((item) => (
            <div key={`${item.source_parameter}-${item.lag_seconds}`} className="rounded border border-panel-border/55 bg-panel-bg/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold capitalize">{item.source_parameter.replaceAll('_', ' ')}</p>
                  <p className="mt-1 text-[0.625rem] text-text-muted">→ Basis Weight · {item.lag_seconds}s lag</p>
                </div>
                <span className={`evidence-tag ${item.is_interaction ? 'text-accent border-accent/25' : ''}`}>
                  {item.is_interaction ? 'New interaction' : 'Single loop'}
                </span>
              </div>
              <div className="mt-4 flex items-end justify-between">
                <div>
                  <p className="text-[0.625rem] uppercase tracking-wider text-text-muted">Strength</p>
                  <p className="data-value text-xl font-semibold">{item.strength > 0 ? '+' : ''}{item.strength.toFixed(3)}</p>
                </div>
                <p className="max-w-[55%] text-right text-[0.625rem] leading-4 text-text-muted">{item.source}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex items-center gap-2 border-b border-panel-border/50 p-5">
          <Database className="h-4 w-4 text-accent" />
          <div>
            <h3 className="text-sm font-semibold">Input tag contract</h3>
            <p className="mt-0.5 text-xs text-text-muted">The exact data used by the feature pipeline.</p>
          </div>
        </div>
        <div className="max-h-[390px] overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel-surface text-[0.625rem] uppercase tracking-wider text-text-muted">
              <tr>
                <th className="px-5 py-3">Tag</th>
                <th className="px-5 py-3">Meaning</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.variables.map((variable) => (
                <tr key={variable.tag} className="border-t border-panel-border/30">
                  <td className="data-value px-5 py-3 text-accent">{variable.tag}</td>
                  <td className="px-5 py-3">{variable.display_name} <span className="text-text-muted">({variable.unit})</span></td>
                  <td className="px-5 py-3 capitalize text-text-secondary">{variable.role}</td>
                  <td className="px-5 py-3 text-text-muted">{variable.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
