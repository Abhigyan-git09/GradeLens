# GradeLens — Round 2: Fix, Polish, and Finish (not a rewrite)

You already built the full GradeLens skeleton — data model, FastAPI backend, ML models, React dashboard,
accept/reject/modify audit flow. The architecture is fundamentally sound. What's broken is a specific,
countable list of wiring bugs sitting underneath a generic-looking UI, not a design problem that needs
starting over.

**Read this whole document before changing anything.** Fix bugs in the order given — several of the visual
symptoms you'd otherwise chase individually are actually caused by the same one or two root issues. Do not
add any new feature (§5) until every item in §2 is fixed and verified.

---

## 0. What this project actually has to prove (recap of the real hackathon brief)

The brief asks for six things — check your build against these literally, not against feature count:

1. Predict when Basis Weight is at risk of going off-spec (>2.5% from setpoint) during a grade change, and
   recommend corrective action before the limit is exceeded.
2. Recommend setpoints that keep the system in safe operating limits.
3. Reduce stabilization time to reach steady state.
4. Provide rationale behind every prediction/recommendation.
5. **Tag every suggestion with its possible source of inference** (historical data, recipe, etc.).
6. **Let the user accept or reject a suggestion, and record that response to evaluate suggestion quality.**

Deliverables #5 and #6 are currently broken or partial in your build (see §2, bugs #2 and #11) — fix those
before anything else, they're literally graded requirements, not nice-to-haves.

---

## 1. Current state, honestly

From the screenshots: the risk number displays, the chart renders, accept/reject/modify persists to the
audit log correctly (this part is genuinely solid — don't touch `routers/recommendations.py`, it's fine).
But the recommendation's before/after numbers don't change, root cause shows one circular item, the
correlation graph shows only textbook relationships behind a static "Physics Model" label, evidence tags
are empty, stabilization is stuck on "Estimating...", and the influence graph renders as unstyled white
boxes. All of these are real, fixable, mostly small bugs — not signs the underlying approach is wrong.

---

## 2. Confirmed bugs — fix in this order

### Bug 1 — Simulation only ever handles `stock_flow`, never `machine_speed` (highest priority — this alone explains most of what looked broken on screen)

**Where:** `backend/app/services/recommendation_engine.py`, lines 82–87, and
`frontend/src/pages/CommandCenter.tsx`, lines 228–230 and 251–254.

**What's wrong:** Both the backend's counterfactual re-scoring and the frontend's live simulator slider only
know how to perturb `stock_flow_ramp`. When the top-ranked candidate is `machine_speed` (as it was in your
screenshots), `sim_features` is left as an exact copy of the current state — so `risk_after == risk_before`
and `stabilization_after == stabilization_before` every single time. This is a deterministic no-op, not a
flaky bug.

**Fix:** Generalize both places to handle whichever parameter the candidate actually is. Backend:

```python
# recommendation_engine.py — replace the stock_flow-only block
sim_features = current_features.copy()
if cand["parameter"] == "stock_flow":
    sim_features["stock_flow_ramp"] = (cand["value"] - latest_pt.stock_flow_actual) / 15.0
elif cand["parameter"] == "machine_speed":
    sim_features["machine_speed_ramp"] = (cand["value"] - latest_pt.machine_speed_actual) / 15.0
```

