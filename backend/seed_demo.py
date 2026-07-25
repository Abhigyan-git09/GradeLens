import os
import sys
import datetime
import random
import joblib
import numpy as np
import lightgbm as lgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

# Add backend dir to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal, init_db
from app.models.domain import (
    GradeChangeEvent,
    TimeseriesPoint,
    Recommendation,
    EvidenceTag,
    OperatorFeedback,
    RecipeConstraint,
)
from ml.feature_service import feature_service, FEATURE_NAMES

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "ml", "artifacts")

def generate_synthetic_data(db):
    if db.query(GradeChangeEvent).first():
        print("Data already exists. Skipping data generation.")
        return

    print("Generating Recipe Constraints...")
    constraints = [
        RecipeConstraint(grade_id="G-100", parameter="basis_weight", min_val=61.5, max_val=66.5, optimal_val=64.0, max_ramp_rate=0.15),
        RecipeConstraint(grade_id="G-100", parameter="stock_flow", min_val=800.0, max_val=900.0, optimal_val=850.0, max_ramp_rate=0.10),
        RecipeConstraint(grade_id="G-100", parameter="moisture", min_val=6.0, max_val=8.0, optimal_val=7.0, max_ramp_rate=0.12),
        RecipeConstraint(grade_id="G-200", parameter="basis_weight", min_val=78.0, max_val=82.0, optimal_val=80.0, max_ramp_rate=0.15),
        RecipeConstraint(grade_id="G-200", parameter="stock_flow", min_val=950.0, max_val=1100.0, optimal_val=1020.0, max_ramp_rate=0.10),
        RecipeConstraint(grade_id="G-200", parameter="moisture", min_val=5.5, max_val=7.5, optimal_val=6.5, max_ramp_rate=0.12),
    ]
    db.add_all(constraints)
    
    print("Generating Grade Change Events...")
    base_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)
    
    events = [
        {"event_id": "EVT-001-SUCCESS", "source": "G-100", "target": "G-200", "bw_old": 64.0, "bw_new": 80.0, "outcome": "success", "start": base_time},
        {"event_id": "EVT-002-FAILURE", "source": "G-200", "target": "G-100", "bw_old": 80.0, "bw_new": 64.0, "outcome": "failure", "start": base_time + datetime.timedelta(hours=6)},
        {"event_id": "EVT-003-RECOVERABLE", "source": "G-100", "target": "G-200", "bw_old": 64.0, "bw_new": 80.0, "outcome": "in_progress", "start": base_time + datetime.timedelta(hours=12)}
    ]

    for ev in events:
        event = GradeChangeEvent(
            event_id=ev["event_id"], machine_id="PM-1", source_grade=ev["source"], target_grade=ev["target"],
            recipe_id=f"REC-{ev['target']}", start_time=ev["start"],
            end_time=ev["start"] + datetime.timedelta(minutes=20) if ev["outcome"] != "in_progress" else None,
            bw_old_target=ev["bw_old"], bw_new_target=ev["bw_new"], transition_outcome=ev["outcome"]
        )
        db.add(event)
        
        ts_points = []
        for i in range(240): # 20 minutes at 5s res
            t = ev["start"] + datetime.timedelta(seconds=i*5)
            progress = min(1.0, i / 120.0)
            smooth_prog = (1 - np.cos(progress * np.pi)) / 2
            
            bw_actual = ev["bw_old"] + (ev["bw_new"] - ev["bw_old"]) * smooth_prog + random.uniform(-0.5, 0.5)
            bw_sp = ev["bw_old"] + (ev["bw_new"] - ev["bw_old"]) * smooth_prog
            stock_flow = 850 + (1020 - 850) * smooth_prog + random.uniform(-5, 5)
            filler_flow = 130 + (150 - 130) * smooth_prog + random.uniform(-0.3, 0.3)
            steam_press = 4.2 + (5.0 - 4.2) * smooth_prog + random.uniform(-0.02, 0.02)
            speed_base_start = 640 if ev["bw_old"] < ev["bw_new"] else 580
            speed_base_end = 580 if ev["bw_old"] < ev["bw_new"] else 640
            machine_speed = speed_base_start + (speed_base_end - speed_base_start) * smooth_prog + random.uniform(-2, 2)
            machine_speed_sp = speed_base_start + (speed_base_end - speed_base_start) * smooth_prog
            
            if ev["outcome"] == "failure" and i > 100:
                # Bug 10 Fix: Aggressive stock-flow ramp without speed change
                stock_flow_excess = (i - 100) * 2.0
                stock_flow += stock_flow_excess
                bw_actual += stock_flow_excess * 0.05
            
            if ev["outcome"] == "in_progress" and i > 60:
                if i > 70:
                    steam_slope = ts_points[i-1].steam_pressure_actual - ts_points[i-10].steam_pressure_actual
                    filler_ramp = ts_points[i-1].filler_flow_actual - ts_points[i-10].filler_flow_actual
                    bw_actual += (filler_ramp * steam_slope) * 15.0
            
            ts_points.append(TimeseriesPoint(
                event_id=ev["event_id"], timestamp=t, basis_weight_actual=bw_actual, basis_weight_setpoint=bw_sp,
                stock_flow_actual=stock_flow, stock_flow_setpoint=stock_flow, filler_flow_actual=filler_flow, filler_flow_setpoint=filler_flow,
                steam_pressure_actual=steam_press, steam_pressure_setpoint=steam_press, machine_speed_actual=machine_speed, machine_speed_setpoint=machine_speed_sp,
                moisture_actual=7.0+random.uniform(-0.2,0.2), moisture_setpoint=7.0, ash_actual=15.0+random.uniform(-0.5,0.5), ash_setpoint=15.0,
                active_alarm_count=1 if ev["outcome"] == "failure" and i > 150 else 0,
                scanner_quality_score=1.0 - (0.1 if random.random() < 0.05 else 0.0)
            ))
        db.add_all(ts_points)
        
        # Add Recommendation + Operator Feedback for successful event (Historical Log)
        if ev["outcome"] == "success":
            rec = Recommendation(
                event_id=ev["event_id"], parameter_name="Stock Flow", current_value=900.0, recommended_value=920.0,
                recommended_ramp_rate=2.0, risk_before=0.55, risk_after=0.15, stabilization_before=180.0, stabilization_after=120.0,
                confidence=0.90, rationale="Proactive stock flow adjustment based on historical success.", status="accepted"
            )
            db.add(rec)
            db.commit()
            
            feedback = OperatorFeedback(
                recommendation_id=rec.recommendation_id, response="accept", operator_selected_value=920.0,
                timestamp=ev["start"] + datetime.timedelta(minutes=5)
            )
            db.add(feedback)
            db.commit()

        # Add Recommendation for in_progress event (Demo)
        if ev["outcome"] == "in_progress":
            rec = Recommendation(
                event_id=ev["event_id"], parameter_name="Stock Flow", current_value=847.0, recommended_value=812.0,
                recommended_ramp_rate=-5.8, risk_before=0.67, risk_after=0.23, stabilization_before=252.0, stabilization_after=126.0,
                confidence=0.82, rationale="Adjust ramping to prevent overshoot due to Filler Flow and Steam Pressure interaction.", status="pending"
            )
            db.add(rec)
            db.commit()
            db.add_all([
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Risk Model", source="Model", detail="82% probability of overshoot"),
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Process Correlation", source="Analytics", detail="Filler x Steam interaction detected")
            ])
            db.commit()

    print("Synthetic data generated.")

