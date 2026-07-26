# GradeLens

<p align="center">
  <em>Explainable Grade Change Intelligence for Paper Manufacturing</em>
</p>

![Command Center](docs/main_dashboard.png)

GradeLens is a sophisticated, AI-driven advisory layer designed to predict and prevent out-of-spec basis weight incidents during automatic grade transitions in paper manufacturing. Built with a strict focus on **safety**, **explainability**, and **actionability**, GradeLens operates entirely in an advisory capacity, putting critical insights directly in front of the operator before physical changes are made.

---

## 🏭 Features

- **Trajectory Forecasting**: Anticipates basis weight drift 30, 60, and 120 seconds into the future.
- **Fail-Closed Recommendation Engine**: Suggests optimal setpoint adjustments to prevent spec deviations. Crucially, the engine refuses to recommend changes for parameters that lack pre-defined safety bounds in the `RecipeConstraint` table.
- **Scenario Lab**: Operators can construct bounded setpoint scenarios and run what-if analyses to simulate the ramp rate and stabilization times of proposed adjustments.
- **Dynamic Evidence & Explainability**: Recommendations are backed by dynamic evidence tags, calculating live confidence intervals and projected business impact (e.g., "$4,500/hr saved").
- **Influence Graph Correlation**: Automatically discovers and maps linear and compound (lagged) relationships between machine actuators and paper quality.

### 🧪 Scenario Lab
The interactive Scenario Lab allows operators to experiment with grade change targets safely.
![Scenario Lab](docs/scenario_lab.png)

### 📊 Explainability & Evidence
GradeLens is completely transparent about its model pipeline, data splits, and causal processing flows.
![Evidence Page](docs/evidence_page.png)

## 🚀 Quick Start (Local Development)

The project consists of a FastAPI backend and a React (Vite) frontend.

### 1. Backend Setup

```bash
cd backend
# Install dependencies
pip install -r requirements.txt
# Start the API server
uvicorn app.main:app --reload --port 8000
```
*Note: The backend will automatically bootstrap the SQLite database, generate synthetic timeseries data, and train the Random Forest & KNN models on first launch.*

### 2. Frontend Setup

```bash
cd frontend
# Install dependencies
npm install
# Start the dev server
npm run dev
```

## 🐳 Deployment (Docker)

GradeLens is production-ready via Docker Compose. The configuration handles cross-container networking and creates a persistent volume for the SQLite database.

```bash
# From the root directory
docker compose up --build -d
```
Access the application at `http://localhost:8080`.

## 🏗️ Architecture

```text
Synthetic Generator (offline script)
        │  writes CSV + SQLite seed
        ▼
FastAPI backend
   ├── feature_service       (deviation, slope, rolling stats, interaction features)
   ├── risk_service          (Random Forest classifier → probability, direction)
   ├── trajectory_service    (per-horizon regressors → 30/60/120s forecast)
   ├── stabilization_service (k-NN over historical events → remaining stabilization time)
   ├── rootcause_service     (feature importances + deviation/slope ranking → ranked list + text)
   ├── correlation_service   (Pearson/Spearman + lagged interaction feature → relationships)
   ├── constraint_service    (recipe/actuator bounds check — hard reject on violation)
   ├── recommendation_service(candidate search → constraint filter → re-score → rank)
   └── feedback_service      (accept/reject/modify persistence + audit query)
        │  REST JSON
        ▼
React frontend
   Command Center → Scenario Lab → Influence Graph → Intelligence/Evidence
```

## ⚠️ Disclaimer

- **Advisory Only**: GradeLens does not replace or write to any live QCS/MPC system. It operates purely as an advisory dashboard.
- **Synthetic Data**: All data in this prototype is synthetically generated to demonstrate the system's capabilities. The seeded interaction relationships (e.g., filler-flow ramp × steam-pressure slope at 45s lag) were deliberately built to validate the discovery engine's sensitivity to compound effects.