This requires `feature_service.extract_features` to actually produce a `machine_speed_ramp` feature (it
currently doesn't track machine speed at all — see Bug 4), and the risk/trajectory models need that feature
in their training input. Do this fix together with Bug 4, not in isolation, or you'll just move the same bug
from `stock_flow` to `machine_speed` in reverse.

On the frontend, generalize `simulatedValue` to carry a `{ parameter, value }` pair instead of a bare number,
and branch the override the same way in both the risk and trajectory query functions.

**Verify:** Generate a recommendation for machine speed specifically, drag the simulator slider, and confirm
the risk/stabilization numbers actually move.

---

### Bug 2 — Evidence tags are saved to the database but never reach the UI

**Where:** `backend/app/models/domain.py` line 82 vs. `backend/app/schemas/domain.py` line 37.

**What's wrong:** The SQLAlchemy relationship is named `evidence`:
```python
evidence = relationship("EvidenceTag", back_populates="recommendation", cascade="all, delete-orphan")
```
but the response schema (and the frontend) expects `evidence_tags`. Pydantic's `from_attributes=True` looks
for an attribute literally called `evidence_tags` on the ORM object, doesn't find it, and silently falls
back to the field's default (`[]`) — no error, no crash, just quietly empty. This is deliverable #5 from the
actual brief and it's currently non-functional.

**Fix — pick one, they're equivalent, just be consistent everywhere it's referenced:**
```python
# Option A — rename the ORM relationship to match the schema
evidence_tags = relationship("EvidenceTag", back_populates="recommendation", cascade="all, delete-orphan")
```
Update the `back_populates` target on `EvidenceTag.recommendation` to match if you rename it.

**Verify:** Generate a recommendation, hit the `/recommendations/generate` response directly (or check the
Network tab), confirm `evidence_tags` is a populated array of 6 objects, not `[]`.

---

### Bug 3 — Root cause lists the target variable as its own cause

**Where:** `backend/app/services/rootcause_service.py`, lines 15 and 52.

**What's wrong:** `bw_deviation` (how far basis weight currently is from its own setpoint) is included as a
candidate "root cause" alongside actual process inputs. Since it's normalized against a much smaller
expected range than the other features, it dominates and gets reported as "Basis Weight Deviation — 99%
contribution" — which is circular: it's the thing you're trying to explain, not a cause of it.

**Fix:** Remove `bw_deviation` from the set of things eligible to be reported as a root cause. It can still
be used as a model *input* feature (that's legitimate), just don't let it appear in the ranked output list.
Root cause should only ever surface actual process levers: stock flow, machine speed, steam pressure, filler
flow, and the interaction feature. This also means the feature set needs to grow — see Bug 4.

**Verify:** Root cause list should never contain "Basis Weight Deviation" or "Basis Weight Velocity" as a
top entry; it should list actual input parameters.

---

### Bug 4 — The feature set is too narrow, and it's disconnected from what the recommendation engine tries to recommend

**Where:** `backend/ml/feature_service.py`, `backend/seed_demo.py` (`train_models`).

**What's wrong:** The entire ML pipeline only ever sees four features: `bw_deviation`, `bw_slope`,
`stock_flow_ramp`, `interaction_feature`. Machine speed, steam pressure, and filler flow are never
individually represented as model inputs — only baked into the one combined interaction feature. But the
recommendation engine searches over `machine_speed` as a candidate parameter (Bug 1), and root cause is
supposed to be able to name it (Bug 3) — there's no way for either of those to work correctly if the
underlying model never saw machine speed as a feature in the first place.

**Fix:** Add `machine_speed_ramp`, `steam_pressure_slope` (already computed, just not fed to the models —
see line 54 of `feature_service.py`, it's returned but unused in training), and `filler_flow_ramp` as first-class
features in `extract_features()`, and include all of them in `X_risk`/`X_traj`/`X_stab` in `seed_demo.py`.
Retrain after this change — old `.joblib`/`.txt` artifacts trained on the narrower feature set are now
stale and must be deleted and regenerated.

**Verify:** After retraining, root cause should be able to rank machine speed or steam pressure as a top
contributor when they're actually the ones moving.

---

### Bug 5 — The interaction feature's live formula doesn't match how it was actually seeded

**Where:** `backend/ml/feature_service.py` lines 34–48 vs. `backend/seed_demo.py` lines 78–82.

**What's wrong:** The synthetic generator computes the hidden filler/steam interaction as
`(point[i-1] - point[i-10])` for both variables — a 45-second **trailing window**, both measured over the
same span, ending at the current moment. But `feature_service.extract_features()` tries to compute something
more literally "lagged" (steam 45s ago vs. filler now), using a shorter window, and it requires 12+ points to
even attempt the intended calculation — every caller in the codebase (`recommendation_engine.py`,
`rootcause_service.py`) only fetches 10 points, so it always falls into the degraded 5-second-window
fallback branch. The result: the feature the model was actually trained to recognize and the feature
computed at serving time are not the same calculation. This is very likely why the correlation module isn't
reliably surfacing the seeded relationship in your testing.

**Fix:** Pick one definition and make `feature_service.py`, `correlation_service.py`, and `seed_demo.py`
compute it identically — same window size, same point offsets. The simplest fix given how it was actually
seeded: match the generator's own definition exactly (45s trailing window for both filler ramp and steam
slope, measured at the same instant), and fetch at least 11 points everywhere this feature is needed instead
of 10.

**Verify — don't just assume this is fixed once it compiles.** After aligning the formulas and retraining,
add a temporary debug print of the correlation coefficient the correlation module computes for Event C, and
confirm it actually clears whatever threshold you're using to decide "newly discovered" before trusting it
in a live demo.

---

### Bug 6 — Correlation graph always analyzes Event C, regardless of which event is on screen

**Where:** `backend/app/routers/stretch.py`, line 22.

**What's wrong:** `correlation_service.discover_relationships("EVT-003-RECOVERABLE", db)` is hardcoded. If a
judge switches to Event A or B, the influence graph keeps showing Event C's relationships (or stale data
from whenever it last ran) with no connection to what's actually being viewed.

**Fix:** Accept `event_id` as a query parameter on `GET /correlations` and pass through the currently
selected event from the frontend, same pattern as `/grade-changes/{event_id}/root-causes`.

---

### Bug 7 — "Physics Model" badge is hardcoded text, not derived from the actual data

**Where:** `frontend/src/pages/CommandCenter.tsx`, line 746.

**What's wrong:**
```tsx
<span className="evidence-tag bg-accent/10 border-accent/20 text-accent">Physics Model</span>
```
This renders unconditionally regardless of what `correlations` actually contains — even once the seeded
interaction relationship is showing up correctly (Bug 5), this label would still misleadingly say "Physics
Model" for the whole panel.

**Fix:** Remove the static badge. Instead, badge each *edge* individually based on its own
`is_newly_discovered` flag — e.g. "Known relationship" for the textbook stock-flow/speed edges, "Newly
discovered" (visually distinct, e.g. your existing amber "Anomaly Discovered" chip inside `InfluenceGraph.tsx`
is the right pattern) for the seeded one. This is a more honest and more interesting story than one flat
label for the whole graph.

