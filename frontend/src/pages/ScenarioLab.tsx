import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCheck2,
  Gauge,
  Play,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
} from 'lucide-react'
import {
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
import {
  getGradeChanges,
  getRecipeConstraints,
  getRecommendationOpportunities,
  getTimeseries,
  runScenario,
  validateDataset,
} from '../api/client'
import type { RecipeConstraint } from '../types'

const SUPPORTED_PARAMETERS = ['stock_flow', 'filler_flow', 'steam_pressure', 'machine_speed']
const DISPLAY_NAMES: Record<string, string> = {
  stock_flow: 'Stock Flow',
  filler_flow: 'Filler Flow',
  steam_pressure: 'Steam Pressure',
  machine_speed: 'Machine Speed',
}
const ACTUAL_FIELDS: Record<string, string> = {
  stock_flow: 'stock_flow_actual',
  filler_flow: 'filler_flow_actual',
  steam_pressure: 'steam_pressure_actual',
  machine_speed: 'machine_speed_actual',
}
const SAMPLE_COLUMNS = [
  'timestamp',
  'basis_weight_actual',
  'basis_weight_setpoint',
  'stock_flow_actual',
  'stock_flow_setpoint',
  'filler_flow_actual',
  'filler_flow_setpoint',
  'steam_pressure_actual',
  'steam_pressure_setpoint',
  'machine_speed_actual',
  'machine_speed_setpoint',
  'moisture_actual',
  'moisture_setpoint',
  'ash_actual',
  'ash_setpoint',
  'caliper_actual',
  'caliper_setpoint',
  'active_alarm_count',
  'scanner_quality_score',
]

function parseCsv(text: string) {
  const records: string[][] = []
  let record: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        value += '"'
        index += 1
      } else {
        quoted = !quoted
      }
    } else if (character === ',' && !quoted) {
      record.push(value)
      value = ''
    } else if ((character === '\n' || character === '\r') && !quoted) {
      if (character === '\r' && text[index + 1] === '\n') index += 1
      record.push(value)
      if (record.some((cell) => cell.trim() !== '')) records.push(record)
      record = []
      value = ''
    } else {
      value += character
    }
  }
  record.push(value)
  if (record.some((cell) => cell.trim() !== '')) records.push(record)
  const columns = (records.shift() ?? []).map((item) => item.trim())
  const rows = records.map((values) =>
    Object.fromEntries(columns.map((column, index) => [column, values[index] ?? ''])),
  )
  return { columns, rows }
}

