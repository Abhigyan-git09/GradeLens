"""Constrained, explainable what-if simulation for grade-change interventions."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import (
    GradeChangeEvent,
    RecipeConstraint,
    TimeseriesPoint,
)
from ml.feature_service import FEATURE_NAMES, feature_service
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service
from ml.trajectory_forecast import trajectory_forecaster_service


class CounterfactualService:
    """Hybrid response model constrained by recipe and actuator limits.

    LightGBM supplies the learned baseline. A small, explicit process-response
    layer applies the expected direction and transport response of an operator
    setpoint change. The transparent hybrid is preferable to claiming causal
    effects from a small synthetic dataset.
    """

    RAMP_SECONDS = 15.0
    # Keep baseline and intervention comparisons symmetric. Equal weighting
    # avoids letting a saturated classifier drown out the responsive
    # 30/60/120-second trajectory until site data supports calibrated weights.
    RISK_MODEL_WEIGHT = 0.50
    RISK_TRAJECTORY_WEIGHT = 1.0 - RISK_MODEL_WEIGHT
    PARAMETER_CONFIG = {
        "stock_flow": {
            "display": "Stock Flow",
            "actual_attr": "stock_flow_actual",
            "feature": "stock_flow_ramp",
            "bw_gain_per_pct": 0.38,
            "source": "Historical response + mass-balance prior",
        },
        "machine_speed": {
            "display": "Machine Speed",
            "actual_attr": "machine_speed_actual",
            "feature": "machine_speed_ramp",
            "bw_gain_per_pct": -0.30,
            "source": "Historical response + sheet mass-balance prior",
        },
        "filler_flow": {
            "display": "Filler Flow",
            "actual_attr": "filler_flow_actual",
            "feature": "filler_flow_ramp",
            "bw_gain_per_pct": 0.11,
            "source": "Historical response + furnish prior",
        },
        "steam_pressure": {
            "display": "Steam Pressure",
            "actual_attr": "steam_pressure_actual",
            "feature": "steam_pressure_slope",
            "bw_gain_per_pct": -0.07,
            "source": "Historical drying response prior",
        },
    }
    DISPLAY_TO_KEY = {
        config["display"].lower(): key
        for key, config in PARAMETER_CONFIG.items()
    }

    def normalize_parameter(self, parameter_name: str) -> str | None:
        key = parameter_name.strip().lower().replace(" ", "_")
        if key in self.PARAMETER_CONFIG:
            return key
        return self.DISPLAY_TO_KEY.get(parameter_name.strip().lower())

    def simulate(
        self,
        event_id: str,
        timestamp: datetime,
        parameter_name: str,
        proposed_value: float,
        db: Session,
    ) -> dict[str, Any] | None:
        event = (
            db.query(GradeChangeEvent)
            .filter(GradeChangeEvent.event_id == event_id)
            .first()
        )
        parameter = self.normalize_parameter(parameter_name)
        if not event or not parameter:
            return None

        points = (
            db.query(TimeseriesPoint)
            .filter(
                TimeseriesPoint.event_id == event_id,
                TimeseriesPoint.timestamp <= timestamp.replace(tzinfo=None),
            )
            .order_by(TimeseriesPoint.timestamp.desc())
            .limit(12)
            .all()
        )
        if len(points) < 12:
            return None
        window = list(reversed(points))
        latest = window[-1]
        config = self.PARAMETER_CONFIG[parameter]
        current_value = float(getattr(latest, config["actual_attr"]))

        constraint = (
            db.query(RecipeConstraint)
            .filter(
                RecipeConstraint.grade_id == event.target_grade,
                RecipeConstraint.parameter == parameter,
            )
            .first()
        )
        feasible, constraint_message = self._validate_constraint(
            constraint, current_value, proposed_value
        )

        features = feature_service.extract_features(window)
        baseline_risk_result = risk_predictor_service.predict_risk(features)
        baseline_stabilization = stabilization_service.estimate_stabilization(
            features
        )
        baseline = trajectory_forecaster_service.forecast(features)

        simulated_features = features.copy()
        simulated_features[config["feature"]] = (
            proposed_value - current_value
        ) / self.RAMP_SECONDS
        model_counterfactual = trajectory_forecaster_service.forecast(
            simulated_features
        )

        counterfactual = self._apply_response(
            baseline,
            model_counterfactual,
            current_value,
            proposed_value,
            config["bw_gain_per_pct"],
        )
        baseline_trajectory_risk = self._trajectory_risk(baseline)
        counterfactual_trajectory_risk = self._trajectory_risk(counterfactual)
        simulated_model_risk = risk_predictor_service.predict_risk(
            simulated_features
        )["probability"]

        blended_risk_before = round(
            self.RISK_MODEL_WEIGHT * baseline_risk_result["probability"]
            + self.RISK_TRAJECTORY_WEIGHT * baseline_trajectory_risk,
            3,
        )
        blended_risk_after = round(
            self.RISK_MODEL_WEIGHT * simulated_model_risk
            + self.RISK_TRAJECTORY_WEIGHT * counterfactual_trajectory_risk,
            3,
        )
        risk_before = round(baseline_risk_result["probability"], 3)
        risk_after = self._align_counterfactual_risk(
            risk_before, blended_risk_before, blended_risk_after
        )
        if not feasible:
            risk_after = risk_before

        off_spec_before = self._off_spec_exposure(baseline)
        off_spec_after = (
            self._off_spec_exposure(counterfactual)
            if feasible
            else off_spec_before
        )
        avoided = max(0.0, off_spec_before - off_spec_after)

        baseline_error = self._max_deviation_pct(baseline)
        counterfactual_error = self._max_deviation_pct(counterfactual)
        error_ratio = min(
            1.5,
            counterfactual_error / max(baseline_error, 0.1),
        )
        stabilization_before = float(
            baseline_stabilization["estimated_seconds"]
        )
        stabilization_after = (
            max(0.0, stabilization_before * (0.25 + 0.75 * error_ratio))
            if feasible
            else stabilization_before
        )

        data_quality = max(
            0.4,
            min(
                1.0,
                float(latest.scanner_quality_score)
                - 0.04 * float(latest.active_alarm_count),
            ),
        )
        model_quality = (
            1.0
            if baseline["model_mode"] == "trained"
            and baseline_risk_result["model_mode"] == "trained"
            else 0.65
        )
        confidence = round(0.5 + 0.25 * data_quality + 0.2 * model_quality, 2)
        risk_before_pct = math.floor(risk_before * 100 + 0.5)
        risk_after_pct = math.floor(risk_after * 100 + 0.5)

        evidence_tags = [
            {
                "tag": "Risk Forecast",
                "source": "LightGBM + specification trajectory",
                "detail": (
                    f"Risk changes from {risk_before_pct}% to "
                    f"{risk_after_pct}% across the 120-second horizon."
                ),
            },
            {
                "tag": "Recipe Constraint",
                "source": f"{event.target_grade} recipe",
                "detail": constraint_message,
            },
            {
                "tag": "Process Response",
                "source": config["source"],
                "detail": (
                    "Counterfactual response includes a transparent "
                    "30/60/120-second transport response."
                ),
            },
            {
                "tag": "Data Quality",
                "source": "Scanner diagnostics and active alarms",
                "detail": (
                    f"Scanner quality {latest.scanner_quality_score:.2f}; "
                    f"{latest.active_alarm_count} active alarm(s)."
                ),
            },
        ]

        return {
            "parameter_name": config["display"],
            "current_value": round(current_value, 3),
            "proposed_value": round(float(proposed_value), 3),
            "feasible": feasible,
            "constraint_message": constraint_message,
            "risk_before": risk_before,
            "risk_after": risk_after,
            "stabilization_before": round(stabilization_before, 1),
            "stabilization_after": round(stabilization_after, 1),
            "off_spec_seconds_before": round(off_spec_before, 1),
            "off_spec_seconds_after": round(off_spec_after, 1),
            "avoided_off_spec_seconds": round(avoided, 1),
            "confidence": confidence,
            "baseline_trajectory": baseline,
            "counterfactual_trajectory": counterfactual,
            "evidence_tags": evidence_tags,
        }

    def candidate_values(
        self,
        event: GradeChangeEvent,
        latest: TimeseriesPoint,
        db: Session,
    ) -> list[tuple[str, float]]:
        constraints = {
            item.parameter: item
            for item in db.query(RecipeConstraint)
            .filter(RecipeConstraint.grade_id == event.target_grade)
            .all()
        }
        candidates: list[tuple[str, float]] = []
        for parameter, config in self.PARAMETER_CONFIG.items():
            constraint = constraints.get(parameter)
            if not constraint:
                continue
            current = float(getattr(latest, config["actual_attr"]))
            span = constraint.max_val - constraint.min_val
            values = {
                current,
                constraint.optimal_val,
                *(
                    current + span * fraction
                    for fraction in (-0.10, -0.06, -0.03, 0.03, 0.06, 0.10)
                ),
            }
            for value in sorted(values):
                feasible, _ = self._validate_constraint(
                    constraint, current, value
                )
                if feasible:
                    candidates.append((parameter, float(value)))
        return candidates

    def rank_opportunities(
        self,
        event_id: str,
        timestamp: datetime,
        db: Session,
    ) -> list[dict[str, Any]]:
        event = (
            db.query(GradeChangeEvent)
            .filter(GradeChangeEvent.event_id == event_id)
            .first()
        )
        latest = (
            db.query(TimeseriesPoint)
            .filter(
                TimeseriesPoint.event_id == event_id,
                TimeseriesPoint.timestamp <= timestamp.replace(tzinfo=None),
            )
            .order_by(TimeseriesPoint.timestamp.desc())
            .first()
        )
        if not event or not latest:
            return []
        best_by_parameter: dict[str, dict[str, Any]] = {}
        for parameter, value in self.candidate_values(event, latest, db):
            result = self.simulate(
                event_id, timestamp, parameter, value, db
            )
            if not result or not result["feasible"]:
                continue
            current_best = best_by_parameter.get(parameter)
            score = (
                result["risk_after"]
                + result["stabilization_after"] / 600.0
            )
            current_score = (
                current_best["risk_after"]
                + current_best["stabilization_after"] / 600.0
                if current_best
                else float("inf")
            )
            if score < current_score:
                best_by_parameter[parameter] = result
        opportunities = list(best_by_parameter.values())
        opportunities.sort(
            key=lambda item: (
                item["risk_after"],
                item["stabilization_after"],
            )
        )
        return opportunities

    def simulate_scenario(
        self,
        event_id: str,
        timestamp: datetime,
        adjustments: list[dict[str, Any]],
        db: Session,
    ) -> dict[str, Any] | None:
        """Simulate up to four coordinated, recipe-bounded adjustments."""
        if not 1 <= len(adjustments) <= 4:
            return None
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
            .limit(12)
            .all()
        )
        if len(points) < 12:
            return None
        window = list(reversed(points))
        latest = window[-1]
        features = feature_service.extract_features(window)
        baseline_risk_result = risk_predictor_service.predict_risk(features)
        baseline_stabilization = stabilization_service.estimate_stabilization(
            features
        )
        baseline = trajectory_forecaster_service.forecast(features)
        constraints = {
            item.parameter: item
            for item in db.query(RecipeConstraint)
            .filter(RecipeConstraint.grade_id == event.target_grade)
            .all()
        }

        normalized = []
        seen = set()
        simulated_features = features.copy()
        all_feasible = True
        for adjustment in adjustments:
            parameter = self.normalize_parameter(
                str(adjustment.get("parameter_name", ""))
            )
            if not parameter or parameter in seen:
                return None
            seen.add(parameter)
            config = self.PARAMETER_CONFIG[parameter]
            current_value = float(getattr(latest, config["actual_attr"]))
            proposed_value = float(adjustment["proposed_value"])
            feasible, message = self._validate_constraint(
                constraints.get(parameter), current_value, proposed_value
            )
            all_feasible = all_feasible and feasible
            if feasible:
                simulated_features[config["feature"]] = (
                    proposed_value - current_value
                ) / self.RAMP_SECONDS
            normalized.append(
                {
                    "key": parameter,
                    "parameter_name": config["display"],
                    "current_value": round(current_value, 3),
                    "proposed_value": round(proposed_value, 3),
                    "feasible": feasible,
                    "constraint_message": message,
                    "evidence_source": (
                        f"{event.target_grade} recipe + {config['source']}"
                    ),
                }
            )

        model_counterfactual = trajectory_forecaster_service.forecast(
            simulated_features
        )
        counterfactual = (
            self._apply_multiple_response(
                baseline, model_counterfactual, normalized
            )
            if all_feasible
            else baseline
        )
        baseline_trajectory_risk = self._trajectory_risk(baseline)
        counterfactual_trajectory_risk = self._trajectory_risk(
            counterfactual
        )
        simulated_model_risk = risk_predictor_service.predict_risk(
            simulated_features
        )["probability"]
        blended_risk_before = round(
            self.RISK_MODEL_WEIGHT * baseline_risk_result["probability"]
            + self.RISK_TRAJECTORY_WEIGHT * baseline_trajectory_risk,
            3,
        )
        blended_risk_after = round(
                self.RISK_MODEL_WEIGHT * simulated_model_risk
                + self.RISK_TRAJECTORY_WEIGHT
                * counterfactual_trajectory_risk,
                3,
            )
        risk_before = round(baseline_risk_result["probability"], 3)
        risk_after = (
            self._align_counterfactual_risk(
                risk_before, blended_risk_before, blended_risk_after
            )
            if all_feasible
            else risk_before
        )
        off_spec_before = self._off_spec_exposure(baseline)
        off_spec_after = (
            self._off_spec_exposure(counterfactual)
            if all_feasible
            else off_spec_before
        )
        baseline_error = self._max_deviation_pct(baseline)
        counterfactual_error = self._max_deviation_pct(counterfactual)
        error_ratio = min(
            1.5, counterfactual_error / max(baseline_error, 0.1)
        )
        stabilization_before = float(
            baseline_stabilization["estimated_seconds"]
        )
        stabilization_after = (
            max(0.0, stabilization_before * (0.25 + 0.75 * error_ratio))
            if all_feasible
            else stabilization_before
        )
        data_quality = max(
            0.4,
            min(
                1.0,
                float(latest.scanner_quality_score)
                - 0.04 * float(latest.active_alarm_count),
            ),
        )
        confidence = round(
            min(0.95, 0.52 + 0.25 * data_quality + 0.15), 2
        )
        evidence_tags = [
            {
                "tag": "Coordinated What-if",
                "source": "Hybrid learned + explicit response model",
                "detail": (
                    f"{len(normalized)} setpoint changes evaluated together "
                    "against the same 30/60/120-second baseline."
                ),
            },
            {
                "tag": "Recipe Guardrail",
                "source": f"{event.target_grade} recipe constraints",
                "detail": (
                    "Every proposed value and 15-second ramp must pass before "
                    "the counterfactual is evaluated."
                ),
            },
            {
                "tag": "Risk Forecast",
                "source": "LightGBM + specification trajectory",
                "detail": (
                    f"Risk changes from {risk_before * 100:.0f}% to "
                    f"{risk_after * 100:.0f}% in the scenario."
                ),
            },
            {
                "tag": "Data Quality",
                "source": "Scanner diagnostics and active alarms",
                "detail": (
                    f"Scanner quality {latest.scanner_quality_score:.2f}; "
                    f"{latest.active_alarm_count} active alarm(s)."
                ),
            },
        ]
        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "feasible": all_feasible,
            "scenario_mode": "advisory_hybrid_counterfactual",
            "adjustments": [
                {
                    key: value
                    for key, value in item.items()
                    if key != "key"
                }
                for item in normalized
            ],
            "risk_before": risk_before,
            "risk_after": risk_after,
            "stabilization_before": round(stabilization_before, 1),
            "stabilization_after": round(stabilization_after, 1),
            "off_spec_seconds_before": round(off_spec_before, 1),
            "off_spec_seconds_after": round(off_spec_after, 1),
            "avoided_off_spec_seconds": round(
                max(0.0, off_spec_before - off_spec_after), 1
            ),
            "confidence": confidence,
            "baseline_trajectory": baseline,
            "counterfactual_trajectory": counterfactual,
            "evidence_tags": evidence_tags,
            "guardrail": (
                "Advisory sandbox only. Run operator and MPC readiness checks "
                "before applying any setpoint in the live process."
            ),
        }

    def _validate_constraint(
        self,
        constraint: RecipeConstraint | None,
        current_value: float,
        proposed_value: float,
    ) -> tuple[bool, str]:
        if not constraint:
            return False, "No recipe constraint is configured for this parameter."
        if not constraint.min_val <= proposed_value <= constraint.max_val:
            return (
                False,
                f"Outside recipe range {constraint.min_val:.2f}–"
                f"{constraint.max_val:.2f}.",
            )
        ramp_rate = abs(proposed_value - current_value) / self.RAMP_SECONDS
        if (
            constraint.max_ramp_rate is not None
            and ramp_rate > constraint.max_ramp_rate
        ):
            return (
                False,
                f"Required ramp {ramp_rate:.2f}/s exceeds actuator limit "
                f"{constraint.max_ramp_rate:.2f}/s.",
            )
        return (
            True,
            f"Within {constraint.min_val:.2f}–{constraint.max_val:.2f}; "
            f"ramp {ramp_rate:.2f}/s is permitted.",
        )

    @staticmethod
    def _apply_response(
        baseline: dict,
        learned_counterfactual: dict,
        current_value: float,
        proposed_value: float,
        gain_per_pct: float,
    ) -> dict:
        pct_change = (
            (proposed_value - current_value) / current_value * 100.0
            if current_value
            else 0.0
        )
        response_fraction = {30: 0.45, 60: 0.78, 120: 1.0}
        learned_by_horizon = {
            int(item["seconds"]): item
            for item in learned_counterfactual["horizons"]
        }
        horizons = []
        for base in baseline["horizons"]:
            seconds = int(base["seconds"])
            learned = learned_by_horizon[seconds]
            explicit_effect = (
                pct_change
                * gain_per_pct
                * response_fraction.get(seconds, 1.0)
            )
            learned_delta = learned["predicted_bw"] - base["predicted_bw"]
            predicted_bw = (
                base["predicted_bw"]
                + 0.35 * learned_delta
                + 0.65 * explicit_effect
            )
            uncertainty = (
                learned["upper_bound"] - learned["lower_bound"]
            ) / 2.0
            horizons.append(
                {
                    "seconds": seconds,
                    "predicted_bw": round(predicted_bw, 2),
                    "predicted_setpoint": base["predicted_setpoint"],
                    "lower_bound": round(predicted_bw - uncertainty, 2),
                    "upper_bound": round(predicted_bw + uncertainty, 2),
                }
            )
        return {"horizons": horizons, "model_mode": "hybrid"}

    @classmethod
    def _apply_multiple_response(
        cls,
        baseline: dict,
        learned_counterfactual: dict,
        adjustments: list[dict[str, Any]],
    ) -> dict:
        response_fraction = {30: 0.45, 60: 0.78, 120: 1.0}
        learned_by_horizon = {
            int(item["seconds"]): item
            for item in learned_counterfactual["horizons"]
        }
        horizons = []
        for base in baseline["horizons"]:
            seconds = int(base["seconds"])
            learned = learned_by_horizon[seconds]
            explicit_effect = 0.0
            for adjustment in adjustments:
                config = cls.PARAMETER_CONFIG[adjustment["key"]]
                current = adjustment["current_value"]
                pct_change = (
                    (adjustment["proposed_value"] - current)
                    / current
                    * 100.0
                    if current
                    else 0.0
                )
                explicit_effect += (
                    pct_change
                    * config["bw_gain_per_pct"]
                    * response_fraction.get(seconds, 1.0)
                )
            learned_delta = learned["predicted_bw"] - base["predicted_bw"]
            predicted_bw = (
                base["predicted_bw"]
                + 0.35 * learned_delta
                + 0.65 * explicit_effect
            )
            uncertainty = (
                learned["upper_bound"] - learned["lower_bound"]
            ) / 2.0
            horizons.append(
                {
                    "seconds": seconds,
                    "predicted_bw": round(predicted_bw, 2),
                    "predicted_setpoint": base["predicted_setpoint"],
                    "lower_bound": round(predicted_bw - uncertainty, 2),
                    "upper_bound": round(predicted_bw + uncertainty, 2),
                }
            )
        return {"horizons": horizons, "model_mode": "hybrid"}

    @staticmethod
    def _max_deviation_pct(trajectory: dict) -> float:
        values = []
        for item in trajectory["horizons"]:
            setpoint = item["predicted_setpoint"]
            if setpoint:
                values.append(
                    abs(item["predicted_bw"] - setpoint) / setpoint * 100.0
                )
        return max(values, default=0.0)

    @staticmethod
    def _align_counterfactual_risk(
        classifier_baseline: float,
        blended_baseline: float,
        blended_counterfactual: float,
    ) -> float:
        """Apply the simulated relative effect to the displayed classifier risk.

        This keeps Command Center, recommendations, and Scenario Lab on one
        probability scale while retaining the trajectory model's responsiveness
        to setpoint changes.
        """
        relative_effect = blended_counterfactual / max(
            blended_baseline, 0.01
        )
        return round(
            min(0.99, max(0.01, classifier_baseline * relative_effect)),
            3,
        )

    @classmethod
    def _trajectory_risk(cls, trajectory: dict) -> float:
        max_deviation = cls._max_deviation_pct(trajectory)
        return 1.0 / (1.0 + math.exp(-2.2 * (max_deviation - 2.5)))

    @staticmethod
    def _off_spec_exposure(trajectory: dict) -> float:
        previous = 0.0
        exposure = 0.0
        for item in trajectory["horizons"]:
            seconds = float(item["seconds"])
            setpoint = item["predicted_setpoint"]
            deviation = (
                abs(item["predicted_bw"] - setpoint) / setpoint * 100.0
                if setpoint
                else 0.0
            )
            if deviation > 2.5:
                exposure += seconds - previous
            previous = seconds
        return exposure


counterfactual_service = CounterfactualService()