---

### Bug 8 — Stabilization panel has nothing to call

**Where:** `backend/app/routers/predictions.py` (no stabilization route exists) and
`frontend/src/pages/CommandCenter.tsx` line 494 (`<span>Estimating...</span>` — literal static text, no query).

**What's wrong:** `stabilization_service.py` is fully implemented and works — it's just never exposed as its
own endpoint, and the frontend never calls anything for this panel at all.

**Fix:** Add to `predictions.py`:
```python
@router.post("/stabilization", response_model=StabilizationSchema)
def predict_stabilization(features: Dict):
    from ml.stabilization_service import stabilization_service
    return stabilization_service.estimate_stabilization(features)
```
Wire the frontend panel to call it the same way the risk/trajectory queries already work, using the same
feature payload.

---

### Bug 9 — Setpoint simulator backend is a stub

**Where:** `backend/app/routers/stretch.py` line 14: `return {"status": "not_implemented"}`.

**What's wrong:** In practice you routed around this stub by calling `/predictions/risk` and
`/predictions/trajectory` directly from the frontend (which is fine), so this endpoint may simply be dead
code at this point. Either implement it properly if something still calls it, or delete it — don't leave an
endpoint in the API surface that visibly returns "not implemented," since a judge poking at your API docs
(FastAPI's `/docs` page will show it) will see that immediately.

---

### Bug 10 — Event B's failure isn't caused by anything

**Where:** `backend/seed_demo.py`, line 76: `if ev["outcome"] == "failure" and i > 100: bw_actual += (i - 100) * 0.1`.

**What's wrong:** This is a bare linear drift with no connection to any process variable. Stock flow, filler
flow, and steam pressure all sit at 0.0% deviation the entire time (matches your Image 1 screenshot exactly).
Root cause and correlation analysis are *correctly* returning nothing meaningful here — there's genuinely
nothing to find, because nothing in the data causes it.

**Fix — this is also a good opportunity to make Event B do useful work for you (see §5):** redesign the
failure mechanism so it's driven by an actual variable relationship instead of a timer — e.g. an
aggressive stock-flow ramp without a compensating machine-speed change, using the *known* stock-flow→basis-weight
relationship. This gives you two distinct, legible stories: Event B demonstrates the system correctly
catching a **known** loop causing failure, Event C demonstrates it catching the **novel** compound
interaction. Right now Event B just looks broken; with this change it becomes a second piece of evidence
your system works, not a landmine a curious judge might click into.

---

### Bug 11 — No train/test split, no evaluation output anywhere

**Where:** `backend/seed_demo.py`, `train_models()`.

**What's wrong:** All three events are used for training with zero holdout, and there's no accuracy,
precision, recall, or any other metric printed or stored anywhere. You currently have no evidence — not even
for yourselves — of whether the risk model generalizes at all, versus memorizing three near-identical curves.

**Fix (cheap, don't over-build this):** Hold out the last ~20% of timesteps from each event chronologically,
train on the rest, and print basic classification metrics (accuracy, precision, recall) to the console when
`train_models()` runs. You don't need a dashboard page for this — a console log you can screenshot for your
technical documentation is enough to honestly claim you evaluated the model instead of just shipping it.

---

## 3. The UI needs a real pass, not more decoration

Being direct: the current look (dark navy background, glowing gradient risk ring, teal accent everywhere) is
the generic "AI dashboard template" look — it doesn't read as a purpose-built industrial tool. Two concrete,
verified problems on top of the general aesthetic issue:

**The influence graph renders as unstyled white boxes with black text (Image 4).** This is a specific,
diagnosable bug, not just bad taste: `InfluenceGraph.tsx` sets Tailwind classes like `bg-[#1e293b] text-white`
on the node objects, but React Flow's own stylesheet (`reactflow/dist/style.css`, imported at the top of the
file) applies default styling to `.react-flow__node` / `.react-flow__node-default` that wins the specificity
tie depending on CSS load order — so your custom classes are silently overridden by the library's stock
white/black defaults. Fix by targeting `.react-flow__node` directly in your global CSS (not just the
per-node `className` prop) with `!important` if needed, or by using a custom node type instead of the
default renderer.

**There's a stray disabled-looking button reading roughly "Reject File" in the bottom-right of the graph
panel** that doesn't belong to this view. I couldn't trace it to a specific line from static code alone —
open it in the browser inspector and check whether it's a leftover/duplicated component, a z-index
stacking issue where the Reject button from the recommendation card is bleeding through, or a React Flow
attribution element that's been mis-styled. Remove or fix whatever it turns out to be.

**Also fix while you're in these files:** unrounded raw floats displayed directly in the UI
(`625.5688161073714`, `569.4476276488094`, `13.93` shown with no consistent decimal precision) — round every
displayed number to a sensible precision (1 decimal for flow rates, 0–1 for percentages). This is a five
minute fix and its absence is exactly the kind of detail that reads as unfinished.

**For the broader visual pass:** actually run the `frontend-design` skill's own process this time — pick a
real token system (specific colors, specific typefaces, one deliberate layout idea) grounded in a
process-control-room subject, rather than defaulting to dark-navy-plus-teal-glow. Forecasts must stay
visually distinct from actual measurements everywhere they appear (dashed vs. solid, already partially done
on the main chart — extend this convention everywhere trajectories appear). Pick **one** signature visual
moment and make it excellent — the live Basis Weight trajectory chart is the strongest candidate — rather
than spreading equal polish across every panel. Keep motion restrained and purposeful: a real animated
before/after transition when a recommendation is accepted (numbers visibly counting from "before" to
"after") would do more for the demo than any additional decorative effect, and right now that transition
doesn't exist at all — the numbers just render statically.

---

## 4. Do these things after §2 and §3 are done and verified, not before

Only touch this section once every bug above is fixed and you've personally re-run the full demo flow (open
app → replay Event C → risk climbs → root cause shows real parameters → recommendation shows real before/after
numbers → evidence tags populate → accept → audit log updates → correlation graph shows the seeded
interaction correctly labeled) without a single visibly broken or static-looking value.