function ConstraintControl({
  constraint,
  currentValue,
  value,
  selected,
  onToggle,
  onChange,
}: {
  constraint: RecipeConstraint
  currentValue: number
  value: number
  selected: boolean
  onToggle: () => void
  onChange: (value: number) => void
}) {
  const requiredRamp = Math.abs(value - currentValue) / 15
  const rampOk = constraint.max_ramp_rate == null || requiredRamp <= constraint.max_ramp_rate
  const rangeOk = value >= constraint.min_val && value <= constraint.max_val
  return (
    <div className={`rounded border p-4 transition-colors ${selected ? 'border-accent/45 bg-accent/5' : 'border-panel-border/55 bg-panel-bg/35'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <button type="button" onClick={onToggle} className="flex items-center gap-2 text-left">
            <span className={`h-3.5 w-3.5 rounded-sm border ${selected ? 'border-accent bg-accent' : 'border-panel-border'}`} />
            <span className="text-sm font-semibold">{DISPLAY_NAMES[constraint.parameter]}</span>
          </button>
          <p className="ml-5 mt-1 text-[0.625rem] text-text-muted">
            Current <span className="data-value text-text-secondary">{currentValue.toFixed(2)}</span> · optimal{' '}
            <span className="data-value text-text-secondary">{constraint.optimal_val.toFixed(2)}</span>
          </p>
        </div>
        <span className={`evidence-tag ${rangeOk && rampOk ? 'text-status-stable' : 'text-status-critical'}`}>
          {rangeOk && rampOk ? 'Feasible' : 'Blocked'}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-[1fr_90px] gap-3">
        <input
          aria-label={`${DISPLAY_NAMES[constraint.parameter]} scenario slider`}
          type="range"
          min={constraint.min_val}
          max={constraint.max_val}
          step={(constraint.max_val - constraint.min_val) / 200}
          value={value}
          disabled={!selected}
          onChange={(event) => onChange(Number(event.target.value))}
          className="accent-accent disabled:opacity-40"
        />
        <input
          aria-label={`${DISPLAY_NAMES[constraint.parameter]} scenario value`}
          type="number"
          min={constraint.min_val}
          max={constraint.max_val}
          step="any"
          value={value}
          disabled={!selected}
          onChange={(event) => onChange(Number(event.target.value))}
          className="data-value rounded border border-panel-border bg-panel-bg px-2 py-1.5 text-right text-xs outline-none focus:border-accent disabled:opacity-40"
        />
      </div>
      <div className="mt-2 flex justify-between text-[0.625rem] text-text-muted">
        <span>{constraint.min_val.toFixed(1)} min</span>
        <span className={rampOk ? '' : 'text-status-critical'}>
          ramp {requiredRamp.toFixed(2)}/s ≤ {constraint.max_ramp_rate?.toFixed(2) ?? '—'}/s
        </span>
        <span>{constraint.max_val.toFixed(1)} max</span>
      </div>
    </div>
  )
}

export default function ScenarioLab() {
  const [eventId, setEventId] = useState('EVT-003-RECOVERABLE')
  const [sampleIndex, setSampleIndex] = useState(11)
  const [selectedParameters, setSelectedParameters] = useState<string[]>(['stock_flow'])
  const [values, setValues] = useState<Record<string, number>>({})
  const [activeTab, setActiveTab] = useState<'scenario' | 'upload'>('scenario')
  const [fileError, setFileError] = useState('')

  const { data: events = [] } = useQuery({ queryKey: ['grade-changes'], queryFn: getGradeChanges })
  const event = events.find((item) => item.event_id === eventId)
  const { data: points = [] } = useQuery({
    queryKey: ['timeseries', eventId],
    queryFn: () => getTimeseries(eventId),
    enabled: Boolean(eventId),
  })
  const { data: constraints = [] } = useQuery({
    queryKey: ['recipe-constraints', event?.target_grade],
    queryFn: () => getRecipeConstraints(event!.target_grade),
    enabled: Boolean(event?.target_grade),
  })

  useEffect(() => {
    if (!points.length) return
    // Start near the pre-violation segment in the curated recoverable demo,
    // while still leaving the full event under operator control.
    setSampleIndex(Math.max(11, Math.min(points.length - 1, Math.round(points.length * 0.47))))
  }, [eventId, points.length])

  const currentPoint = points[sampleIndex]
  const supportedConstraints = useMemo(
    () => constraints.filter((item) => SUPPORTED_PARAMETERS.includes(item.parameter)),
    [constraints],
  )

  useEffect(() => {
    if (!currentPoint || !supportedConstraints.length) return
    setValues((previous) => {
      const next = { ...previous }
      for (const constraint of supportedConstraints) {
        if (next[constraint.parameter] == null) {
          next[constraint.parameter] = constraint.optimal_val
        }
      }
      return next
    })
  }, [currentPoint, supportedConstraints])

  const { data: opportunities = [] } = useQuery({
    queryKey: ['scenario-opportunities', eventId, currentPoint?.timestamp],
    queryFn: () => getRecommendationOpportunities(eventId, currentPoint!.timestamp),
    enabled: Boolean(currentPoint && sampleIndex >= 11),
  })

  const scenarioMutation = useMutation({
    mutationFn: runScenario,
  })
  const validationMutation = useMutation({
    mutationFn: validateDataset,
  })

  const runCurrentScenario = () => {
    if (!currentPoint || !selectedParameters.length) return
    scenarioMutation.mutate({
      event_id: eventId,
      timestamp: currentPoint.timestamp,
      adjustments: selectedParameters.map((parameter) => ({
        parameter_name: parameter,
        proposed_value: values[parameter],
      })),
    })
  }

  const resetToRecipe = () => {
    setValues(Object.fromEntries(supportedConstraints.map((item) => [item.parameter, item.optimal_val])))
    scenarioMutation.reset()
  }

  const loadLearnedCandidate = (parameter: string) => {
    const candidate = opportunities.find(
      (item) => item.parameter_name.toLowerCase().replaceAll(' ', '_') === parameter,
    )
    if (!candidate) return
    setSelectedParameters((previous) => previous.includes(parameter) ? previous : [...previous, parameter].slice(0, 4))
    setValues((previous) => ({ ...previous, [parameter]: candidate.proposed_value }))
  }

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    setFileError('')
    validationMutation.reset()
    const file = event.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) {
      setFileError('File exceeds the 10 MB sandbox validation limit.')
      return
    }
    try {
      const parsed = parseCsv(await file.text())
      if (!parsed.columns.length) throw new Error('No CSV header found.')
      validationMutation.mutate({
        file_name: file.name,
        columns: parsed.columns,
        rows: parsed.rows.slice(0, 500),
      })
    } catch (error) {
      setFileError(error instanceof Error ? error.message : 'CSV could not be parsed.')
    }
  }

  const validateDemoContract = () => {
    const baseRow = {
      basis_weight_actual: 80,
      basis_weight_setpoint: 80,
      stock_flow_actual: 1020,
      stock_flow_setpoint: 1020,
      filler_flow_actual: 150,
      filler_flow_setpoint: 150,
      steam_pressure_actual: 5,
      steam_pressure_setpoint: 5,
      machine_speed_actual: 580,
      machine_speed_setpoint: 580,
      moisture_actual: 6.5,
      moisture_setpoint: 6.5,
      ash_actual: 18,
      ash_setpoint: 18,
      caliper_actual: 107,
      caliper_setpoint: 107,
      active_alarm_count: 0,
      scanner_quality_score: 0.98,
    }
    validationMutation.mutate({
      file_name: 'built-in-tag-contract-demo.csv',
      columns: SAMPLE_COLUMNS,
      rows: Array.from({ length: 12 }, (_, index) => ({
        timestamp: new Date(Date.UTC(2026, 6, 1, 0, 0, index * 5)).toISOString(),
        ...baseRow,
      })),
    })
  }

  const result = scenarioMutation.data
  const chartData = result?.baseline_trajectory.horizons.map((baseline, index) => ({
    seconds: baseline.seconds,
    setpoint: baseline.predicted_setpoint,
    baseline: baseline.predicted_bw,
    scenario: result.counterfactual_trajectory.horizons[index].predicted_bw,
  })) ?? []

  return (
    <div className="mx-auto max-w-[1720px] space-y-5 p-5 md:p-7">
      <section className="panel panel-accent p-5 md:p-7">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2 text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-accent">
              <SlidersHorizontal className="h-4 w-4" /> Operator Scenario Lab
            </div>
            <h2 className="text-2xl font-semibold md:text-3xl">Control the evidence before trusting the advice.</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              Select a historical transition and decision time, coordinate up to four setpoint changes, or validate a
              site CSV tag contract. Every run is bounded by the target recipe and actuator ramp limits.
            </p>
          </div>
          <div className="flex rounded border border-panel-border bg-panel-bg/40 p-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('scenario')}
              className={`rounded px-4 py-2 font-medium ${activeTab === 'scenario' ? 'bg-accent text-text-inverse' : 'text-text-secondary'}`}
            >
              What-if Scenario
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('upload')}
              className={`rounded px-4 py-2 font-medium ${activeTab === 'upload' ? 'bg-accent text-text-inverse' : 'text-text-secondary'}`}
            >
              Validate Site CSV
            </button>
          </div>
        </div>
      </section>

      {activeTab === 'scenario' ? (
        <>
          <section className="panel p-5">
            <div className="mb-4 flex items-center gap-2">
              <Database className="h-4 w-4 text-status-predicted" />
              <h3 className="text-sm font-semibold">1 · Choose the evidence slice</h3>
            </div>
            <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
              <label className="text-xs text-text-secondary">
                Historical grade-change event
                <select
                  aria-label="Historical grade-change event"
                  value={eventId}
                  onChange={(event) => {
                    setEventId(event.target.value)
                    setValues({})
                    scenarioMutation.reset()
                  }}
                  className="mt-2 w-full rounded border border-panel-border bg-panel-bg px-3 py-2.5 text-xs text-text-primary outline-none focus:border-accent"
                >
                  {events.map((item) => (
                    <option key={item.event_id} value={item.event_id}>
                      {item.event_id} · {item.source_grade} → {item.target_grade} · {item.transition_outcome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-text-secondary">
                Decision point · sample {sampleIndex + 1}/{points.length || '—'} ·{' '}
                <span className="data-value text-accent">{currentPoint ? new Date(currentPoint.timestamp).toLocaleTimeString() : 'loading'}</span>
                <input
                  aria-label="Scenario decision point"
                  type="range"
                  min={11}
                  max={Math.max(11, points.length - 1)}
                  value={Math.min(sampleIndex, Math.max(11, points.length - 1))}
                  onChange={(event) => {
                    setSampleIndex(Number(event.target.value))
                    scenarioMutation.reset()
                  }}
                  className="mt-4 w-full accent-accent"
                />
                <span className="mt-1 flex justify-between text-[0.625rem] text-text-muted">
                  <span>60s context ready</span>
                  <span>End of event</span>
                </span>
              </label>
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="panel p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold">2 · Build a bounded setpoint scenario</h3>
                  <p className="mt-1 text-xs text-text-muted">Select one to four parameters. Values are validated as a coordinated action.</p>
                </div>
                <button type="button" onClick={resetToRecipe} className="btn btn-outline !px-3 !py-1.5 !text-[0.625rem]">
                  <RotateCcw className="h-3 w-3" /> Recipe optimal
                </button>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {supportedConstraints.map((constraint) => {
                  const currentValue = Number(currentPoint?.[ACTUAL_FIELDS[constraint.parameter] as keyof typeof currentPoint] ?? constraint.optimal_val)
                  return (
                    <ConstraintControl
                      key={constraint.parameter}
                      constraint={constraint}
                      currentValue={currentValue}
                      value={values[constraint.parameter] ?? constraint.optimal_val}
                      selected={selectedParameters.includes(constraint.parameter)}
                      onToggle={() => setSelectedParameters((previous) =>
                        previous.includes(constraint.parameter)
                          ? previous.filter((item) => item !== constraint.parameter)
                          : [...previous, constraint.parameter].slice(0, 4),
                      )}
                      onChange={(value) => setValues((previous) => ({ ...previous, [constraint.parameter]: value }))}
                    />
                  )
                })}
              </div>
              {opportunities.length > 0 && (
                <div className="mt-4 rounded border border-status-predicted/20 bg-status-predicted/5 p-3">
                  <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-status-predicted">Learned candidates at this timestamp</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {opportunities.slice(0, 4).map((opportunity) => {
                      const parameter = opportunity.parameter_name.toLowerCase().replaceAll(' ', '_')
                      return (
                        <button
                          type="button"
                          key={opportunity.parameter_name}
                          onClick={() => loadLearnedCandidate(parameter)}
                          className="evidence-tag"
                        >
                          {opportunity.parameter_name} {opportunity.proposed_value.toFixed(2)} · risk {Math.round(opportunity.risk_after * 100)}%
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
              <button
                type="button"
                onClick={runCurrentScenario}
                disabled={!currentPoint || !selectedParameters.length || scenarioMutation.isPending}
                className="btn btn-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Play className="h-4 w-4" />
                {scenarioMutation.isPending ? 'Running constrained scenario…' : `Run ${selectedParameters.length || 0}-parameter scenario`}
              </button>
              {scenarioMutation.isError && (
                <p className="mt-3 text-xs text-status-critical">The scenario could not be evaluated. Confirm the feature window and recipe limits.</p>
              )}
            </div>

            <div className="panel p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold">3 · Compare future state</h3>
                  <p className="mt-1 text-xs text-text-muted">Same baseline and horizons; only your selected setpoints change.</p>
                </div>
                {result && (
                  <span className={`evidence-tag ${result.feasible ? 'text-status-stable' : 'text-status-critical'}`}>
                    {result.feasible ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                    {result.feasible ? 'All guardrails passed' : 'Scenario blocked'}
                  </span>
                )}
              </div>
              {result ? (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                      <p className="text-[0.625rem] uppercase text-text-muted">Risk</p>
                      <p className="data-value mt-1 text-base"><span className="text-status-warning">{Math.round(result.risk_before * 100)}%</span> → <span className={result.risk_after < result.risk_before ? 'text-status-stable' : 'text-status-critical'}>{Math.round(result.risk_after * 100)}%</span></p>
                    </div>
                    <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                      <p className="text-[0.625rem] uppercase text-text-muted">Stabilization</p>
                      <p className="data-value mt-1 text-base">{(result.stabilization_before / 60).toFixed(1)}m → <span className="text-status-stable">{(result.stabilization_after / 60).toFixed(1)}m</span></p>
                    </div>
                    <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                      <p className="text-[0.625rem] uppercase text-text-muted">Avoided off-spec</p>
                      <p className="data-value mt-1 text-base text-accent">{result.avoided_off_spec_seconds.toFixed(0)}s</p>
                    </div>
                  </div>
                  <div className="mt-4 h-[280px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid stroke="#27272a" vertical={false} />
                        <XAxis dataKey="seconds" stroke="#71717a" tick={{ fontSize: 10 }} unit="s" />
                        <YAxis stroke="#71717a" tick={{ fontSize: 10 }} domain={['auto', 'auto']} unit=" gsm" />
                        <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', fontSize: 11 }} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <ReferenceLine y={chartData[0]?.setpoint} stroke="#71717a" strokeDasharray="4 4" />
                        <Line type="monotone" dataKey="baseline" name="Current trajectory" stroke="#eab308" strokeWidth={2} />
                        <Line type="monotone" dataKey="scenario" name="Your scenario" stroke="#22c55e" strokeWidth={2.5} />
                        <Line type="monotone" dataKey="setpoint" name="Moving setpoint" stroke="#a1a1aa" strokeDasharray="5 5" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-3 space-y-2">
                    {result.adjustments.map((adjustment) => (
                      <div key={adjustment.parameter_name} className="rounded border border-panel-border/45 bg-panel-bg/35 px-3 py-2 text-[0.6875rem]">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">{adjustment.parameter_name}</span>
                          <span className={adjustment.feasible ? 'text-status-stable' : 'text-status-critical'}>{adjustment.constraint_message}</span>
                        </div>
                        <p className="mt-1 text-text-muted">Source: {adjustment.evidence_source}</p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 flex items-start gap-2 rounded border border-status-warning/20 bg-status-warning/5 p-3 text-[0.6875rem] leading-5 text-text-secondary">
                    <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-warning" /> {result.guardrail}
                  </p>
                </>
              ) : (
                <div className="flex min-h-[430px] items-center justify-center">
                  <div className="w-full max-w-[36rem] rounded border border-panel-border/55 bg-panel-bg/35 px-5 py-8 text-center sm:px-8">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-status-predicted/25 bg-status-predicted/8">
                      <Gauge className="h-6 w-6 text-status-predicted" />
                    </div>
                    <p className="mt-4 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-status-predicted">
                      Awaiting scenario
                    </p>
                    <h4 className="mt-2 text-base font-semibold tracking-tight">
                      Compare a safer future state
                    </h4>
                    <p className="mx-auto mt-2 w-full max-w-[28rem] text-xs leading-5 text-text-muted">
                      Configure a bounded intervention on the left, then run it to compare projected risk,
                      stabilization time, and off-spec exposure.
                    </p>

                    <div className="mt-6 grid grid-cols-1 gap-2 text-left sm:grid-cols-3">
                      {[
                        ['01', 'Choose a decision point'],
                        ['02', 'Adjust safe setpoints'],
                        ['03', 'Run and compare'],
                      ].map(([number, label]) => (
                        <div
                          key={number}
                          className="flex items-center gap-2.5 rounded border border-panel-border/45 bg-panel-surface/45 px-3 py-2.5"
                        >
                          <span className="data-value text-[0.625rem] font-semibold text-accent">{number}</span>
                          <span className="text-[0.6875rem] font-medium text-text-secondary">{label}</span>
                        </div>
                      ))}
                    </div>

                    <p className="mt-5 text-[0.625rem] leading-4 text-text-muted">
                      Advisory simulation only · no control-system writes
                    </p>
                  </div>
                </div>
              )}
            </div>
          </section>
        </>
      ) : (
        <section className="grid gap-5 xl:grid-cols-[0.75fr_1.25fr]">
          <div className="panel p-5">
            <div className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-accent" />
              <h3 className="text-sm font-semibold">Validate a historian export</h3>
            </div>
            <p className="mt-2 text-xs leading-5 text-text-muted">
              Choose a CSV to test column coverage, numeric quality, and the minimum 60-second feature window. The browser sends at most
              500 parsed rows to the local API; nothing is persisted.
            </p>
            <label className="mt-5 flex min-h-[190px] cursor-pointer flex-col items-center justify-center rounded border border-dashed border-panel-border bg-panel-bg/35 p-6 text-center hover:border-accent/60">
              <Upload className="mb-3 h-8 w-8 text-text-muted" />
              <span className="text-sm font-medium">Choose CSV file</span>
              <span className="mt-1 text-[0.6875rem] text-text-muted">Up to 10 MB · header row required</span>
              <input aria-label="Upload process CSV" type="file" accept=".csv,text/csv" onChange={handleFile} className="hidden" />
            </label>
            <button
              type="button"
              onClick={validateDemoContract}
              disabled={validationMutation.isPending}
              className="btn btn-outline mt-3 w-full disabled:opacity-45"
            >
              <FileCheck2 className="h-3.5 w-3.5" />
              Validate built-in demo contract
            </button>
            {(fileError || validationMutation.isError) && (
              <p className="mt-3 text-xs text-status-critical">{fileError || 'Validation request failed.'}</p>
            )}
            <div className="mt-4 rounded border border-status-warning/20 bg-status-warning/5 p-3 text-[0.6875rem] leading-5 text-text-secondary">
              This validates compatibility only. It does not train a model, create an event, or grant live control authority.
            </div>
          </div>

          <div className="panel p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">Tag contract report</h3>
                <p className="mt-1 text-xs text-text-muted">Actual/setpoint pairs, alarms, scanner quality, and timestamp are required.</p>
              </div>
              {validationMutation.data && (
                <span className={`evidence-tag ${validationMutation.data.valid ? 'text-status-stable' : 'text-status-critical'}`}>
                  <FileCheck2 className="h-3 w-3" />
                  {validationMutation.data.valid ? 'Inference ready' : 'Action required'}
                </span>
              )}
            </div>
            {validationMutation.isPending ? (
              <div className="h-[360px] skeleton" />
            ) : validationMutation.data ? (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                    <p className="text-[0.625rem] uppercase text-text-muted">Column coverage</p>
                    <p className="data-value mt-1 text-xl font-semibold">{validationMutation.data.coverage_pct.toFixed(1)}%</p>
                  </div>
                  <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                    <p className="text-[0.625rem] uppercase text-text-muted">Numeric quality</p>
                    <p className="data-value mt-1 text-xl font-semibold">{validationMutation.data.data_quality.numeric_completeness_pct.toFixed(1)}%</p>
                  </div>
                  <div className="rounded border border-panel-border/50 bg-panel-bg/40 p-3">
                    <p className="text-[0.625rem] uppercase text-text-muted">Rows sampled</p>
                    <p className="data-value mt-1 text-xl font-semibold">{validationMutation.data.row_count}</p>
                  </div>
                </div>
                <div className="rounded border border-panel-border/50 p-3">
                  <p className="text-[0.625rem] font-semibold uppercase tracking-wider text-text-muted">Mapped tags</p>
                  <div className="mt-2 flex max-h-[120px] flex-wrap gap-1.5 overflow-auto">
                    {Object.entries(validationMutation.data.mapped_columns).map(([canonical, source]) => (
                      <span key={canonical} className="evidence-tag" title={`CSV column: ${source}`}>{canonical}</span>
                    ))}
                  </div>
                </div>
                {validationMutation.data.missing_columns.length > 0 && (
                  <div className="rounded border border-status-critical/20 bg-status-critical/5 p-3">
                    <p className="text-[0.625rem] font-semibold uppercase text-status-critical">Missing required tags</p>
                    <p className="data-value mt-2 text-xs leading-5 text-text-secondary">{validationMutation.data.missing_columns.join(', ')}</p>
                  </div>
                )}
                {[...validationMutation.data.warnings, ...validationMutation.data.parse_errors].length > 0 && (
                  <div className="space-y-1 rounded border border-status-warning/20 bg-status-warning/5 p-3 text-[0.6875rem] text-text-secondary">
                    {[...validationMutation.data.warnings, ...validationMutation.data.parse_errors].map((message) => (
                      <p key={message} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-status-warning" />{message}</p>
                    ))}
                  </div>
                )}
                <p className="flex gap-2 text-[0.6875rem] leading-5 text-status-stable">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {validationMutation.data.sandbox_note}
                </p>
              </div>
            ) : (
              <div className="flex min-h-[360px] flex-col items-center justify-center text-center">
                <Database className="mb-3 h-8 w-8 text-text-muted" />
                <p className="text-sm font-medium">Waiting for a file</p>
                <p className="mt-1 max-w-sm text-xs leading-5 text-text-muted">The report will show canonical tag mapping and exactly what must be fixed before data can enter a model pipeline.</p>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
