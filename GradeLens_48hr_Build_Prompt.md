# GradeLens — 48-Hour Build Prompt (Scoped for Hackathon Win, Not Enterprise Spec)

You are the lead engineer building **GradeLens**, an explainable advisory layer that predicts Basis Weight
spec risk during automatic grade changes in paper manufacturing, explains *why*, recommends a safe
corrective setpoint, and learns from operator accept/reject/modify feedback.

You have **48 hours**, one build track, and a hard rule: **a small system that works flawlessly and tells
a sharp story beats a large system that half-works.** Every section below is written to that constraint.
Do not expand scope beyond what's written here without explicitly re-checking the time budget.

---

## 0. Win Thesis (keep this in view at all times)

Judges will see many "AI risk dashboards." The thing that wins is not feature count — it's whether GradeLens
can prove, on stage, that it caught something a human staring at individual gauges would have missed, explained
it in language a papermaking engineer trusts, proposed one precise correction, and can show a real (even if
small) log of operator decisions being tracked for quality. Optimize every hour toward that proof, not toward
breadth.

The one genuinely novel beat (see §5) is: **an interaction between two variables that looks harmless
individually but compounds into risk together** — this is the literal ask in the original brief
("find new correlations not defined in the system") and most competing teams will not bother to construct
it deliberately. Don't skip it.

---

## 1. Scope Contract — MVP vs Stretch (read this before writing any code)

### MVP — must be 100% working and demo-rehearsed. This is the win condition.
1. One synthetic dataset: 3 grade-change events (success / failure / **recoverable** — recoverable is the demo event).
2. Basis Weight chart: actual, setpoint, ±2.5% limits, predicted trajectory — replaying live on a timer.
3. Risk model: off-spec probability, direction, time-to-violation — real numbers from a real trained model.
4. Root-cause ranking: top 4–5 contributing parameters with plain-language rationale.
5. One recommendation: specific parameter + value + ramp rate, constraint-validated, with before/after
   risk, max deviation, and stabilization time.
6. 4–6 evidence tags on that recommendation, clickable to show the underlying evidence text.
7. Accept / Reject / Modify → persisted to a real audit log, visible in a simple table.
8. Deployed, reachable URL + a 90-second backup screen recording (see §14).

### Stretch — only after MVP is fully working and rehearsed, in this order:
1. Setpoint simulator (counterfactual "what-if" sliders) — highest demo value per hour spent.
2. Correlation / influence graph view — second highest value, ties directly to the novelty hook.
3. Similar historical transitions retrieval ("12 of 15 similar successful transitions kept X between A–B").
4. Recommendation-quality metrics panel (acceptance rate, etc.).
5. Second and third replay scenarios wired into the UI (success/failure), not just the demo event.

### Explicitly out of scope for 48 hours — do not build these:
- Full 7-page dashboard, model/system-health page, role-based access, rate limiting.
- GNN / GRU / TCN / Bayesian optimization / drift detection.
- Full unit+integration+e2e test suite. Write a handful of smoke tests for the risk math and constraint
  validator only — those are the two places a silent bug would be embarrassing on stage.
- Security hardening beyond input validation and no-hardcoded-secrets.
- Submission-size tooling, multi-environment CI/CD.
- The presentation deck — you already have the template and are handling that separately. Do not generate
  slide content until asked.

---

## 2. Hour-by-Hour Plan (48h, adjust ±2h per block but keep the order)

| Hours | Block |
|---|---|
| 0–2 | Repo scaffold, lock tech stack (§3), stub API, stub frontend shell, confirm everything boots |
| 2–8 | Synthetic data generator: 3 events, recipe constraints, operator actions, seeded interaction relationship (§5) |
| 8–14 | Feature engineering + train risk model + trajectory models + stabilization estimator; save artifacts |
| 14–18 | Recommendation engine: candidate generation, constraint validation, scoring, rationale text |
| 18–20 | Root-cause ranking + correlation/interaction discovery module |
| 20–22 | Backend API wiring, SQLite persistence, seed script, smoke tests on risk math + constraints |
| 22–32 | Frontend: Command Center page fully wired (chart, risk cards, root cause, recommendation, accept/reject/modify) |
| 32–36 | Stretch #1: Setpoint simulator |
| 36–40 | Stretch #2: Correlation/influence view |
| 40–44 | UI polish pass: motion, transitions, empty/loading/error states, responsive check, frontend-design critique pass (§10) |
| 44–46 | Deploy (Vercel + Render), full end-to-end smoke test, record 90s backup video |
| 46–48 | Buffer, rehearse the live pitch out loud twice, write the short README (§13) |

If you're behind schedule at hour 22, cut stretch items first — never cut MVP polish time.

---

