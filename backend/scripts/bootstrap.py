import os
import sys
import datetime
import random
import joblib
import argparse
import numpy as np
import lightgbm as lgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

# Add backend dir to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
from sqlalchemy import text
from app.config import settings

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts")

def clear_existing_data(db):
    print("Clearing existing data for idempotent run...")
    db.execute(text("DELETE FROM operator_feedback"))
    db.execute(text("DELETE FROM evidence_tags"))
    db.execute(text("DELETE FROM recommendations"))
    db.execute(text("DELETE FROM timeseries_points"))
    db.execute(text("DELETE FROM grade_change_events"))
    db.execute(text("DELETE FROM recipe_constraints"))
    db.commit()

def generate_synthetic_data(db, force_reset=False):
    existing_count = db.query(GradeChangeEvent).count()
    if existing_count > 0 and not force_reset:
        print("Database already seeded. Skipping data generation. Use --reset to clear and re-seed.")
        return

    if force_reset:
        clear_existing_data(db)

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
    base_time = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    
    events = [
        {"event_id": "EVT-001-SUCCESS", "source": "G-100", "target": "G-200", "bw_old": 64.0, "bw_new": 80.0, "outcome": "success", "start": base_time},
        {"event_id": "EVT-002-FAILURE", "source": "G-200", "target": "G-100", "bw_old": 80.0, "bw_new": 64.0, "outcome": "failure", "start": base_time + datetime.timedelta(hours=6)},
        {"event_id": "EVT-003-RECOVERABLE", "source": "G-100", "target": "G-200", "bw_old": 64.0, "bw_new": 80.0, "outcome": "in_progress", "start": base_time + datetime.timedelta(hours=12)}
    ]
    
    # Generate 100 more events for training
    for i in range(100):
        is_success = random.random() > 0.3
        target = "G-200" if random.random() > 0.5 else "G-100"
        source = "G-100" if target == "G-200" else "G-200"
        bw_old = 64.0 if source == "G-100" else 80.0
        bw_new = 80.0 if target == "G-200" else 64.0
        events.append({
            "event_id": f"EVT-TRAIN-{1000+i}",
            "source": source,
            "target": target,
            "bw_old": bw_old,
            "bw_new": bw_new,
            "outcome": "success" if is_success else "failure",
            "start": base_time + datetime.timedelta(hours=24 + i*6)
        })

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
                # Stock-flow ramp
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
        if ev["event_id"] == "EVT-001-SUCCESS":
            db.commit()
            rec = Recommendation(
                recommendation_id="REC-001-HIST",
                event_id=ev["event_id"], parameter_name="Stock Flow", current_value=900.0, recommended_value=920.0,
                recommended_ramp_rate=2.0, risk_before=0.55, risk_after=0.15, stabilization_before=180.0, stabilization_after=120.0,
                confidence=0.90, rationale="Proactive stock flow adjustment based on historical success.", status="accepted",
                timestamp=ev["start"] + datetime.timedelta(minutes=4)
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
        if ev["event_id"] == "EVT-003-RECOVERABLE":
            db.commit()
            rec = Recommendation(
                recommendation_id="REC-003-DEMO",
                event_id=ev["event_id"], parameter_name="Stock Flow", current_value=847.0, recommended_value=812.0,
                recommended_ramp_rate=-5.8, risk_before=0.67, risk_after=0.23, stabilization_before=252.0, stabilization_after=126.0,
                confidence=0.82, rationale="Adjust ramping to prevent overshoot due to Filler Flow and Steam Pressure interaction.", status="pending",
                timestamp=ev["start"] + datetime.timedelta(minutes=6)
            )
            db.add(rec)
            db.commit()
            db.add_all([
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Risk Model", source="Model", detail="82% probability of overshoot"),
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Process Correlation", source="Analytics", detail="Filler x Steam interaction detected")
            ])
            db.commit()

    db.commit()
    print("Synthetic data generated.")

def train_models(db):
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    
    # We will overwrite artifacts since training is deterministic or if forced
    events = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id.like('EVT-TRAIN-%')).all()
    if not events:
        print("No training events found.")
        return
        
    X_risk, y_risk = [], []
    X_traj_train, y_traj_30_train, y_traj_60_train, y_traj_120_train = [], [], [], []
    X_stab_train, y_stab_train = [], []
    
    event_ids = [e.event_id for e in events] # Should be exactly 100 events
    
    # Split by event_id: 70 train, 15 val, 15 test
    # 30% for temp -> 15% val, 15% test
    train_event_ids, temp_event_ids = train_test_split(event_ids, test_size=0.30, random_state=42)
    val_event_ids, test_event_ids = train_test_split(temp_event_ids, test_size=0.50, random_state=42)
    
    for event in events:
        is_train = event.event_id in train_event_ids
        is_val = event.event_id in val_event_ids
        
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event.event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
        
        event_X_risk, event_y_risk = [], []
        for i in range(12, len(pts) - 24):
            window = pts[i-12:i]
            features = feature_service.extract_features(window)
            
            future_window = pts[i:i+24]
            max_dev_percent = max(abs(pt.basis_weight_actual - pt.basis_weight_setpoint) / pt.basis_weight_setpoint * 100 for pt in future_window)
            failed = 1 if max_dev_percent > (settings.SPEC_DEVIATION_PCT * 100) else 0
            
            feat_vec = [features.get(f, 0.0) for f in FEATURE_NAMES]
            
            event_X_risk.append(feat_vec)
            event_y_risk.append(failed)
            
            if is_train:
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

        if is_train:
            X_risk.extend(event_X_risk)
            y_risk.extend(event_y_risk)
        elif is_val:
            # We don't train on validation/test events directly
            pass

    # Extract test set explicitly
    X_risk_test, y_risk_test = [], []
    for event_id in test_event_ids:
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
        for i in range(12, len(pts) - 24):
            window = pts[i-12:i]
            features = feature_service.extract_features(window)
            future_window = pts[i:i+24]
            max_dev_percent = max(abs(pt.basis_weight_actual - pt.basis_weight_setpoint) / pt.basis_weight_setpoint * 100 for pt in future_window)
            failed = 1 if max_dev_percent > (settings.SPEC_DEVIATION_PCT * 100) else 0
            feat_vec = [features.get(f, 0.0) for f in FEATURE_NAMES]
            X_risk_test.append(feat_vec)
            y_risk_test.append(failed)

    X_risk, y_risk = np.array(X_risk), np.array(y_risk)
    X_risk_test, y_risk_test = np.array(X_risk_test), np.array(y_risk_test)

    # Ensure both classes in train set
    if len(np.unique(y_risk)) < 2:
        X_risk = np.vstack([X_risk, X_risk[0] * 1.5])
        y_risk = np.append(y_risk, 1 - y_risk[0])

    print("Training ML Models...")
    clf = lgb.LGBMClassifier(n_estimators=50, max_depth=2, random_state=42)
    clf.fit(X_risk, y_risk)
    clf._Booster.save_model(os.path.join(ARTIFACTS_DIR, "risk_model.txt"))
    joblib.dump(clf, os.path.join(ARTIFACTS_DIR, "risk_model.joblib"))
    
    # Evaluate model on test set
    if len(X_risk_test) > 0:
        y_pred = clf.predict(X_risk_test)
    print("\n--- Synthetic Test-Set Results ---")
    print(f"Total events generated: {len(events)}")
    print(f"Training events: {len(train_event_ids)}")
    print(f"Validation events: {len(val_event_ids)}")
    print(f"Testing events: {len(test_event_ids)}")
    print("Demo/Curated events (excluded from training): 3")
    print(f"Accuracy:  {accuracy_score(y_risk_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_risk_test, y_pred, zero_division=0):.3f}")
    print(f"Recall:    {recall_score(y_risk_test, y_pred, zero_division=0):.3f}")
    print("----------------------------------\n")
    
    for horizon, y_t in [(30, y_traj_30_train), (60, y_traj_60_train), (120, y_traj_120_train)]:
        reg = lgb.LGBMRegressor(n_estimators=50, max_depth=3, random_state=42).fit(np.array(X_traj_train), np.array(y_t))
        joblib.dump(reg, os.path.join(ARTIFACTS_DIR, f"trajectory_{horizon}s.joblib"))

    knn = KNeighborsRegressor(n_neighbors=3, weights='distance').fit(np.array(X_stab_train), np.array(y_stab_train))
    joblib.dump(knn, os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib"))
    print(f"ML models trained and saved to {ARTIFACTS_DIR}")

def main():
    parser = argparse.ArgumentParser(description="Bootstrap GradeLens Database and ML Models")
    parser.add_argument("--reset", action="store_true", help="Force clear existing data and re-seed.")
    parser.add_argument("--retrain", action="store_true", help="Force retrain models even if data exists.")
    args = parser.parse_args()

    print("Initializing Database...")
    init_db()
    db = SessionLocal()
    
    generate_synthetic_data(db, force_reset=args.reset)
    
    # Always train models if we reset, retrained, or if artifacts are missing
    artifacts_exist = (
        os.path.exists(os.path.join(ARTIFACTS_DIR, "risk_model.txt")) and
        os.path.exists(os.path.join(ARTIFACTS_DIR, "trajectory_30s.joblib")) and
        os.path.exists(os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib"))
    )
    
    if args.reset or args.retrain or not artifacts_exist:
        train_models(db)
    else:
        print("Models already trained. Use --retrain or --reset to re-run training.")
        
    db.close()
    print("bootstrap.py complete!")

if __name__ == "__main__":
    main()