## 5. Worthwhile additions, ranked (only if time remains)

1. **Fix Event B into a "known-loop" failure case (see Bug 10)** — cheap, and turns a currently-broken path
   into a second piece of evidence instead of a landmine.
2. **Model evaluation metrics from Bug 11, surfaced as a small line in the docs or a tiny badge** — "trained
   on N samples across 3 transitions, holdout precision X%, recall Y%" is a real credibility signal for very
   little build cost.
3. **A one-line business-impact framing after a recommendation is accepted** — e.g. "estimated ~X minutes of
   off-spec production avoided on this transition," clearly labeled as model-estimated. This is the kind of
   detail that moves a judge from "interesting tech" to "I understand why this matters."
4. **A recommendation-quality summary** (acceptance rate, rejection rate from the audit log you already have
   working) — you have the raw data already in `OperatorFeedback`; this is mostly a read-only aggregation
   query plus one small panel, not a new subsystem.

**Do not** start any of these before §2 and §3 are fully done. Do not add anything not listed here — no new
pages, no new models, no new panels beyond what's above. The project has enough surface area already; what it
needs now is for the surface area it has to actually work and look intentional.

## 6. Final check before calling this done

Walk through the original acceptance criteria one more time, specifically:
- Every suggestion has real, populated evidence-source tags (Bug 2).
- The before/after impact of a recommendation is a real, different number, for every parameter type the
  engine can recommend, not just stock flow (Bug 1, Bug 4).
- Root cause never lists Basis Weight itself as its own cause (Bug 3).
- The correlation graph correctly and honestly distinguishes known vs. newly-discovered relationships,
  scoped to whichever event is actually selected (Bug 5, 6, 7).
- No panel is permanently stuck on a placeholder string (Bug 8).
- No API endpoint visibly returns "not implemented" (Bug 9).
- Every event in the dropdown tells a coherent, non-broken story if a judge clicks into it (Bug 10).