## 3. Tech Stack (locked — do not re-litigate mid-build)

**Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy + SQLite, pandas, scikit-learn, LightGBM,
joblib. Use built-in `feature_importances_` for root-cause ranking; only add `shap` if the risk model is
done with hours to spare (it's a nice-to-have, not required — feature importance + rule-based rationale
text is sufficient to satisfy the brief's "rationale" requirement).

**Frontend:** React + Vite + TypeScript, Tailwind CSS, Recharts (faster to get right than ECharts in this
timeframe), Framer Motion, TanStack Query, lucide-react.

**Deployment:** Frontend → Vercel. Backend → Render (or Railway). CORS opened to the Vercel origin. A single
`seed_demo.py` script trains/loads models and populates SQLite on boot so the deployed instance always has
data — no judge should ever see an empty state unless they're specifically testing the empty state.

Do not introduce Docker, Kubernetes, message queues, or a second database. None of that is judge-visible.

---

## 4. Simplified Architecture

```text
Synthetic Generator (offline script)
        │  writes CSV + SQLite seed
        ▼
FastAPI backend
   ├── feature_service      (deviation, slope, rolling stats, ramp rate, interaction features)
   ├── risk_service          (LightGBM classifier → probability, direction, time-to-violation)
   ├── trajectory_service     (per-horizon LightGBM regressors → 30/60/120s forecast)
   ├── stabilization_service  (k-NN over historical events → remaining stabilization time)
   ├── rootcause_service      (feature importances + deviation/slope ranking → ranked list + text)
   ├── correlation_service    (Pearson/Spearman + lagged interaction feature → discovered relationships)
   ├── constraint_service     (recipe/actuator bounds check — hard reject on violation)
   ├── recommendation_service (candidate search → constraint filter → re-score with risk_service → rank)
   └── feedback_service       (accept/reject/modify persistence + audit query)
        │  REST JSON
        ▼
React frontend
   Command Center → Simulator (stretch) → Correlation view (stretch) → Audit table
```

---

## 5. Synthetic Data — Including the Novelty Hook

Generate 3 grade-change events, ~15–20 minutes each at 5-second resolution, deterministic seed.

**Event A — Success:** well-coordinated ramps, Basis Weight stays inside ±2.5% throughout, short
stabilization.

**Event B — Failure:** aggressive stock-flow ramp, delayed machine-speed response, Basis Weight overshoots
upper limit, long off-spec duration. Used for historical-comparison evidence, not the live demo.

**Event C — Recoverable (the demo event):** starts normal-looking, risk climbs mid-transition, GradeLens
catches it, operator accepts the recommendation, trajectory recovers. This is what you replay live for judges.

**Known/expected relationships to encode** (these are the "textbook" ones — necessary for realism, but not
your novelty claim):
- Stock-flow increase → Basis Weight rises after a short delay.
- Machine-speed increase → Basis Weight falls, roughly offsetting stock-flow effects.
- Steam pressure → moisture, with secondary effect on Basis Weight stability.
- Filler flow → Ash.

**The seeded novel relationship (build this deliberately — this is your "we found something new" moment):**

Encode a genuine **interaction effect**: neither the filler-flow ramp rate nor the steam-pressure slope
alone is a strong predictor of overshoot, but their **product, at a ~45-second lag**, is — and this
interaction is much stronger in Event B (failure) than Event A (success). Concretely:

```text
interaction_feature = filler_flow_ramp_rate(t) × steam_pressure_slope(t - 45s)
```

Only trigger amplified Basis Weight deviation in the generator when this joint interaction exceeds a
threshold — neither variable individually crossing its own threshold should be sufficient. Then make sure
the correlation/interaction discovery module (§8) actually surfaces this compound feature as a top-ranked
relationship, distinctly called out in the UI as "not part of any single existing control loop."

Label this honestly wherever it appears: *"This relationship was deliberately built into the demo dataset to
validate the discovery engine's sensitivity to compound effects — presented as a capability demonstration,
not a claim about a specific mill."* This keeps the claim intellectually honest while still giving you a real,
non-generic "aha" moment on stage.

**Also generate:** recipe constraint table (min/max/ramp-rate per parameter per grade), a handful of operator
action log rows, and basic data-quality flags (one deliberately-stale signal window, used to demonstrate the
degraded-mode fallback in §9).

---

## 6. Trimmed Data Model

Keep only these tables — drop the rest of the original 7-table schema for now:

```text
grade_change_events   (event_id, machine_id, source_grade, target_grade, recipe_id, start_time, end_time,
                        bw_old_target, bw_new_target, stabilization_seconds, off_spec_seconds,
                        max_deviation_pct, transition_outcome)

process_timeseries     (timestamp, event_id, basis_weight_actual, basis_weight_setpoint,
                        stock_flow_actual/setpoint, filler_flow_actual/setpoint,
                        steam_pressure_actual/setpoint, machine_speed_actual/setpoint,
                        moisture_actual/setpoint, ash_actual/setpoint, active_alarm_count,
                        scanner_quality_score)

recipe_constraints     (recipe_id, parameter_name, min_value, max_value, max_ramp_rate)

recommendations        (recommendation_id, event_id, timestamp, parameter_name, current_value,
                        recommended_value, recommended_ramp_rate, risk_before, risk_after,
                        stabilization_before, stabilization_after, confidence, rationale,
                        evidence_tags, status)

operator_feedback      (feedback_id, recommendation_id, response, operator_selected_value,
                        rejection_reason, timestamp)

discovered_relationships (source_parameter, target_parameter, strength, lag_seconds, is_interaction,
                        is_newly_discovered, sample_note)
```

---

## 7. ML — Kept Deliberately Lean

- **Risk model:** LightGBM binary classifier → `P(off-spec within 120s)`. Add direction (upper/lower/none)
  as a second small classifier or a simple rule on the trajectory sign. Calibration: skip Platt/isotonic
  unless there's spare time — report raw probability, label it clearly as "model-estimated."
- **Trajectory model:** three LightGBM regressors for +30s / +60s / +120s Basis Weight (three horizons is
  enough to show multi-horizon forecasting — don't build five).
- **Stabilization estimator:** k-nearest-neighbors over historical event feature vectors, weighted by
  distance. No training needed, fully explainable ("similar to 4 prior transitions with a median
  stabilization time of Xs"), fast to implement.
- **Leakage discipline:** split by whole event, not by row. With only 3 events, train risk/trajectory
  models on rows from all events but evaluate/report on held-out time windows within Event C to avoid
  literally training on the exact demo moment — document this clearly as a prototype-scale limitation.

---

## 8. Root Cause + Correlation Discovery

- Root cause: rank features by `feature_importances_` from the risk model, cross-check against current
  deviation/slope magnitude, and generate template-filled rationale text (see original brief's example
  format — "Stock flow — 38% contribution — ramp is 27% above the median successful trajectory").
- Correlation module: compute Pearson/Spearman + a single best time-lag for each parameter pair, plus the
  seeded interaction feature from §5. Rank by strength, threshold out weak relationships, tag each as
  `known` or `newly discovered`. This feeds both the root-cause panel and (stretch) the influence graph.

---

## 9. Recommendation Engine (simple, real, constraint-safe)

1. **Candidates:** for stock-flow setpoint, stock-flow ramp rate, and machine-speed setpoint, generate ~10
   candidates each via a small grid (±2%, ±4%, ±6%, ±8%, ±10% from current value). Grid search over ~30–50
   total candidates is more than fast enough — no need for Bayesian optimization.
2. **Constraint filter:** reject any candidate outside `recipe_constraints` min/max or exceeding max ramp
   rate. This must never be skipped, even under time pressure — it's cheap and it's explicitly required by
   the brief ("recommend setpoints to keep the system in safe operating limits").
3. **Re-score:** re-run the risk model and stabilization estimator on each valid candidate's projected
   feature vector to get risk-after and stabilization-after.
4. **Objective:** `score = w1*risk_after + w2*stabilization_after + w3*abs(change from current)` — pick the
   best, keep one runner-up as an "alternative" for the modify flow. Three weights, hardcoded and documented,
   is enough; don't build a full configurable multi-objective system.
5. **Evidence tags (trim to 6):** `Risk Model`, `Trajectory Forecast`, `Recipe Constraint`,
   `Historical Success`, `Process Correlation`, `Rule-Based Safety Check`. Each tag click reveals 1–2
   sentences of real supporting data, not filler text.

---

## 10. Frontend & UI/UX — Use the `frontend-design` skill, not a generic template

Before writing any UI code, run the `frontend-design` skill's own process: brainstorm a small token system
(4–6 named colors, 2 typefaces, one layout concept, one signature element) grounded specifically in a
**process-control-room** subject — not the generic AI-dashboard defaults (warm cream + terracotta, near-black
+ neon accent, or broadsheet/newspaper hairlines). Direction to build from, not exact hex codes to copy:

- Base: dark graphite/navy control-room panels, not pure black — should feel like a real SCADA/HMI screen,
  not a marketing site.
- Status colors carry real meaning and never stand alone — always pair color with a text label or icon
  (amber = warning, red = critical, green = stable, blue = predicted/model output).
- Forecasts are visually distinct from measurements everywhere they appear (e.g., dashed vs. solid lines) —
  this is a functional requirement, not decoration, since judges need to instantly tell "actual" from
  "predicted."
- Pick one **signature element** the page is remembered by — the strongest candidate here is the live Basis
  Weight trajectory chart itself (actual line, setpoint, spec limits, dashed forecast, and a distinct
  recommended-path line all in one view) — make that genuinely good rather than spreading equal effort
  across five mediocre charts.
- Motion: orchestrated, not scattered. Good candidates — a smooth chart transition when replay advances, a
  staged reveal of root-cause bars, a clear before/after animation when a recommendation is accepted
  (numbers visibly counting from "before" to "after"), subtle hover states on cards. Respect reduced-motion
  preferences. Do not animate everything; pick 3–4 moments that matter and make them land.
- Quality floor regardless of how much time is left: responsive down to a reasonable tablet width, visible
  keyboard focus states, real loading/empty/error states (no blank white screens), no placeholder buttons.

Reusable components (keep this list short): `RiskBadge`, `MetricCard`, `TrajectoryChart`, `RecommendationCard`,
`EvidenceTag`, `RootCauseBar`, `ConstraintPill`, `AuditTable`.

If you end up building this in a different tool later (e.g. an agentic coding environment) that has its own
design-assist skill under a different name, apply the same principles above — the constraint is the design
process (token system → grounded in the subject → one signature → restrained motion), not the specific tool name.

---

## 11. Trimmed API Surface

```text
GET  /health
GET  /grade-changes
GET  /grade-changes/{event_id}
GET  /grade-changes/{event_id}/timeseries
POST /predictions/risk
POST /predictions/trajectory
GET  /grade-changes/{event_id}/root-causes
GET  /grade-changes/{event_id}/recommendations
POST /recommendations/generate
POST /recommendations/{id}/accept
POST /recommendations/{id}/reject
POST /recommendations/{id}/modify
POST /simulation/setpoints           (stretch)
GET  /correlations                    (stretch)
GET  /audit/recommendations
```

Sixteen endpoints, all directly load-bearing for something a judge will see. Nothing speculative.

---

## 12. Fallback / Degraded-Mode Behavior (keep this — it's cheap insurance)

Wrap model inference in try/except. If a model file is missing or a required signal is stale/missing, fall
back to a simple rule-based estimate (e.g., threshold on current deviation + slope) and **visibly label the
response** `model_mode: "demo"` or `"degraded"` instead of `"trained"`. The frontend should show this mode
plainly. This single feature does a lot of credibility work with technical judges for very little build time.

---

## 13. Documentation Footprint (minimal — do not over-invest)

- **README:** what it is, the deployed URL, demo credentials if any, how to run locally, one architecture
  diagram (the one in §4), what's synthetic and why, what's MVP vs stretch, known limitations. Keep it to
  roughly one scroll-length page.
- **One-page technical summary (PDF or Markdown, not a 24-section document):** problem → approach →
  architecture diagram → the seeded-interaction novelty explanation → key metrics → limitations. This is
  enough to satisfy the brief's "document the building blocks" requirement without eating build hours.
- Presentation deck: you already have the template — bring it to me separately once the app is stable and
  I'll help fill it with the real numbers/screenshots from your working build, not before.

---

## 14. Demo Script (rehearse this out loud at least twice before submission)

1. Open on Event C already loaded — never make judges wait on an upload step.
2. Press play. Narrate: "Individually, none of these values look wrong yet."
3. Risk climbs — call out the number and the countdown-to-violation.
4. Root cause panel appears — point at the interaction feature specifically: "this is a compound effect
   between filler-flow ramp and steam-pressure slope, 45 seconds apart — not something any single existing
   loop is watching for."
5. Recommendation card appears with before/after numbers.
6. Click 2–3 evidence tags live — show it isn't a black box.
7. Accept it → animated before/after → audit table updates in real time.
8. If time allows (stretch built): open the simulator, nudge a slider, show the counterfactual trajectory
   update live.
9. Close with the one-line business framing: estimated minutes of off-spec time avoided on this transition,
   clearly labeled as a model-estimated prototype figure.

Have the 90-second backup recording ready and tested in case the live deployment hiccups during judging —
this single safeguard prevents the most common way hackathon teams lose points on demo day.

---

## 15. Non-Negotiable Guardrails

- Never fabricate live-looking numbers client-side. Every displayed value comes from the backend, the
  synthetic generator, or the simulation endpoint.
- Never skip constraint validation on a recommendation, even under time pressure.
- Never claim GradeLens replaces or writes to the live QCS/MPC — advisory-only, stated explicitly in the UI
  and docs.
- Never present the seeded interaction relationship as a real plant finding — label it as a capability
  demonstration.
- Stop building stretch features the moment MVP polish or demo rehearsal time is at risk.