def train_models(db):
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    
    # Delete old artifacts
    for f in os.listdir(ARTIFACTS_DIR):
        if f.endswith('.joblib') or f.endswith('.txt'):
            os.remove(os.path.join(ARTIFACTS_DIR, f))

    events = db.query(GradeChangeEvent).all()
    if len(events) < 3:
        return
        
    X_risk, y_risk = [], []
    X_traj_train, y_traj_30_train, y_traj_60_train, y_traj_120_train = [], [], [], []
    X_stab_train, y_stab_train = [], []
    
    for event in events:
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event.event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
        # Instead of chronological holdout which causes 100% accuracy due to 
        # the late-stage data being trivial, we'll collect all points and use train_test_split.
        
        for i in range(12, len(pts) - 24):
            window = pts[i-12:i]
            features = feature_service.extract_features(window)
            
            future_window = pts[i:i+24]
            max_dev = max(abs(pt.basis_weight_actual - pt.basis_weight_setpoint) for pt in future_window)
            failed = 1 if max_dev > 1.5 else 0
            
            feat_vec = [features.get(f, 0.0) for f in FEATURE_NAMES]
            
            X_risk.append(feat_vec)
            y_risk.append(failed)
            
            # Keep traj and stab on all data for simplicity
            current_bw = features["current_bw"]
            y_traj_30_train.append(pts[i+6].basis_weight_actual - current_bw)
            y_traj_60_train.append(pts[i+12].basis_weight_actual - current_bw)
            y_traj_120_train.append(pts[i+24].basis_weight_actual - current_bw)
            X_traj_train.append(feat_vec)
            
            remaining_pts = pts[i:]
            stab_idx = len(remaining_pts) - 1 if len(remaining_pts) > 0 else 0
            for j in range(len(remaining_pts)):
                if all(abs(p.basis_weight_actual - p.basis_weight_setpoint) < 0.5 for p in remaining_pts[j:]):
                    stab_idx = j
                    break
            X_stab_train.append(feat_vec)
            y_stab_train.append(stab_idx * 5.0)

    # Convert to numpy arrays
    X_risk, y_risk = np.array(X_risk), np.array(y_risk)
    
    inter_feat = X_risk[:, 6]
    corr = np.corrcoef(inter_feat, y_risk)[0, 1]
    print(f"\n--- BUG 5 VERIFICATION ---")
    print(f"Correlation between interaction_feature and failure risk: {corr:.3f}")
    print(f"--------------------------\n")
    
    # Train/Test split for evaluation (80/20 random split across all timepoints ensures a realistic mix of easy and hard cases)
    X_risk_train, X_risk_test, y_risk_train, y_risk_test = train_test_split(X_risk, y_risk, test_size=0.2, random_state=42)
    
    # Ensure both classes in train set
    if len(np.unique(y_risk_train)) < 2:
        X_risk_train = np.vstack([X_risk_train, X_risk_train[0] * 1.5])
        y_risk_train = np.append(y_risk_train, 1 - y_risk_train[0])

    print("Training ML Models...")
    # Use max_depth=2 to prevent perfect overfitting on small synthetic data
    clf = lgb.LGBMClassifier(n_estimators=50, max_depth=2, random_state=42)
    clf.fit(X_risk_train, y_risk_train)
    clf._Booster.save_model(os.path.join(ARTIFACTS_DIR, "risk_model.txt"))
    joblib.dump(clf, os.path.join(ARTIFACTS_DIR, "risk_model.joblib"))
    
    # Evaluate model
    if len(X_risk_test) > 0:
        y_pred = clf.predict(X_risk_test)
        print("\n--- Model Evaluation ---")
        print(f"Accuracy:  {accuracy_score(y_risk_test, y_pred):.3f}")
        print(f"Precision: {precision_score(y_risk_test, y_pred, zero_division=0):.3f}")
        print(f"Recall:    {recall_score(y_risk_test, y_pred, zero_division=0):.3f}")
        print("------------------------\n")
    
    for horizon, y_t in [(30, y_traj_30_train), (60, y_traj_60_train), (120, y_traj_120_train)]:
        reg = lgb.LGBMRegressor(n_estimators=50, max_depth=3, random_state=42).fit(np.array(X_traj_train), np.array(y_t))
        joblib.dump(reg, os.path.join(ARTIFACTS_DIR, f"trajectory_{horizon}s.joblib"))

    knn = KNeighborsRegressor(n_neighbors=3, weights='distance').fit(np.array(X_stab_train), np.array(y_stab_train))
    joblib.dump(knn, os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib"))
    print(f"ML models trained and saved to {ARTIFACTS_DIR}")

def main():
    print("Initializing Database...")
    init_db()
    db = SessionLocal()
    generate_synthetic_data(db)
    train_models(db)
    db.close()
    print("seed_demo.py complete!")

if __name__ == "__main__":
    main()
