import os
import sys
import datetime
import random
import joblib
import argparse
import json
import numpy as np
import lightgbm as lgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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
RANDOM_SEED = 42

def clear_existing_data(db):
    print("Clearing existing data for idempotent run...")
    db.execute(text("DELETE FROM discovered_relationships"))
    db.execute(text("DELETE FROM operator_feedback"))
    db.execute(text("DELETE FROM evidence_tags"))
    db.execute(text("DELETE FROM recommendations"))
    db.execute(text("DELETE FROM timeseries_points"))
    db.execute(text("DELETE FROM grade_change_events"))
    db.execute(text("DELETE FROM recipe_constraints"))
    db.commit()

def generate_synthetic_data(db, force_reset=False):
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    existing_count = db.query(GradeChangeEvent).count()
    if existing_count > 0 and not force_reset:
        print("Database already seeded. Skipping data generation. Use --reset to clear and re-seed.")
        return

    if force_reset:
        clear_existing_data(db)

    print("Generating Recipe Constraints...")
    constraints = [
        RecipeConstraint(grade_id="G-100", parameter="basis_weight", min_val=61.5, max_val=66.5, optimal_val=64.0, max_ramp_rate=0.20),
        RecipeConstraint(grade_id="G-100", parameter="stock_flow", min_val=790.0, max_val=910.0, optimal_val=850.0, max_ramp_rate=6.0),
        RecipeConstraint(grade_id="G-100", parameter="machine_speed", min_val=600.0, max_val=680.0, optimal_val=640.0, max_ramp_rate=3.0),
        RecipeConstraint(grade_id="G-100", parameter="filler_flow", min_val=115.0, max_val=145.0, optimal_val=130.0, max_ramp_rate=1.5),
        RecipeConstraint(grade_id="G-100", parameter="steam_pressure", min_val=3.8, max_val=4.6, optimal_val=4.2, max_ramp_rate=0.04),
        RecipeConstraint(grade_id="G-100", parameter="moisture", min_val=6.0, max_val=8.0, optimal_val=7.0, max_ramp_rate=0.08),
        RecipeConstraint(grade_id="G-100", parameter="ash", min_val=13.0, max_val=17.0, optimal_val=15.0, max_ramp_rate=0.10),
        RecipeConstraint(grade_id="G-100", parameter="caliper", min_val=88.0, max_val=96.0, optimal_val=92.0, max_ramp_rate=0.30),
        RecipeConstraint(grade_id="G-200", parameter="basis_weight", min_val=78.0, max_val=82.0, optimal_val=80.0, max_ramp_rate=0.20),
        RecipeConstraint(grade_id="G-200", parameter="stock_flow", min_val=940.0, max_val=1100.0, optimal_val=1020.0, max_ramp_rate=6.0),
        RecipeConstraint(grade_id="G-200", parameter="machine_speed", min_val=540.0, max_val=620.0, optimal_val=580.0, max_ramp_rate=3.0),
        RecipeConstraint(grade_id="G-200", parameter="filler_flow", min_val=135.0, max_val=165.0, optimal_val=150.0, max_ramp_rate=1.5),
        RecipeConstraint(grade_id="G-200", parameter="steam_pressure", min_val=4.6, max_val=5.4, optimal_val=5.0, max_ramp_rate=0.04),
        RecipeConstraint(grade_id="G-200", parameter="moisture", min_val=5.5, max_val=7.5, optimal_val=6.5, max_ramp_rate=0.08),
        RecipeConstraint(grade_id="G-200", parameter="ash", min_val=16.0, max_val=20.0, optimal_val=18.0, max_ramp_rate=0.10),
        RecipeConstraint(grade_id="G-200", parameter="caliper", min_val=102.0, max_val=112.0, optimal_val=107.0, max_ramp_rate=0.30),
    ]
    db.add_all(constraints)
    
    print("Generating Grade Change Events...")
    base_time = (
        datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        - datetime.timedelta(days=30)
    )
    profiles = {
        "G-100": {
            "stock": 850.0, "filler": 130.0, "steam": 4.2,
            "speed": 640.0, "moisture": 7.0, "ash": 15.0,
            "caliper": 92.0,
        },
        "G-200": {
            "stock": 1020.0, "filler": 150.0, "steam": 5.0,
            "speed": 580.0, "moisture": 6.5, "ash": 18.0,
            "caliper": 107.0,
        },
    }
    
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
        
        source_profile = profiles[ev["source"]]
        target_profile = profiles[ev["target"]]
        failure_mode = sum(ord(char) for char in ev["event_id"]) % 3
        ts_points = []
        for i in range(240): # 20 minutes at 5s res
            t = ev["start"] + datetime.timedelta(seconds=i*5)
            progress = min(1.0, i / 120.0)
            smooth_prog = (1 - np.cos(progress * np.pi)) / 2
            
            bw_sp = ev["bw_old"] + (ev["bw_new"] - ev["bw_old"]) * smooth_prog
            process_setpoints = {
                name: source_profile[name]
                + (target_profile[name] - source_profile[name]) * smooth_prog
                for name in source_profile
            }
            stock_flow = process_setpoints["stock"] + random.uniform(-3.0, 3.0)
            filler_flow = process_setpoints["filler"] + random.uniform(-0.4, 0.4)
            steam_press = process_setpoints["steam"] + random.uniform(-0.025, 0.025)
            machine_speed = process_setpoints["speed"] + random.uniform(-1.5, 1.5)
            moisture = process_setpoints["moisture"] + random.uniform(-0.12, 0.12)
            ash = process_setpoints["ash"] + random.uniform(-0.25, 0.25)
            caliper = process_setpoints["caliper"] + random.uniform(-0.4, 0.4)

            # Normal transport lag during the grade ramp.
            transition_lag = (
                np.sin(progress * np.pi)
                * (0.35 if ev["bw_new"] > ev["bw_old"] else -0.35)
            )
            bw_actual = bw_sp + transition_lag + random.uniform(-0.28, 0.28)

            # Failures arise from multiple actionable mechanisms rather than
            # from the outcome label itself.
            if ev["outcome"] == "failure" and i > 72:
                severity = min(1.0, (i - 72) / 55.0)
                if failure_mode == 0:
                    disturbance = 75.0 * severity
                    stock_flow += disturbance
                    bw_actual += disturbance * 0.045
                elif failure_mode == 1:
                    disturbance = 42.0 * severity
                    machine_speed -= disturbance
                    bw_actual += disturbance * 0.075
                else:
                    filler_disturbance = 9.0 * severity
                    steam_disturbance = 0.55 * severity
                    filler_flow += filler_disturbance
                    steam_press += steam_disturbance
                    bw_actual += filler_disturbance * steam_disturbance * 0.72

            # Curated recoverable event: a time-limited filler/steam coupling
            # creates an early warning window, then naturally decays.
            if ev["outcome"] == "in_progress" and 62 < i < 132:
                envelope = max(0.0, 1.0 - abs(i - 96) / 36.0)
                filler_disturbance = 8.0 * envelope
                steam_disturbance = 0.48 * envelope
                filler_flow += filler_disturbance
                steam_press += steam_disturbance
                bw_actual += filler_disturbance * steam_disturbance * 0.78
            
            ts_points.append(TimeseriesPoint(
                event_id=ev["event_id"], timestamp=t, basis_weight_actual=bw_actual, basis_weight_setpoint=bw_sp,
                stock_flow_actual=stock_flow, stock_flow_setpoint=process_setpoints["stock"],
                filler_flow_actual=filler_flow, filler_flow_setpoint=process_setpoints["filler"],
                steam_pressure_actual=steam_press, steam_pressure_setpoint=process_setpoints["steam"],
                machine_speed_actual=machine_speed, machine_speed_setpoint=process_setpoints["speed"],
                moisture_actual=moisture, moisture_setpoint=process_setpoints["moisture"],
                ash_actual=ash, ash_setpoint=process_setpoints["ash"],
                caliper_actual=caliper, caliper_setpoint=process_setpoints["caliper"],
                active_alarm_count=1 if ev["outcome"] == "failure" and i > 105 else 0,
                scanner_quality_score=0.82 if ev["outcome"] == "failure" and i > 135 else 0.98 - (0.08 if random.random() < 0.03 else 0.0)
            ))
        db.add_all(ts_points)
        deviations = [
            abs(point.basis_weight_actual - point.basis_weight_setpoint)
            / point.basis_weight_setpoint
            * 100.0
            for point in ts_points
        ]
        event.max_deviation_pct = max(deviations)
        event.off_spec_seconds = sum(
            deviation > settings.SPEC_DEVIATION_PCT
            for deviation in deviations
        ) * 5.0
        stable_index = len(ts_points) - 1
        for index in range(len(ts_points)):
            if all(deviation <= 0.75 for deviation in deviations[index:]):
                stable_index = index
                break
        event.stabilization_seconds = stable_index * 5.0
        
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
                event_id=ev["event_id"], parameter_name="Stock Flow", current_value=1000.0, recommended_value=960.0,
                recommended_ramp_rate=-2.67, risk_before=0.82, risk_after=0.28, stabilization_before=252.0, stabilization_after=126.0,
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
            failed = 1 if max_dev_percent > settings.SPEC_DEVIATION_PCT else 0
            
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
    X_traj_test = []
    y_traj_test = {30: [], 60: [], 120: []}
    X_stab_test, y_stab_test = [], []
    for event_id in test_event_ids:
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
        for i in range(12, len(pts) - 24):
            window = pts[i-12:i]
            features = feature_service.extract_features(window)
            future_window = pts[i:i+24]
            max_dev_percent = max(abs(pt.basis_weight_actual - pt.basis_weight_setpoint) / pt.basis_weight_setpoint * 100 for pt in future_window)
            failed = 1 if max_dev_percent > settings.SPEC_DEVIATION_PCT else 0
            feat_vec = [features.get(f, 0.0) for f in FEATURE_NAMES]
            X_risk_test.append(feat_vec)
            y_risk_test.append(failed)
            current_bw = features["current_bw"]
            X_traj_test.append(feat_vec)
            y_traj_test[30].append(pts[i+6].basis_weight_actual - current_bw)
            y_traj_test[60].append(pts[i+12].basis_weight_actual - current_bw)
            y_traj_test[120].append(pts[i+24].basis_weight_actual - current_bw)
            remaining_pts = pts[i:]
            stab_idx = len(remaining_pts) - 1
            for j in range(len(remaining_pts)):
                if all(
                    abs(p.basis_weight_actual - p.basis_weight_setpoint) < 0.5
                    for p in remaining_pts[j:]
                ):
                    stab_idx = j
                    break
            X_stab_test.append(feat_vec)
            y_stab_test.append(stab_idx * 5.0)

    X_risk, y_risk = np.array(X_risk), np.array(y_risk)
    X_risk_test, y_risk_test = np.array(X_risk_test), np.array(y_risk_test)

    # Ensure both classes in train set
    if len(np.unique(y_risk)) < 2:
        X_risk = np.vstack([X_risk, X_risk[0] * 1.5])
        y_risk = np.append(y_risk, 1 - y_risk[0])

    print("Training ML Models...")
    clf = lgb.LGBMClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.06,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        verbosity=-1,
    )
    clf.fit(X_risk, y_risk)
    clf._Booster.save_model(os.path.join(ARTIFACTS_DIR, "risk_model.txt"))
    joblib.dump(clf, os.path.join(ARTIFACTS_DIR, "risk_model.joblib"))
    
    # Evaluate model on test set
    y_pred = clf.predict(X_risk_test)
    y_probability = clf.predict_proba(X_risk_test)[:, 1]
    total_event_count = db.query(GradeChangeEvent).count()
    metrics = {
        "dataset": {
            "events_total": total_event_count,
            "training_pool_events": len(events),
            "curated_demo_events": total_event_count - len(events),
            "events_train": len(train_event_ids),
            "events_validation": len(val_event_ids),
            "events_test": len(test_event_ids),
            "test_windows": int(len(y_risk_test)),
            "positive_test_windows": int(np.sum(y_risk_test)),
            "spec_deviation_pct": settings.SPEC_DEVIATION_PCT,
            "feature_count": len(FEATURE_NAMES),
        },
        "risk": {
            "accuracy": float(accuracy_score(y_risk_test, y_pred)),
            "precision": float(precision_score(y_risk_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_risk_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_risk_test, y_probability)),
            "pr_auc": float(average_precision_score(y_risk_test, y_probability)),
            "brier_score": float(brier_score_loss(y_risk_test, y_probability)),
        },
        "trajectory_mae_gsm": {},
    }
    print("\n--- Synthetic Test-Set Results ---")
    print(f"Total events generated: {total_event_count}")
    print(f"Training events: {len(train_event_ids)}")
    print(f"Validation events: {len(val_event_ids)}")
    print(f"Testing events: {len(test_event_ids)}")
    print("Demo/Curated events (excluded from training): 3")
    print(f"Accuracy:  {metrics['risk']['accuracy']:.3f}")
    print(f"Precision: {metrics['risk']['precision']:.3f}")
    print(f"Recall:    {metrics['risk']['recall']:.3f}")
    print(f"ROC-AUC:   {metrics['risk']['roc_auc']:.3f}")
    print("----------------------------------\n")
    
    for horizon, y_t in [(30, y_traj_30_train), (60, y_traj_60_train), (120, y_traj_120_train)]:
        reg = lgb.LGBMRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.06,
            random_state=RANDOM_SEED,
            verbosity=-1,
        ).fit(np.array(X_traj_train), np.array(y_t))
        joblib.dump(reg, os.path.join(ARTIFACTS_DIR, f"trajectory_{horizon}s.joblib"))
        metrics["trajectory_mae_gsm"][str(horizon)] = float(
            mean_absolute_error(
                y_traj_test[horizon],
                reg.predict(np.asarray(X_traj_test)),
            )
        )

    neighbor_model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("knn", KNeighborsRegressor(n_neighbors=5, weights="distance")),
        ]
    ).fit(np.array(X_stab_train), np.array(y_stab_train))
    stabilization_model = lgb.LGBMRegressor(
        n_estimators=140,
        max_depth=4,
        learning_rate=0.05,
        random_state=RANDOM_SEED,
        verbosity=-1,
    ).fit(np.array(X_stab_train), np.array(y_stab_train))
    joblib.dump(
        {
            "regressor": stabilization_model,
            "neighbors": neighbor_model,
            "neighbor_count": 5,
        },
        os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib"),
    )
    stabilization_prediction = (
        0.8 * stabilization_model.predict(np.asarray(X_stab_test))
        + 0.2 * neighbor_model.predict(np.asarray(X_stab_test))
    )
    metrics["stabilization_mae_seconds"] = float(
        mean_absolute_error(
            y_stab_test,
            stabilization_prediction,
        )
    )
    with open(
        os.path.join(ARTIFACTS_DIR, "metrics.json"),
        "w",
        encoding="utf-8",
    ) as metrics_file:
        json.dump(metrics, metrics_file, indent=2)
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
        os.path.exists(os.path.join(ARTIFACTS_DIR, "risk_model.joblib")) and
        all(
            os.path.exists(os.path.join(ARTIFACTS_DIR, f"trajectory_{h}s.joblib"))
            for h in settings.PREDICTION_HORIZONS
        ) and
        os.path.exists(os.path.join(ARTIFACTS_DIR, "stabilization_knn.joblib")) and
        os.path.exists(os.path.join(ARTIFACTS_DIR, "metrics.json"))
    )
    
    if args.reset or args.retrain or not artifacts_exist:
        train_models(db)
    else:
        print("Models already trained. Use --retrain or --reset to re-run training.")
        
    db.close()
    print("bootstrap.py complete!")

if __name__ == "__main__":
    main()
