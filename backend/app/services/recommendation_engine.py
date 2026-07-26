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
    RecipeConstraint,
    Recommendation,
    TimeseriesPoint,
)
from app.services.counterfactual_service import counterfactual_service
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service


class RecommendationEngine:
    MIN_RISK_IMPROVEMENT = 0.03
    MIN_AVOIDED_OFF_SPEC_SECONDS = 10.0
    MIN_STABILIZATION_IMPROVEMENT_SECONDS = 60.0
    MIN_STABILIZATION_IMPROVEMENT_FRACTION = 0.10

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
        current_risk_result = risk_predictor_service.predict_risk(features)
        current_risk = current_risk_result["probability"]
        current_stabilization = stabilization_service.estimate_stabilization(
            features
        )["estimated_seconds"]
        no_action_confidence = self._estimate_no_action_confidence(
            latest,
            current_risk,
            current_risk_result["model_mode"],
            risk_predictor_service.decision_threshold,
        )

        if current_risk < risk_predictor_service.decision_threshold:
            return self._create_no_action_recommendation(
                event,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "Current forecast remains within the operating envelope.",
                no_action_confidence,
                latest,
                risk_predictor_service.decision_threshold,
                current_risk_result["model_mode"],
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
                event,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "No candidate satisfies the active recipe and actuator limits.",
                no_action_confidence,
                latest,
                risk_predictor_service.decision_threshold,
                current_risk_result["model_mode"],
            )

        scored.sort(key=lambda item: (item[0], item[1]))
        best = scored[0][2]
        if not self._is_material_improvement(best):
            return self._create_no_action_recommendation(
                event,
                db,
                current_risk,
                current_stabilization,
                decision_time,
                "Constrained candidates do not provide a material improvement.",
                no_action_confidence,
                latest,
                risk_predictor_service.decision_threshold,
                current_risk_result["model_mode"],
            )

        delta = best["proposed_value"] - best["current_value"]
        direction = "Increase" if delta > 0 else "Decrease"
        benefit_summary = self._benefit_summary(best)
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
                f"{best['proposed_value']:.2f}; {benefit_summary} while "
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

    @classmethod
    def _is_material_improvement(cls, simulation: dict) -> bool:
        """Require a meaningful risk, quality-loss, or stabilization benefit."""
        risk_improvement = (
            simulation["risk_before"] - simulation["risk_after"]
        )
        avoided_off_spec_seconds = simulation["avoided_off_spec_seconds"]
        stabilization_improvement = (
            simulation["stabilization_before"]
            - simulation["stabilization_after"]
        )
        required_stabilization_improvement = max(
            cls.MIN_STABILIZATION_IMPROVEMENT_SECONDS,
            cls.MIN_STABILIZATION_IMPROVEMENT_FRACTION
            * simulation["stabilization_before"],
        )
        return bool(
            risk_improvement >= cls.MIN_RISK_IMPROVEMENT
            or avoided_off_spec_seconds >= cls.MIN_AVOIDED_OFF_SPEC_SECONDS
            or stabilization_improvement
            >= required_stabilization_improvement
        )

    @staticmethod
    def _benefit_summary(simulation: dict) -> str:
        avoided = simulation["avoided_off_spec_seconds"]
        risk_improvement_pct = max(
            0.0,
            (
                simulation["risk_before"]
                - simulation["risk_after"]
            )
            * 100.0,
        )
        stabilization_improvement = max(
            0.0,
            simulation["stabilization_before"]
            - simulation["stabilization_after"],
        )
        if avoided >= RecommendationEngine.MIN_AVOIDED_OFF_SPEC_SECONDS:
            return (
                f"projected off-spec exposure falls by {avoided:.0f}s, "
                f"risk by {risk_improvement_pct:.1f} points, and "
                f"stabilization by {stabilization_improvement:.0f}s"
            )
        if risk_improvement_pct >= (
            RecommendationEngine.MIN_RISK_IMPROVEMENT * 100.0
        ):
            return (
                f"projected risk falls by {risk_improvement_pct:.1f} "
                f"percentage points and stabilization improves by "
                f"{stabilization_improvement:.0f}s"
            )
        return (
            f"projected stabilization improves by "
            f"{stabilization_improvement:.0f}s"
        )

    @staticmethod
    def _estimate_no_action_confidence(
        latest: TimeseriesPoint,
        current_risk: float,
        model_mode: str,
        decision_threshold: float,
    ) -> float:
        """Ground no-action confidence in data/model quality and risk margin."""
        scanner_quality = min(
            1.0, max(0.0, float(latest.scanner_quality_score))
        )
        alarm_penalty = min(
            0.40, max(0, int(latest.active_alarm_count)) * 0.08
        )
        data_quality = max(0.0, scanner_quality - alarm_penalty)
        model_quality = 1.0 if model_mode == "trained" else 0.60
        scale = max(decision_threshold, 1.0 - decision_threshold, 1e-6)
        risk_margin = min(
            1.0, abs(current_risk - decision_threshold) / scale
        )
        confidence = (
            0.35
            + 0.30 * data_quality
            + 0.20 * model_quality
            + 0.10 * risk_margin
        )
        return round(min(0.95, max(0.50, confidence)), 2)

    @staticmethod
    def _create_no_action_recommendation(
        event,
        db,
        current_risk,
        current_stabilization,
        timestamp=None,
        reason="No corrective action is currently recommended.",
        confidence=0.50,
        latest=None,
        decision_threshold=0.60,
        model_mode="degraded",
    ):
        operator_response = (
            "Continue monitoring."
            if current_risk < decision_threshold
            else "Hold current setpoints and request operator review."
        )
        rec = Recommendation(
            recommendation_id=str(uuid.uuid4()),
            event_id=event.event_id,
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
            confidence=confidence,
            rationale=f"{reason} {operator_response}",
            status="pending",
        )
        db.add(rec)
        db.flush()

        evidence = [
            {
                "tag": "Risk Forecast",
                "source": (
                    f"{model_mode.title()} 120-second basis-weight risk model"
                ),
                "detail": (
                    f"Forecast risk is {current_risk * 100:.1f}% versus the "
                    f"{decision_threshold * 100:.1f}% intervention threshold."
                ),
            },
            {
                "tag": "Historical Stability",
                "source": (
                    "Chronologically validated historical-transition model"
                ),
                "detail": (
                    f"Estimated stabilization remaining is "
                    f"{current_stabilization:.0f} seconds."
                ),
            },
        ]

        if latest is not None:
            setpoint = abs(float(latest.basis_weight_setpoint))
            deviation_pct = (
                abs(
                    float(latest.basis_weight_actual)
                    - float(latest.basis_weight_setpoint)
                )
                / setpoint
                * 100.0
                if setpoint > 1e-6
                else 0.0
            )
            spec_margin = settings.SPEC_DEVIATION_PCT - deviation_pct
            margin_detail = (
                f"Current deviation is {deviation_pct:.2f}%; "
                f"{spec_margin:.2f} percentage points remain before the "
                f"±{settings.SPEC_DEVIATION_PCT:.1f}% limit."
                if spec_margin >= 0
                else (
                    f"Current deviation is {deviation_pct:.2f}%, exceeding "
                    f"the ±{settings.SPEC_DEVIATION_PCT:.1f}% limit by "
                    f"{abs(spec_margin):.2f} percentage points."
                )
            )
            evidence.extend(
                [
                    {
                        "tag": "Specification Margin",
                        "source": (
                            "Current QCS basis-weight measurement and "
                            "configured specification limit"
                        ),
                        "detail": margin_detail,
                    },
                    {
                        "tag": "Scanner Diagnostics",
                        "source": (
                            "QCS scanner quality and active alarm history"
                        ),
                        "detail": (
                            f"Scanner quality is "
                            f"{float(latest.scanner_quality_score) * 100:.0f}% "
                            f"with {int(latest.active_alarm_count)} active "
                            f"alarm(s)."
                        ),
                    },
                ]
            )

        constraint_count = (
            db.query(RecipeConstraint)
            .filter(RecipeConstraint.grade_id == event.target_grade)
            .count()
        )
        evidence.append(
            {
                "tag": "Recipe Envelope",
                "source": (
                    f"Target-grade recipe {event.recipe_id}"
                ),
                "detail": (
                    f"{constraint_count} active parameter constraint(s) are "
                    f"registered for grade {event.target_grade}. {reason}"
                ),
            }
        )
        db.add_all(
            [
                EvidenceTag(
                    recommendation_id=rec.recommendation_id,
                    **tag,
                )
                for tag in evidence
            ]
        )
        db.commit()
        db.refresh(rec)
        return rec


recommendation_engine = RecommendationEngine()
