"""Dataset provenance, EDA summaries, and upload-contract validation."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models.domain import GradeChangeEvent, TimeseriesPoint
from ml.feature_service import FEATURE_NAMES
from ml.risk_predictor import risk_predictor_service


class DataIntelligenceService:
    """Build compact, auditable evidence from the active application dataset."""

    PROCESS_FIELDS = [
        "basis_weight_actual",
        "basis_weight_setpoint",
        "stock_flow_actual",
        "stock_flow_setpoint",
        "filler_flow_actual",
        "filler_flow_setpoint",
        "steam_pressure_actual",
        "steam_pressure_setpoint",
        "machine_speed_actual",
        "machine_speed_setpoint",
        "moisture_actual",
        "moisture_setpoint",
        "ash_actual",
        "ash_setpoint",
        "caliper_actual",
        "caliper_setpoint",
        "active_alarm_count",
        "scanner_quality_score",
    ]
    REQUIRED_UPLOAD_COLUMNS = ["timestamp", *PROCESS_FIELDS]
    COLUMN_ALIASES = {
        "time": "timestamp",
        "datetime": "timestamp",
        "date_time": "timestamp",
        "basis_weight": "basis_weight_actual",
        "bw_actual": "basis_weight_actual",
        "bw_setpoint": "basis_weight_setpoint",
        "stock_flow": "stock_flow_actual",
        "stock_setpoint": "stock_flow_setpoint",
        "filler_flow": "filler_flow_actual",
        "filler_setpoint": "filler_flow_setpoint",
        "steam_pressure": "steam_pressure_actual",
        "steam_setpoint": "steam_pressure_setpoint",
        "machine_speed": "machine_speed_actual",
        "speed_setpoint": "machine_speed_setpoint",
        "moisture": "moisture_actual",
        "ash": "ash_actual",
        "caliper": "caliper_actual",
        "alarms": "active_alarm_count",
        "scanner_quality": "scanner_quality_score",
    }
    VARIABLE_META = {
        "basis_weight": ("Basis Weight", "gsm", "primary quality"),
        "stock_flow": ("Stock Flow", "L/min", "manipulated"),
        "filler_flow": ("Filler Flow", "L/min", "manipulated"),
        "steam_pressure": ("Steam Pressure", "bar", "manipulated"),
        "machine_speed": ("Machine Speed", "m/min", "manipulated"),
        "moisture": ("Moisture", "%", "quality"),
        "ash": ("Ash", "%", "quality"),
        "caliper": ("Caliper", "µm", "quality"),
    }

    def overview(self, db: Session) -> dict[str, Any]:
        events = (
            db.query(GradeChangeEvent)
            .order_by(GradeChangeEvent.start_time)
            .all()
        )
        points = (
            db.query(TimeseriesPoint)
            .order_by(TimeseriesPoint.event_id, TimeseriesPoint.timestamp)
            .all()
        )
        metrics = self._load_metrics()
        grouped: dict[str, list[TimeseriesPoint]] = defaultdict(list)
        for point in points:
            grouped[point.event_id].append(point)

        outcomes = Counter(event.transition_outcome for event in events)
        missing_cells = sum(
            getattr(point, field) is None
            for point in points
            for field in self.PROCESS_FIELDS
        )
        total_cells = max(1, len(points) * len(self.PROCESS_FIELDS))
        scanner_scores = [
            float(point.scanner_quality_score)
            for point in points
            if point.scanner_quality_score is not None
        ]
        alarm_points = sum(
            1 for point in points if (point.active_alarm_count or 0) > 0
        )
        sample_intervals = []
        for event_points in grouped.values():
            sample_intervals.extend(
                (
                    event_points[index].timestamp
                    - event_points[index - 1].timestamp
                ).total_seconds()
                for index in range(1, min(len(event_points), 20))
            )

        outcome_summary = []
        for outcome in sorted(outcomes):
            matching = [
                event for event in events
                if event.transition_outcome == outcome
            ]
            outcome_summary.append(
                {
                    "outcome": outcome,
                    "event_count": len(matching),
                    "avg_stabilization_seconds": self._mean(
                        event.stabilization_seconds for event in matching
                    ),
                    "avg_off_spec_seconds": self._mean(
                        event.off_spec_seconds for event in matching
                    ),
                    "avg_max_deviation_pct": self._mean(
                        event.max_deviation_pct for event in matching
                    ),
                }
            )

        training_pool = metrics.get("dataset", {}).get(
            "training_pool_events", 0
        )
        variables = []
        for prefix, (display, unit, role) in self.VARIABLE_META.items():
            variables.extend(
                [
                    {
                        "tag": f"{prefix}_actual",
                        "display_name": f"{display} Actual",
                        "unit": unit,
                        "role": role,
                        "source": "QCS/DCS historian analogue",
                    },
                    {
                        "tag": f"{prefix}_setpoint",
                        "display_name": f"{display} Setpoint",
                        "unit": unit,
                        "role": "control target",
                        "source": "Recipe / MD control analogue",
                    },
                ]
            )
        variables.extend(
            [
                {
                    "tag": "active_alarm_count",
                    "display_name": "Active Alarm Count",
                    "unit": "count",
                    "role": "operating context",
                    "source": "Alarm historian analogue",
                },
                {
                    "tag": "scanner_quality_score",
                    "display_name": "Scanner Quality",
                    "unit": "0–1",
                    "role": "data quality",
                    "source": "Scanner diagnostics analogue",
                },
            ]
        )

        return {
            "provenance": {
                "source_type": "deterministic synthetic historian",
                "dataset_label": "GradeLens hackathon demonstration dataset",
                "storage": "Local SQLite; read-only analytical path",
                "generated_by": "scripts/bootstrap.py process simulator",
                "synthetic": True,
                "deterministic_seed": 42,
                "sample_interval_seconds": round(
                    self._mean(sample_intervals), 2
                ),
                "event_count": len(events),
                "point_count": len(points),
                "start_time": (
                    events[0].start_time.isoformat() if events else None
                ),
                "end_time": (
                    max(
                        (
                            event.end_time or event.start_time
                            for event in events
                        ),
                        default=None,
                    ).isoformat()
                    if events
                    else None
                ),
                "machines": sorted({event.machine_id for event in events}),
                "grades": sorted(
                    {
                        grade
                        for event in events
                        for grade in (event.source_grade, event.target_grade)
                    }
                ),
                "grade_pairs": sorted(
                    {
                        f"{event.source_grade} → {event.target_grade}"
                        for event in events
                    }
                ),
                "site_data_status": (
                    "Not connected. Replace the simulator adapter with "
                    "site historian/DCS connectors for deployment."
                ),
            },
            "outcome_counts": dict(outcomes),
            "data_quality": {
                "missing_cells": missing_cells,
                "completeness_pct": round(
                    100.0 * (1.0 - missing_cells / total_cells), 2
                ),
                "avg_scanner_quality": round(
                    self._mean(scanner_scores), 3
                ),
                "alarm_point_pct": round(
                    100.0 * alarm_points / max(1, len(points)), 2
                ),
            },
            "variables": variables,
            "split": {
                "strategy": "event-level chronological split",
                "training_pool_events": training_pool,
                "train_events": metrics.get("dataset", {}).get(
                    "events_train", 0
                ),
                "validation_events": metrics.get("dataset", {}).get(
                    "events_validation", 0
                ),
                "test_events": metrics.get("dataset", {}).get(
                    "events_test", 0
                ),
                "curated_demo_events": metrics.get("dataset", {}).get(
                    "curated_demo_events", 0
                ),
                "demo_events_excluded": True,
                "future_window_leakage_prevented": True,
            },
            "model_metrics": metrics,
            "outcome_summary": outcome_summary,
            "trajectory_profiles": self._trajectory_profiles(events, grouped),
            "feature_importance": self._feature_importance(),
            "relationships": self._discover_global_relationships(
                grouped, limit=9
            ),
            "processing_steps": [
                {
                    "stage": "1 · Ingest",
                    "detail": (
                        "Historian-like actuals/setpoints, recipe limits, "
                        "alarms, scanner quality, and event outcomes."
                    ),
                },
                {
                    "stage": "2 · Align",
                    "detail": (
                        "Five-second samples are grouped by grade-change event; "
                        "only observations at or before decision time are used."
                    ),
                },
                {
                    "stage": "3 · Engineer",
                    "detail": (
                        "A 60-second causal window produces 16 deviation, slope, "
                        "ramp, data-quality, and interaction features."
                    ),
                },
                {
                    "stage": "4 · Predict",
                    "detail": (
                        "LightGBM predicts ±2.5% risk; trajectory models forecast "
                        "30/60/120 s; KNN estimates stabilization time."
                    ),
                },
                {
                    "stage": "5 · Constrain",
                    "detail": (
                        "Counterfactual candidates are checked against target "
                        "recipe ranges and actuator ramp limits."
                    ),
                },
                {
                    "stage": "6 · Explain & learn",
                    "detail": (
                        "Local contributions, historical relationships, source "
                        "tags, and operator accept/reject/modify feedback are retained."
                    ),
                },
            ],
        }

    def validate_upload(
        self,
        file_name: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized: dict[str, str] = {}
        for original in columns:
            clean = (
                original.strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("%", "pct")
            )
            canonical = self.COLUMN_ALIASES.get(clean, clean)
            if canonical in self.REQUIRED_UPLOAD_COLUMNS:
                normalized[canonical] = original
        missing = [
            field
            for field in self.REQUIRED_UPLOAD_COLUMNS
            if field not in normalized
        ]
        parse_errors = []
        numeric_fields = [
            field
            for field in self.REQUIRED_UPLOAD_COLUMNS
            if field != "timestamp" and field in normalized
        ]
        numeric_values = 0
        valid_numeric_values = 0
        for row_index, row in enumerate(rows[:500], start=2):
            for field in numeric_fields:
                numeric_values += 1
                value = row.get(normalized[field])
                try:
                    number = float(value)
                    if not np.isfinite(number):
                        raise ValueError
                    valid_numeric_values += 1
                except (TypeError, ValueError):
                    if len(parse_errors) < 12:
                        parse_errors.append(
                            f"Row {row_index}: {field} is not numeric."
                        )

        warnings = []
        if len(rows) < 12:
            warnings.append(
                "At least 12 samples (60 seconds at 5-second cadence) are "
                "needed before inference can start."
            )
        if len(rows) > 500:
            warnings.append(
                "Validation sampled the first 500 rows; the original file "
                "was not uploaded or persisted."
            )
        if "event_id" not in {
            column.strip().lower().replace(" ", "_") for column in columns
        }:
            warnings.append(
                "No event_id column found; a sandbox event identifier will "
                "be required before replay."
            )
        if missing:
            warnings.append(
                "Missing tags prevent full feature generation and model inference."
            )

        coverage = (
            100.0
            * (len(self.REQUIRED_UPLOAD_COLUMNS) - len(missing))
            / len(self.REQUIRED_UPLOAD_COLUMNS)
        )
        numeric_completeness = (
            100.0 * valid_numeric_values / max(1, numeric_values)
        )
        valid = (
            not missing
            and not parse_errors
            and len(rows) >= 12
        )
        return {
            "valid": valid,
            "file_name": file_name,
            "row_count": len(rows),
            "coverage_pct": round(coverage, 1),
            "mapped_columns": normalized,
            "missing_columns": missing,
            "warnings": warnings,
            "parse_errors": parse_errors,
            "data_quality": {
                "numeric_completeness_pct": round(
                    numeric_completeness, 1
                ),
                "validated_rows": min(len(rows), 500),
                "required_feature_window_rows": 12,
            },
            "preview": rows[:5],
            "sandbox_note": (
                "Validated in memory only. No row was written to the GradeLens "
                "database or any QCS/DCS control system."
            ),
        }

    @staticmethod
    def _load_metrics() -> dict[str, Any]:
        path = Path(settings.MODEL_DIR) / "metrics.json"
        if not path.exists():
            return {}
        with path.open(encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _mean(values) -> float:
        clean = [float(value) for value in values if value is not None]
        return round(sum(clean) / len(clean), 3) if clean else 0.0

    def _trajectory_profiles(
        self,
        events: list[GradeChangeEvent],
        grouped: dict[str, list[TimeseriesPoint]],
    ) -> list[dict[str, Any]]:
        values: dict[tuple[str, int], list[float]] = defaultdict(list)
        event_by_id = {event.event_id: event for event in events}
        for event_id, event_points in grouped.items():
            event = event_by_id.get(event_id)
            if not event or len(event_points) < 2:
                continue
            last_index = len(event_points) - 1
            for bucket in range(0, 101, 5):
                point = event_points[
                    min(last_index, round(last_index * bucket / 100.0))
                ]
                setpoint = float(point.basis_weight_setpoint or 0.0)
                deviation = (
                    100.0
                    * (float(point.basis_weight_actual) - setpoint)
                    / setpoint
                    if setpoint
                    else 0.0
                )
                values[(event.transition_outcome, bucket)].append(deviation)
        profiles = []
        for (outcome, bucket), deviations in sorted(values.items()):
            profiles.append(
                {
                    "outcome": outcome,
                    "progress_pct": bucket,
                    "mean_deviation_pct": round(
                        float(np.mean(deviations)), 3
                    ),
                    "p10_deviation_pct": round(
                        float(np.percentile(deviations, 10)), 3
                    ),
                    "p90_deviation_pct": round(
                        float(np.percentile(deviations, 90)), 3
                    ),
                }
            )
        return profiles

    @staticmethod
    def _feature_importance() -> list[dict[str, Any]]:
        model = risk_predictor_service.model
        raw = (
            np.asarray(model.feature_importances_, dtype=float)
            if model is not None and hasattr(model, "feature_importances_")
            else np.ones(len(FEATURE_NAMES), dtype=float)
        )
        denominator = float(raw.sum()) or 1.0
        importance = [
            {
                "feature": name,
                "importance": round(float(value / denominator), 4),
            }
            for name, value in zip(FEATURE_NAMES, raw)
        ]
        return sorted(
            importance, key=lambda item: item["importance"], reverse=True
        )

    @staticmethod
    def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
        if (
            len(left) < 30
            or float(np.std(left)) < 1e-9
            or float(np.std(right)) < 1e-9
        ):
            return 0.0
        return float(np.corrcoef(left, right)[0, 1])

    def _discover_global_relationships(
        self,
        grouped: dict[str, list[TimeseriesPoint]],
        limit: int,
    ) -> list[dict[str, Any]]:
        drivers = [
            "stock_flow",
            "filler_flow",
            "steam_pressure",
            "machine_speed",
            "moisture",
            "ash",
            "caliper",
        ]
        event_arrays: list[dict[str, np.ndarray]] = []
        for points in grouped.values():
            if len(points) < 20:
                continue
            arrays = {}
            for parameter in ["basis_weight", *drivers]:
                arrays[parameter] = np.asarray(
                    [
                        float(getattr(point, f"{parameter}_actual"))
                        - float(getattr(point, f"{parameter}_setpoint"))
                        for point in points
                    ],
                    dtype=float,
                )
            event_arrays.append(arrays)

        candidates = []
        for parameter in drivers:
            best_strength = 0.0
            best_lag = 0
            for lag_samples in (0, 2, 4, 6):
                left_parts = []
                right_parts = []
                for arrays in event_arrays:
                    if lag_samples:
                        left_parts.append(arrays[parameter][:-lag_samples])
                        right_parts.append(
                            arrays["basis_weight"][lag_samples:]
                        )
                    else:
                        left_parts.append(arrays[parameter])
                        right_parts.append(arrays["basis_weight"])
                strength = self._safe_corr(
                    np.concatenate(left_parts),
                    np.concatenate(right_parts),
                )
                if abs(strength) > abs(best_strength):
                    best_strength = strength
                    best_lag = lag_samples * 5
            candidates.append(
                {
                    "source_parameter": parameter,
                    "target_parameter": "basis_weight",
                    "strength": round(best_strength, 3),
                    "lag_seconds": best_lag,
                    "is_interaction": False,
                    "occurrences": len(event_arrays),
                    "source": (
                        "Historical event-level lag scan; association only"
                    ),
                }
            )

        for left_index, left_name in enumerate(drivers):
            for right_name in drivers[left_index + 1 :]:
                interactions = []
                target = []
                for arrays in event_arrays:
                    interactions.append(
                        arrays[left_name] * arrays[right_name]
                    )
                    target.append(arrays["basis_weight"])
                strength = self._safe_corr(
                    np.concatenate(interactions),
                    np.concatenate(target),
                )
                candidates.append(
                    {
                        "source_parameter": (
                            f"{left_name} × {right_name}"
                        ),
                        "target_parameter": "basis_weight",
                        "strength": round(strength, 3),
                        "lag_seconds": 0,
                        "is_interaction": True,
                        "occurrences": len(event_arrays),
                        "source": (
                            "Exploratory interaction scan; association only"
                        ),
                    }
                )
        candidates.sort(
            key=lambda item: abs(item["strength"]), reverse=True
        )
        return [
            item for item in candidates
            if abs(item["strength"]) >= 0.15
        ][:limit]


data_intelligence_service = DataIntelligenceService()
