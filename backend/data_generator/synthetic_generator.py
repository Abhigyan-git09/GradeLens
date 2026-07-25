import os
import sys
import datetime
import random
import numpy as np

# Add backend dir to python path
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

def generate_synthetic_data():
    print("Initializing Database...")
    init_db()
    
    db = SessionLocal()
    
    # Check if data already exists
    if db.query(GradeChangeEvent).first():
        print("Data already exists. Skipping generation.")
        db.close()
        return

    print("Generating Recipe Constraints...")
    constraints = [
        RecipeConstraint(grade_id="G-100", parameter="basis_weight", min_val=61.5, max_val=66.5, optimal_val=64.0),
        RecipeConstraint(grade_id="G-100", parameter="stock_flow", min_val=800.0, max_val=900.0, optimal_val=850.0),
        RecipeConstraint(grade_id="G-100", parameter="moisture", min_val=6.0, max_val=8.0, optimal_val=7.0),
        RecipeConstraint(grade_id="G-200", parameter="basis_weight", min_val=78.0, max_val=82.0, optimal_val=80.0),
        RecipeConstraint(grade_id="G-200", parameter="stock_flow", min_val=950.0, max_val=1100.0, optimal_val=1020.0),
        RecipeConstraint(grade_id="G-200", parameter="moisture", min_val=5.5, max_val=7.5, optimal_val=6.5),
    ]
    db.add_all(constraints)
    
    print("Generating Grade Change Events...")
    base_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)
    
    events = [
        {
            "event_id": "EVT-001-SUCCESS",
            "source": "G-100", "target": "G-200",
            "bw_old": 64.0, "bw_new": 80.0,
            "outcome": "success",
            "start_time": base_time
        },
        {
            "event_id": "EVT-002-FAILURE",
            "source": "G-200", "target": "G-100",
            "bw_old": 80.0, "bw_new": 64.0,
            "outcome": "failure",
            "start_time": base_time + datetime.timedelta(hours=6)
        },
        {
            "event_id": "EVT-003-RECOVERABLE",
            "source": "G-100", "target": "G-200",
            "bw_old": 64.0, "bw_new": 80.0,
            "outcome": "in_progress", # Recoverable scenario
            "start_time": base_time + datetime.timedelta(hours=12)
        }
    ]

    for ev in events:
        event = GradeChangeEvent(
            event_id=ev["event_id"],
            machine_id="PM-1",
            source_grade=ev["source"],
            target_grade=ev["target"],
            recipe_id=f"REC-{ev['target']}",
            start_time=ev["start_time"],
            end_time=ev["start_time"] + datetime.timedelta(minutes=20) if ev["outcome"] != "in_progress" else None,
            bw_old_target=ev["bw_old"],
            bw_new_target=ev["bw_new"],
            transition_outcome=ev["outcome"]
        )
        db.add(event)
        
        # Generate Timeseries for 20 minutes (1 point per 5 seconds = 240 points)
        ts_points = []
        duration_pts = 240
        
        # Base physics simulation
        for i in range(duration_pts):
            t = ev["start_time"] + datetime.timedelta(seconds=i*5)
            progress = min(1.0, i / 120.0) # Ramp over 10 minutes
            
            # Smooth transition using sine wave
            smooth_prog = (1 - np.cos(progress * np.pi)) / 2
            
            bw_actual = ev["bw_old"] + (ev["bw_new"] - ev["bw_old"]) * smooth_prog + random.uniform(-0.5, 0.5)
            bw_sp = ev["bw_old"] + (ev["bw_new"] - ev["bw_old"]) * smooth_prog
            
            stock_flow = 850 + (1020 - 850) * smooth_prog + random.uniform(-5, 5)
            filler_flow = 130 + (150 - 130) * smooth_prog + random.uniform(-2, 2)
            steam_press = 4.2 + (5.0 - 4.2) * smooth_prog + random.uniform(-0.1, 0.1)
            
            # Inject Failure Mode
            if ev["outcome"] == "failure" and i > 100:
                bw_actual += (i - 100) * 0.1 # Drift off spec
                
            # Inject Recoverable Interaction (Filler Flow Ramp x Steam Pressure at 45s lag)
            if ev["outcome"] == "in_progress" and i > 60:
                # 45s lag is 9 points (9 * 5 = 45s)
                if i > 69:
                    steam_slope = ts_points[i-1].steam_pressure_actual - ts_points[i-9].steam_pressure_actual
                    filler_ramp = ts_points[i-1].filler_flow_actual - ts_points[i-9].filler_flow_actual
                    interaction_effect = (filler_ramp * steam_slope) * 0.5
                    bw_actual -= interaction_effect
            
            ts = TimeseriesPoint(
                event_id=ev["event_id"],
                timestamp=t,
                basis_weight_actual=bw_actual,
                basis_weight_setpoint=bw_sp,
                stock_flow_actual=stock_flow,
                stock_flow_setpoint=stock_flow,
                filler_flow_actual=filler_flow,
                filler_flow_setpoint=filler_flow,
                steam_pressure_actual=steam_press,
                steam_pressure_setpoint=steam_press,
                machine_speed_actual=640 + random.uniform(-2, 2),
                machine_speed_setpoint=640,
                moisture_actual=7.0 + random.uniform(-0.2, 0.2),
                moisture_setpoint=7.0,
                ash_actual=15.0 + random.uniform(-0.5, 0.5),
                ash_setpoint=15.0,
                active_alarm_count=1 if ev["outcome"] == "failure" and i > 150 else 0,
                scanner_quality_score=1.0 - (0.1 if random.random() < 0.05 else 0.0)
            )
            ts_points.append(ts)
            
        db.add_all(ts_points)
        
        # Add a Recommendation for the in-progress recoverable event
        if ev["outcome"] == "in_progress":
            rec = Recommendation(
                event_id=ev["event_id"],
                parameter_name="Stock Flow",
                current_value=847.0,
                recommended_value=812.0,
                recommended_ramp_rate=-5.8,
                risk_before=0.67,
                risk_after=0.23,
                stabilization_before=252.0, # 4.2 min
                stabilization_after=126.0,  # 2.1 min
                confidence=0.82,
                rationale="Adjust ramping to prevent overshoot due to Filler Flow and Steam Pressure interaction.",
                status="pending"
            )
            db.add(rec)
            db.commit() # Commit to get ID
            
            tags = [
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Risk Model", source="Model", detail=""),
                EvidenceTag(recommendation_id=rec.recommendation_id, tag="Process Correlation", source="Analytics", detail="Filler x Steam interaction detected")
            ]
            db.add_all(tags)

    db.commit()
    db.close()
    print("Synthetic data generation complete!")

if __name__ == "__main__":
    generate_synthetic_data()
