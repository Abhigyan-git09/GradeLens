import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.domain import GradeChangeEvent, TimeseriesPoint
from app.services.counterfactual_service import counterfactual_service
from app.services.data_intelligence_service import data_intelligence_service
from app.services.explanation_service import explanation_service
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service


def _high_risk_context(db):
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
        ranked.append(
            (
                risk_predictor_service.predict_risk(features)[
                    "probability"
                ],
                index,
            )
        )
    _, index = max(ranked)
    return event, points[index]


def test_data_overview_makes_provenance_and_leakage_visible():
    db = SessionLocal()
    overview = data_intelligence_service.overview(db)
    assert overview["provenance"]["synthetic"] is True
    assert overview["provenance"]["deterministic_seed"] == 42
    assert overview["provenance"]["event_count"] >= 103
    assert overview["provenance"]["point_count"] > 20_000
    assert overview["split"]["demo_events_excluded"] is True
    assert overview["split"]["future_window_leakage_prevented"] is True
    assert len(overview["trajectory_profiles"]) >= 40
    assert len(overview["feature_importance"]) == 16
    assert any(
        item["is_interaction"] for item in overview["relationships"]
    )
    db.close()


def test_upload_validation_is_real_and_non_persistent():
    columns = data_intelligence_service.REQUIRED_UPLOAD_COLUMNS
    valid_rows = [
        {
            column: (
                f"2025-01-01T00:00:{index:02d}"
                if column == "timestamp"
                else 1
            )
            for column in columns
        }
        for index in range(12)
    ]
    result = data_intelligence_service.validate_upload(
        "historian.csv", columns, valid_rows
    )
    assert result["valid"] is True
    assert result["coverage_pct"] == 100.0
    assert "No row was written" in result["sandbox_note"]

    incomplete = data_intelligence_service.validate_upload(
        "bad.csv",
        ["timestamp", "bw_actual", "bw_setpoint"],
        valid_rows,
    )
    assert incomplete["valid"] is False
    assert "stock_flow_actual" in incomplete["missing_columns"]


def test_coordinated_scenario_is_constrained_and_explained():
    db = SessionLocal()
    event, point = _high_risk_context(db)
    opportunities = counterfactual_service.rank_opportunities(
        event.event_id, point.timestamp, db
    )
    assert opportunities
    best = opportunities[0]
    result = counterfactual_service.simulate_scenario(
        event.event_id,
        point.timestamp,
        [
            {
                "parameter_name": best["parameter_name"],
                "proposed_value": best["proposed_value"],
            }
        ],
        db,
    )
    assert result is not None
    assert result["feasible"] is True
    assert result["risk_after"] <= result["risk_before"]
    assert len(result["evidence_tags"]) >= 4
    assert "Advisory sandbox" in result["guardrail"]

    invalid = counterfactual_service.simulate_scenario(
        event.event_id,
        point.timestamp,
        [
            {
                "parameter_name": "Stock Flow",
                "proposed_value": 10_000,
            }
        ],
        db,
    )
    assert invalid is not None
    assert invalid["feasible"] is False
    assert invalid["risk_after"] == invalid["risk_before"]
    db.close()


def test_explanation_uses_grounded_facts_without_an_api_key():
    db = SessionLocal()
    event, point = _high_risk_context(db)
    result = explanation_service.explain(
        event.event_id,
        point.timestamp,
        db,
        prefer_llm=False,
    )
    assert result is not None
    assert result["mode"] == "grounded-template"
    assert "Basis Weight" in result["headline"]
    assert len(result["operator_checks"]) == 3
    assert len(result["evidence"]) >= 3
    assert "never writes" in result["guardrail"]
    assert "Generate a constrained counterfactual" in result[
        "suggested_response"
    ]
    db.close()
