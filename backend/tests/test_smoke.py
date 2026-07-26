import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models.domain import GradeChangeEvent, TimeseriesPoint
from app.services.correlation_service import correlation_service
from app.services.counterfactual_service import counterfactual_service
from app.services.rootcause_service import rootcause_service
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service
from ml.trajectory_forecast import trajectory_forecaster_service


def _recoverable_context(db):
    event = (
        db.query(GradeChangeEvent)
        .filter_by(event_id="EVT-003-RECOVERABLE")
        .one()
    )
    points = (
        db.query(TimeseriesPoint)
        .filter_by(event_id=event.event_id)
        .order_by(TimeseriesPoint.timestamp)
        .all()
    )
    ranked = []
    for index in range(11, len(points)):
        features = feature_service.extract_features(
            points[index - 11 : index + 1]
        )
        risk = risk_predictor_service.predict_risk(features)["probability"]
        ranked.append((risk, index, features))
    _, index, features = max(
        ranked, key=lambda item: (item[0], item[1])
    )
    return event, points, index, features


def test_early_warning_before_spec_violation():
    db = SessionLocal()
    _, _, _, features = _recoverable_context(db)
    result = risk_predictor_service.predict_risk(features)
    assert result["probability"] >= 0.75
    assert abs(features["bw_deviation_pct"]) < 2.5
    assert result["decision_threshold"] == (
        risk_predictor_service.decision_threshold
    )
    assert result["spec_deviation_pct"] == 2.5
    db.close()


def test_trajectory_tracks_moving_grade_setpoint():
    db = SessionLocal()
    _, _, _, features = _recoverable_context(db)
    trajectory = trajectory_forecaster_service.forecast(features)
    assert len(trajectory["horizons"]) == 3
    assert all("predicted_setpoint" in item for item in trajectory["horizons"])
    assert trajectory["model_mode"] == "trained"
    db.close()


def test_constrained_counterfactual_materially_improves_risk():
    db = SessionLocal()
    event, points, index, _ = _recoverable_context(db)
    latest = points[index]
    simulations = []
    for parameter, value in counterfactual_service.candidate_values(
        event, latest, db
    ):
        result = counterfactual_service.simulate(
            event.event_id, latest.timestamp, parameter, value, db
        )
        if result and result["feasible"]:
            simulations.append(result)
    assert len(simulations) >= 8
    exposure_reducing = [
        item for item in simulations if item["avoided_off_spec_seconds"] > 0
    ]
    assert exposure_reducing
    best = min(exposure_reducing, key=lambda item: item["risk_after"])
    assert best["risk_after"] <= best["risk_before"] - 0.10
    assert best["stabilization_after"] < best["stabilization_before"]
    assert best["avoided_off_spec_seconds"] > 0
    assert len(best["evidence_tags"]) >= 4
    db.close()


def test_timestamp_safe_interaction_discovery():
    db = SessionLocal()
    event, points, _, _ = _recoverable_context(db)
    early = correlation_service.discover_relationships(
        event.event_id, db, timestamp=points[20].timestamp
    )
    complete = correlation_service.discover_relationships(
        event.event_id, db, timestamp=points[-1].timestamp
    )
    assert early == []
    assert any(item.is_interaction for item in complete)
    db.close()


def test_local_root_cause_explanation():
    db = SessionLocal()
    event, points, index, features = _recoverable_context(db)
    causes = rootcause_service.get_root_causes(
        event.event_id, db, features=features
    )
    assert causes
    assert 0.95 <= sum(item.contribution_pct for item in causes) <= 1.05
    assert all("local SHAP" in item.rationale for item in causes)
    db.close()


if __name__ == "__main__":
    init_db()
    test_early_warning_before_spec_violation()
    test_trajectory_tracks_moving_grade_setpoint()
    test_constrained_counterfactual_materially_improves_risk()
    test_timestamp_safe_interaction_discovery()
    test_local_root_cause_explanation()
    print("All GradeLens smoke checks passed.")
