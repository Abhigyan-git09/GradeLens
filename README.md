# GradeLens

Grade Change Intelligence in Paper Making Process.

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
Synthetic Generator (offline script)
        │  writes CSV + SQLite seed
        ▼
FastAPI backend
   ├── feature_service      (deviation, slope, rolling stats, interaction features)
   ├── risk_service          (LightGBM classifier → probability, direction, time-to-violation)
   ├── trajectory_service    (per-horizon LightGBM regressors → 30/60/120s forecast)
   ├── stabilization_service (k-NN over historical events → remaining stabilization time)
   ├── rootcause_service     (feature importances + deviation/slope ranking → ranked list + text)
   ├── correlation_service   (Pearson/Spearman + lagged interaction feature → discovered relationships)
   ├── constraint_service    (recipe/actuator bounds check — hard reject on violation)
   ├── recommendation_service(candidate search → constraint filter → re-score → rank)
   └── feedback_service      (accept/reject/modify persistence + audit query)
        │  REST JSON
        ▼
React frontend
   Command Center → Simulator (stretch) → Correlation view (stretch) → Audit table
```

## What's Synthetic

All data in this prototype is synthetically generated to demonstrate the system's capabilities.
The seeded interaction relationship (filler-flow ramp × steam-pressure slope at 45s lag) was
deliberately built into the demo dataset to validate the discovery engine's sensitivity to
compound effects — presented as a capability demonstration, not a claim about a specific mill.

## Advisory Only

GradeLens does not replace or write to any live QCS/MPC system. It is advisory-only.
