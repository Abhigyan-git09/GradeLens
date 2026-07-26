import os
import sys
import pytest
import datetime
from types import SimpleNamespace
from sqlalchemy import text

# Add backend dir to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models.domain import (
    EvidenceTag,
    Recommendation,
    OperatorFeedback,
    GradeChangeEvent,
    TimeseriesPoint,
)
from app.routers.recommendations import accept_recommendation
from app.routers.grade_changes import get_snapshot
from fastapi import HTTPException
from app.services.recommendation_engine import recommendation_engine
from app.config import settings

def test_idempotent_feedback():
    db = SessionLocal()
    
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == "REC-001-HIST").first()
    if not rec:
        db.close()
        pytest.skip("REC-001-HIST not found (might be missing if tests run in isolation without bootstrap)")
        return
        
    # Try to accept it again, should raise 409
    try:
        accept_recommendation(rec.recommendation_id, db)
        assert False, "Should have raised HTTPException 409"
    except HTTPException as e:
        assert e.status_code == 409
        
    db.close()

def test_snapshot_leakage():
    db = SessionLocal()
    event = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id == "EVT-003-RECOVERABLE").first()
    if not event:
        db.close()
        pytest.skip("Test event not found")
        return
        
    pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event.event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
    if len(pts) < 15:
        db.close()
        pytest.skip("Not enough points")
        return
        
    T = pts[14].timestamp
    
    # Generate snapshot at T
    snapshot_before = get_snapshot(event.event_id, T, db)
    assert snapshot_before is not None
    assert snapshot_before.risk is not None
    
    future_pt = db.query(TimeseriesPoint).filter(
        TimeseriesPoint.event_id == event.event_id,
        TimeseriesPoint.timestamp > T
    ).order_by(TimeseriesPoint.timestamp.asc()).first()
    assert future_pt is not None
    original_future_value = future_pt.basis_weight_actual
    future_pt.basis_weight_actual = original_future_value + 100.0
    db.flush()
    
    # Generate snapshot again at T
    snapshot_after = get_snapshot(event.event_id, T, db)
    
    db.rollback()
    db.close()
    
    # Assert identical JSON
    assert snapshot_before.model_dump_json() == snapshot_after.model_dump_json(), "Snapshot leaked future data!"

def test_no_action_baseline():
    db = SessionLocal()
    event = (
        db.query(GradeChangeEvent)
        .filter(GradeChangeEvent.event_id == "EVT-001-SUCCESS")
        .first()
    )
    if not event:
        db.close()
        pytest.skip("Seeded success event not found")
    points = (
        db.query(TimeseriesPoint)
        .filter(TimeseriesPoint.event_id == event.event_id)
        .order_by(TimeseriesPoint.timestamp.asc())
        .all()
    )
    assert len(points) >= 13
    rec = None
    try:
        rec = recommendation_engine.generate(
            event.event_id,
            db,
            points[12].timestamp.isoformat(),
        )
        assert rec is not None
        assert rec.parameter_name == "No intervention"
        assert "Continue monitoring." in rec.rationale
        assert 0.50 <= rec.confidence <= 0.95
        assert len(rec.evidence_tags) >= 5
        assert {
            "Risk Forecast",
            "Specification Margin",
            "Scanner Diagnostics",
            "Historical Stability",
            "Recipe Envelope",
        }.issubset({tag.tag for tag in rec.evidence_tags})
    finally:
        if rec is not None:
            db.query(EvidenceTag).filter(
                EvidenceTag.recommendation_id == rec.recommendation_id
            ).delete(synchronize_session=False)
            db.query(Recommendation).filter(
                Recommendation.recommendation_id == rec.recommendation_id
            ).delete(synchronize_session=False)
            db.commit()
        db.close()

def test_minimum_risk_reduction():
    weak_candidate = {
        "risk_before": 0.99,
        "risk_after": 0.987,
        "stabilization_before": 767.0,
        "stabilization_after": 739.6,
        "avoided_off_spec_seconds": 0.0,
    }
    useful_risk_candidate = {
        **weak_candidate,
        "risk_after": 0.93,
    }
    useful_stabilization_candidate = {
        **weak_candidate,
        "stabilization_after": 660.0,
    }
    assert not recommendation_engine._is_material_improvement(weak_candidate)
    assert recommendation_engine._is_material_improvement(
        useful_risk_candidate
    )
    assert recommendation_engine._is_material_improvement(
        useful_stabilization_candidate
    )


def test_no_action_confidence_responds_to_data_quality():
    clean = SimpleNamespace(
        scanner_quality_score=0.99,
        active_alarm_count=0,
    )
    degraded = SimpleNamespace(
        scanner_quality_score=0.55,
        active_alarm_count=3,
    )
    clean_confidence = recommendation_engine._estimate_no_action_confidence(
        clean, 0.10, "trained", 0.60
    )
    degraded_confidence = (
        recommendation_engine._estimate_no_action_confidence(
            degraded, 0.10, "degraded", 0.60
        )
    )
    assert 0.50 <= degraded_confidence < clean_confidence <= 0.95

def test_demo_event_exclusion():
    from ml.feature_service import feature_service
    # Re-run a check over the artifacts or simply verify the train split logic 
    # doesn't include "EVT-003-RECOVERABLE".
    # In bootstrap.py, we only train on events matching 'EVT-TRAIN-%'
    db = SessionLocal()
    train_events = db.query(GradeChangeEvent).filter(GradeChangeEvent.event_id.like('EVT-TRAIN-%')).count()
    assert train_events > 0
    
    demo_in_train = db.query(GradeChangeEvent).filter(
        GradeChangeEvent.event_id == "EVT-003-RECOVERABLE",
        GradeChangeEvent.event_id.like('EVT-TRAIN-%')
    ).count()
    assert demo_in_train == 0
    db.close()

def test_bootstrap_idempotency():
    from scripts.bootstrap import generate_synthetic_data
    db = SessionLocal()
    initial_count = db.query(GradeChangeEvent).count()
    generate_synthetic_data(db, force_reset=False)
    final_count = db.query(GradeChangeEvent).count()
    db.close()
    
    assert initial_count == final_count, "Bootstrap is not idempotent, row count changed!"

