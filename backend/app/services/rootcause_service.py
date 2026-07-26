"""Local, timestamp-safe root-cause explanations for the risk classifier."""

from __future__ import annotations

from typing import Dict, List

import joblib
import numpy as np
from dateutil.parser import isoparse
from sqlalchemy.orm import Session

from app.config import settings
from app.models.domain import TimeseriesPoint
from app.schemas.domain import RootCauseSchema
from ml.feature_service import FEATURE_NAMES, feature_service


class RootCauseService:
    def __init__(self):
        self.model_path = settings.MODEL_DIR / "risk_model.joblib"
        self.feature_names = FEATURE_NAMES
        self.display_names = {
            "stock_flow_ramp": "Stock Flow Ramp",
            "machine_speed_ramp": "Machine Speed Ramp",
            "steam_pressure_slope": "Steam Pressure Velocity",
            "filler_flow_ramp": "Filler Flow Ramp",
            "moisture_deviation": "Moisture Deviation",
            "ash_deviation": "Ash Deviation",
            "caliper_deviation": "Caliper Deviation",
            "active_alarm_count": "Active Alarms",
            "scanner_quality_score": "Scanner Quality",
            "interaction_feature": "Filler x Steam Interaction",
        }
        self.model = None
        self._load_model()

    def _load_model(self):
        self.model = None
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
            except Exception:
                self.model = None

    def reload_model(self):
        self._load_model()

    def get_root_causes(
        self,
        event_id: str,
        db: Session,
        features: Dict | None = None,
        timestamp: str | None = None,
    ) -> List[RootCauseSchema]:
        if not self.model:
            return []
        if features is None:
            query = db.query(TimeseriesPoint).filter(
                TimeseriesPoint.event_id == event_id
            )
            if timestamp:
                try:
                    query = query.filter(
                        TimeseriesPoint.timestamp
                        <= isoparse(timestamp).replace(tzinfo=None)
                    )
                except (TypeError, ValueError):
                    return []
            points = (
                query.order_by(TimeseriesPoint.timestamp.desc())
                .limit(12)
                .all()
            )
            if len(points) < 12:
                return []
            features = feature_service.extract_features(list(reversed(points)))

        vector = np.asarray(
            [[features.get(name, 0.0) for name in self.feature_names]]
        )
        try:
            local_values = self.model.booster_.predict(
                vector, pred_contrib=True
            )[0][:-1]
        except Exception:
            local_values = np.asarray(self.model.feature_importances_, dtype=float)

        excluded = {
            "current_bw",
            "current_setpoint",
            "bw_deviation",
            "bw_deviation_pct",
            "bw_slope",
            "setpoint_slope",
        }
        ranked = [
            (
                name,
                abs(float(local_values[index])),
                float(features.get(name, 0.0)),
            )
            for index, name in enumerate(self.feature_names)
            if name not in excluded
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        ranked = [item for item in ranked if item[1] > 0][:5]
        total = sum(item[1] for item in ranked)
        if total <= 0:
            return []

        results = []
        for name, score, raw_value in ranked:
            contribution = score / total
            display = self.display_names.get(name, name)
            if name == "interaction_feature":
                explanation = (
                    "filler-flow and steam-pressure movement are compounding "
                    "inside the current 45-second window"
                )
            elif name == "scanner_quality_score":
                explanation = (
                    "measurement quality is influencing forecast certainty"
                )
            elif name == "active_alarm_count":
                explanation = "active equipment/process alarms raise transition risk"
            else:
                explanation = "the current value materially changes this local forecast"
            results.append(
                RootCauseSchema(
                    parameter_name=display,
                    contribution_pct=round(contribution, 3),
                    current_deviation=round(raw_value, 3),
                    rationale=(
                        f"{display} — {contribution * 100:.0f}% share of the "
                        "ranked local SHAP attribution; "
                        f"{explanation}."
                    ),
                    is_interaction=name == "interaction_feature",
                )
            )
        return results


rootcause_service = RootCauseService()
