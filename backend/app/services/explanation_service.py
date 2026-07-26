"""Grounded operator explanations with an optional language-model renderer."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.domain import GradeChangeEvent, Recommendation, TimeseriesPoint
from app.services.correlation_service import correlation_service
from app.services.rootcause_service import rootcause_service
from ml.feature_service import feature_service
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service
from ml.trajectory_forecast import trajectory_forecaster_service


class ExplanationService:
    """Turn model facts into concise prose without delegating decisions."""

    def explain(
        self,
        event_id: str,
        timestamp: datetime,
        db: Session,
        recommendation_id: str | None = None,
        prefer_llm: bool = False,
    ) -> dict[str, Any] | None:
        facts = self._facts(
            event_id, timestamp, db, recommendation_id
        )
        if facts is None:
            return None
        fallback = self._deterministic(facts)
        if not prefer_llm or not settings.LLM_API_KEY:
            return fallback
        try:
            rendered = self._render_with_openai(facts)
            return {
                **rendered,
                "mode": "openai-grounded",
                "model": settings.LLM_MODEL,
                "evidence": fallback["evidence"],
                "guardrail": fallback["guardrail"],
            }
        except (
            OSError,
            TimeoutError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ):
            fallback["mode"] = "grounded-template-fallback"
            return fallback

    def _facts(
        self,
        event_id: str,
        timestamp: datetime,
        db: Session,
        recommendation_id: str | None,
    ) -> dict[str, Any] | None:
        event = (
            db.query(GradeChangeEvent)
            .filter(GradeChangeEvent.event_id == event_id)
            .first()
        )
        if not event:
            return None
        points = (
            db.query(TimeseriesPoint)
            .filter(
                TimeseriesPoint.event_id == event_id,
                TimeseriesPoint.timestamp <= timestamp.replace(tzinfo=None),
            )
            .order_by(TimeseriesPoint.timestamp.desc())
            .limit(60)
            .all()
        )
        if len(points) < 12:
            return None
        chronological = list(reversed(points))
        window = chronological[-12:]
        latest = window[-1]
        features = feature_service.extract_features(window)
        risk = risk_predictor_service.predict_risk(features)
        trajectory = trajectory_forecaster_service.forecast(features)
        stabilization = stabilization_service.estimate_stabilization(features)
        causes = rootcause_service.get_root_causes(
            event_id, db, features=features
        )
        relationships = (
            correlation_service.discover_relationships(
                event_id, db, timestamp=timestamp
            )
            if len(chronological) >= 30
            else []
        )
        recommendation = None
        if recommendation_id:
            recommendation = (
                db.query(Recommendation)
                .filter(
                    Recommendation.event_id == event_id,
                    Recommendation.recommendation_id
                    == recommendation_id,
                    Recommendation.timestamp
                    == timestamp.replace(tzinfo=None),
                )
                .first()
            )
        return {
            "event": {
                "event_id": event.event_id,
                "transition": (
                    f"{event.source_grade} to {event.target_grade}"
                ),
                "machine": event.machine_id,
                "recipe": event.recipe_id,
                "spec_limit_pct": settings.SPEC_DEVIATION_PCT,
            },
            "state": {
                "timestamp": timestamp.isoformat(),
                "basis_weight_actual": round(
                    latest.basis_weight_actual, 2
                ),
                "basis_weight_setpoint": round(
                    latest.basis_weight_setpoint, 2
                ),
                "deviation_pct": round(
                    features["bw_deviation_pct"], 2
                ),
                "risk_probability": risk["probability"],
                "risk_level": risk["risk_level"],
                "direction": risk["direction"],
                "time_to_violation_seconds": (
                    risk["time_to_violation_seconds"]
                ),
                "estimated_stabilization_seconds": stabilization[
                    "estimated_seconds"
                ],
                "scanner_quality": round(
                    latest.scanner_quality_score, 2
                ),
                "active_alarms": latest.active_alarm_count,
            },
            "trajectory": trajectory["horizons"],
            "root_causes": [
                {
                    "parameter": cause.parameter_name,
                    "contribution_pct": round(
                        cause.contribution_pct * 100.0, 1
                    ),
                    "current_deviation": cause.current_deviation,
                    "is_interaction": cause.is_interaction,
                }
                for cause in causes[:3]
            ],
            "relationships": [
                {
                    "source": item.source_parameter,
                    "target": item.target_parameter,
                    "strength": round(item.strength, 2),
                    "lag_seconds": item.lag_seconds,
                    "is_new": item.is_newly_discovered,
                }
                for item in relationships[:3]
            ],
            "recommendation": (
                {
                    "parameter": recommendation.parameter_name,
                    "current_value": recommendation.current_value,
                    "recommended_value": recommendation.recommended_value,
                    "ramp_rate": recommendation.recommended_ramp_rate,
                    "risk_before": recommendation.risk_before,
                    "risk_after": recommendation.risk_after,
                    "rationale": recommendation.rationale,
                    "evidence": [
                        {
                            "tag": tag.tag,
                            "source": tag.source,
                            "detail": tag.detail,
                        }
                        for tag in recommendation.evidence_tags
                    ],
                }
                if recommendation
                else None
            ),
        }

    @staticmethod
    def _deterministic(facts: dict[str, Any]) -> dict[str, Any]:
        state = facts["state"]
        causes = facts["root_causes"]
        relationships = facts["relationships"]
        recommendation = facts["recommendation"]
        risk_pct = round(state["risk_probability"] * 100)
        deviation = state["deviation_pct"]
        direction_word = "above" if deviation >= 0 else "below"
        top_cause = causes[0] if causes else None
        limit = facts["event"]["spec_limit_pct"]
        if risk_pct >= 75:
            headline = (
                f"Basis Weight is at critical transition risk ({risk_pct}%)."
            )
        elif risk_pct >= 50:
            headline = (
                f"Basis Weight is approaching the spec boundary ({risk_pct}% risk)."
            )
        else:
            headline = (
                f"Basis Weight remains inside the predicted safe envelope ({risk_pct}% risk)."
            )
        what = (
            f"Measured Basis Weight is {state['basis_weight_actual']:.2f} gsm "
            f"against {state['basis_weight_setpoint']:.2f} gsm, or "
            f"{abs(deviation):.2f}% {direction_word} target. The model estimates "
            f"{state['estimated_stabilization_seconds']:.0f} seconds to stabilize."
        )
        if top_cause:
            why = (
                f"{top_cause['parameter']} is the largest local driver at "
                f"{top_cause['contribution_pct']:.0f}% of the explained risk"
            )
            if relationships:
                relationship = relationships[0]
                why += (
                    f". Historical replay also shows "
                    f"{relationship['source']} linked to "
                    f"{relationship['target']} with strength "
                    f"{relationship['strength']:+.2f} at a "
                    f"{relationship['lag_seconds']}-second lag"
                )
            why += ". These are predictive associations, not proof of causality."
        else:
            why = (
                "No stable local driver is available yet; continue collecting "
                "a complete 60-second feature window."
            )
        if recommendation and recommendation["parameter"] != "No intervention":
            suggested = (
                f"Evaluate moving {recommendation['parameter']} from "
                f"{recommendation['current_value']:.2f} to "
                f"{recommendation['recommended_value']:.2f} at "
                f"{recommendation['ramp_rate']:+.2f}/s. The constrained "
                f"counterfactual changes risk from "
                f"{recommendation['risk_before'] * 100:.0f}% to "
                f"{recommendation['risk_after'] * 100:.0f}%."
            )
        elif recommendation:
            suggested = recommendation["rationale"]
        else:
            suggested = (
                "Generate a constrained counterfactual before changing a "
                "setpoint; no unvalidated control action is proposed."
            )
        evidence = [
            {
                "tag": "Current State",
                "source": "QCS/DCS replay window",
                "detail": (
                    f"{state['basis_weight_actual']:.2f} gsm actual, "
                    f"{state['basis_weight_setpoint']:.2f} gsm setpoint, "
                    f"{abs(deviation):.2f}% deviation."
                ),
            },
            {
                "tag": "Risk & Trajectory",
                "source": "LightGBM + 30/60/120-second models",
                "detail": (
                    f"{risk_pct}% probability of exceeding the ±{limit}% "
                    "specification boundary."
                ),
            },
            {
                "tag": "Root Cause",
                "source": "Timestamp-safe local SHAP",
                "detail": (
                    f"{top_cause['parameter']} contributes "
                    f"{top_cause['contribution_pct']:.0f}% locally."
                    if top_cause
                    else "No local contribution is available."
                ),
            },
        ]
        if recommendation:
            evidence.extend(recommendation["evidence"][:2])
        return {
            "mode": "grounded-template",
            "model": None,
            "headline": headline,
            "what_is_happening": what,
            "why": why,
            "suggested_response": suggested,
            "operator_checks": [
                "Confirm scanner quality and sheet-break/alarm status.",
                "Verify the active target-grade recipe and actuator availability.",
                "Run the proposed setpoints in Scenario Lab before accepting.",
            ],
            "evidence": evidence,
            "guardrail": (
                "Explanation only. Risk and setpoints come from deterministic "
                "models and recipe checks; GradeLens never writes to live QCS/MPC."
            ),
        }

    @staticmethod
    def _render_with_openai(
        facts: dict[str, Any],
    ) -> dict[str, Any]:
        instructions = (
            "You explain a paper-machine grade change to an operator. Use only "
            "the supplied JSON facts. Do not calculate or invent numbers, causes, "
            "setpoints, or guarantees. Keep associations distinct from causality. "
            "Return one valid JSON object with exactly: headline, "
            "what_is_happening, why, suggested_response, operator_checks. "
            "operator_checks must contain exactly three short strings."
        )
        payload = {
            "model": settings.LLM_MODEL,
            "instructions": instructions,
            "input": json.dumps(facts, separators=(",", ":")),
            "reasoning": {"effort": "low"},
            "text": {"verbosity": "low"},
            "store": False,
        }
        request = urllib.request.Request(
            f"{settings.LLM_BASE_URL.rstrip('/')}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=settings.LLM_TIMEOUT_SECONDS
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = result.get("output_text")
        if not text:
            text = next(
                (
                    content.get("text")
                    for item in result.get("output", [])
                    for content in item.get("content", [])
                    if content.get("type") == "output_text"
                ),
                None,
            )
        if not text:
            raise ValueError("The language model returned no text.")
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(clean)
        required = {
            "headline",
            "what_is_happening",
            "why",
            "suggested_response",
            "operator_checks",
        }
        if (
            set(parsed) != required
            or not all(
                isinstance(parsed[field], str)
                for field in required - {"operator_checks"}
            )
            or not isinstance(parsed["operator_checks"], list)
            or len(parsed["operator_checks"]) != 3
            or not all(
                isinstance(item, str)
                for item in parsed["operator_checks"]
            )
        ):
            raise ValueError("The language model output contract was invalid.")
        return parsed


explanation_service = ExplanationService()
