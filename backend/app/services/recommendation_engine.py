"""Constraint-aware recommendation search backed by counterfactual simulation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from dateutil.parser import isoparse
from sqlalchemy.orm import Session

from app.config import settings
from app.models.domain import (
    EvidenceTag,
    GradeChangeEvent,
    Recommendation,
    TimeseriesPoint,
)
from app.services.counterfactual_service import counterfactual_service
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service


class RecommendationEngine:
    def generate(
        self,
        event_id: str,
        db: Session,
        timestamp: str | None = None,
    ) -> Optional[Recommendation]:
        event = (
            db.query(GradeChangeEvent)
            .filter(GradeChangeEvent.event_id == event_id)
            .first()
        )
        if not event:
            return None

        query = db.query(TimeseriesPoint).filter(
            TimeseriesPoint.event_id == event_id
        )
        decision_time = datetime.now(UTC).replace(tzinfo=None)
        if timestamp:
            try:
                decision_time = isoparse(timestamp).replace(tzinfo=None)
                query = query.filter(TimeseriesPoint.timestamp <= decision_time)
            except (TypeError, ValueError):
                return None
        points = (
            query.order_by(TimeseriesPoint.timestamp.desc()).limit(12).all()
        )
        if len(points) < 12:
            return None
        window = list(reversed(points))
        latest = window[-1]
        features = feature_service.extract_features(window)
        current_risk = risk_predictor_service.predict_risk(features)[
            "probability"
        ]
        current_stabilization = stabilization_service.estimate_stabilization(
            features
        )["estimated_seconds"]

        if current_risk < settings.RISK_THRESHOLD:
            return self._create_no_action_recommendation(
                event_id,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "Current forecast remains within the operating envelope.",
            )

        scored = []
        for parameter, value in counterfactual_service.candidate_values(
            event, latest, db
        ):
            simulation = counterfactual_service.simulate(
                event_id, decision_time, parameter, value, db
            )
            if not simulation or not simulation["feasible"]:
                continue
            change_fraction = abs(
                simulation["proposed_value"] - simulation["current_value"]
            ) / max(abs(simulation["current_value"]), 1e-6)
            score = (
                settings.REC_WEIGHT_RISK * simulation["risk_after"]
                + settings.REC_WEIGHT_STABILIZATION
                * simulation["stabilization_after"]
                / 600.0
                + settings.REC_WEIGHT_CHANGE * change_fraction
            )
            benefit = (
                simulation["risk_before"] - simulation["risk_after"]
                + simulation["avoided_off_spec_seconds"] / 120.0
            )
            scored.append((score, -benefit, simulation))

        if not scored:
            return self._create_no_action_recommendation(
                event_id,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "No candidate satisfies the active recipe and actuator limits.",
            )

        scored.sort(key=lambda item: (item[0], item[1]))
        best = scored[0][2]
        risk_improvement = best["risk_before"] - best["risk_after"]
        stabilization_improvement = (
            best["stabilization_before"] - best["stabilization_after"]
        )
        if risk_improvement < 0.03 and stabilization_improvement < 20:
            return self._create_no_action_recommendation(
                event_id,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "Constrained candidates do not provide a material improvement.",
            )

        delta = best["proposed_value"] - best["current_value"]
        direction = "Increase" if delta > 0 else "Decrease"
        rec = Recommendation(
            recommendation_id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=decision_time,
            parameter_name=best["parameter_name"],
            current_value=best["current_value"],
            recommended_value=best["proposed_value"],
            recommended_ramp_rate=delta
            / counterfactual_service.RAMP_SECONDS,
            risk_before=best["risk_before"],
            risk_after=best["risk_after"],
            stabilization_before=best["stabilization_before"],
            stabilization_after=best["stabilization_after"],
            confidence=best["confidence"],
            rationale=(
                f"{direction} {best['parameter_name']} to "
                f"{best['proposed_value']:.2f}; projected off-spec exposure "
                f"falls by {best['avoided_off_spec_seconds']:.0f}s while "
                "remaining inside recipe and ramp constraints."
            ),
            status="pending",
        )
        db.add(rec)
        db.flush()
        db.add_all(
            [
                EvidenceTag(recommendation_id=rec.recommendation_id, **tag)
                for tag in best["evidence_tags"]
            ]
        )
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def _create_no_action_recommendation(
        event_id,
        db,
        current_risk,
        current_stabilization,
        timestamp=None,
        reason="No corrective action is currently recommended.",
    ):
        rec = Recommendation(
            recommendation_id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=timestamp
            or datetime.now(UTC).replace(tzinfo=None),
            parameter_name="No intervention",
            current_value=0.0,
            recommended_value=0.0,
            recommended_ramp_rate=0.0,
            risk_before=current_risk,
            risk_after=current_risk,
            stabilization_before=current_stabilization,
            stabilization_after=current_stabilization,
            confidence=0.95,
            rationale=f"{reason} Continue monitoring.",
            status="pending",
        )
        db.add(rec)
        db.flush()
        db.add(
            EvidenceTag(
                recommendation_id=rec.recommendation_id,
                tag="Safe Envelope",
                source="Risk forecast and active recipe constraints",
                detail=reason,
            )
        )
        db.commit()
        db.refresh(rec)
        return rec


recommendation_engine = RecommendationEngine()
