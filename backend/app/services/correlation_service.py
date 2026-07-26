"""Timestamp-safe lag and interaction discovery for process influence."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy.orm import Session

from app.models.domain import DiscoveredRelationship, TimeseriesPoint


class CorrelationService:
    KNOWN_PARAMETERS = {
        "stock": "Stock Flow",
        "speed": "Machine Speed",
        "filler": "Filler Flow",
        "steam": "Steam Pressure",
        "moisture": "Moisture",
        "ash": "Ash",
        "caliper": "Caliper",
    }

    def discover_relationships(
        self,
        event_id: str,
        db: Session,
        timestamp: datetime | None = None,
    ):
        query = db.query(TimeseriesPoint).filter(
            TimeseriesPoint.event_id == event_id
        )
        if timestamp is not None:
            query = query.filter(
                TimeseriesPoint.timestamp <= timestamp.replace(tzinfo=None)
            )
        points = query.order_by(TimeseriesPoint.timestamp.asc()).all()
        if len(points) < 30:
            return []

        frame = pd.DataFrame(
            {
                "bw": [
                    point.basis_weight_actual - point.basis_weight_setpoint
                    for point in points
                ],
                "stock": [
                    point.stock_flow_actual - point.stock_flow_setpoint
                    for point in points
                ],
                "speed": [
                    point.machine_speed_actual - point.machine_speed_setpoint
                    for point in points
                ],
                "filler": [
                    point.filler_flow_actual - point.filler_flow_setpoint
                    for point in points
                ],
                "steam": [
                    point.steam_pressure_actual
                    - point.steam_pressure_setpoint
                    for point in points
                ],
                "moisture": [
                    point.moisture_actual - point.moisture_setpoint
                    for point in points
                ],
                "ash": [
                    point.ash_actual - point.ash_setpoint for point in points
                ],
                "caliper": [
                    (point.caliper_actual or 0.0)
                    - (point.caliper_setpoint or 0.0)
                    for point in points
                ],
            }
        )

        relationships = []
        for column, display in self.KNOWN_PARAMETERS.items():
            strength, lag_points, p_value, support = self._best_lag(
                frame[column], frame["bw"]
            )
            if abs(strength) >= 0.28 and p_value < 0.05:
                relationships.append(
                    DiscoveredRelationship(
                        event_id=event_id,
                        source_parameter=display,
                        target_parameter="Basis Weight",
                        strength=float(strength),
                        lag_seconds=int(lag_points * 5),
                        is_interaction=False,
                        is_newly_discovered=False,
                        sample_note=(
                            f"Detrended lag relationship; n={support}, "
                            f"p={p_value:.3f}."
                        ),
                    )
                )

        # Both inputs are already deviations from their moving setpoints, so
        # their product is detrended while retaining a sustained compound
        # effect that first differences would erase.
        interaction = frame["filler"] * frame["steam"]
        strength, lag_points, p_value, support = self._best_level_lag(
            interaction, frame["bw"]
        )
        if abs(strength) >= 0.25 and p_value < 0.05:
            relationships.append(
                DiscoveredRelationship(
                    event_id=event_id,
                    source_parameter=(
                        "Filler Flow Ramp × Steam Pressure Slope"
                    ),
                    target_parameter="Basis Weight",
                    strength=float(strength),
                    lag_seconds=int(lag_points * 5),
                    is_interaction=True,
                    is_newly_discovered=True,
                    sample_note=(
                        "Compound relationship not present in the standard "
                        f"single-loop map; n={support}, p={p_value:.3f}."
                    ),
                )
            )

        relationships.sort(key=lambda item: abs(item.strength), reverse=True)
        # Persist only a complete-event analysis. Playback analyses remain
        # ephemeral and therefore cannot overwrite the event summary.
        if timestamp is None:
            db.query(DiscoveredRelationship).filter(
                DiscoveredRelationship.event_id == event_id
            ).delete()
            db.add_all(relationships)
            db.commit()
        return relationships

    @staticmethod
    def _best_lag(source: pd.Series, target: pd.Series):
        best = (0.0, 0, 1.0, 0)
        source_delta = source.diff()
        target_delta = target.diff()
        for lag in range(0, 13):
            aligned = pd.concat(
                [source_delta, target_delta.shift(-lag)], axis=1
            ).dropna()
            if len(aligned) < 24 or aligned.iloc[:, 0].nunique() < 3:
                continue
            strength, p_value = spearmanr(
                aligned.iloc[:, 0], aligned.iloc[:, 1]
            )
            if (
                np.isfinite(strength)
                and np.isfinite(p_value)
                and abs(strength) > abs(best[0])
            ):
                best = (float(strength), lag, float(p_value), len(aligned))
        return best

    @staticmethod
    def _best_level_lag(source: pd.Series, target: pd.Series):
        best = (0.0, 0, 1.0, 0)
        for lag in range(0, 13):
            aligned = pd.concat(
                [source, target.shift(-lag)], axis=1
            ).dropna()
            if len(aligned) < 24 or aligned.iloc[:, 0].nunique() < 3:
                continue
            strength, p_value = spearmanr(
                aligned.iloc[:, 0], aligned.iloc[:, 1]
            )
            if (
                np.isfinite(strength)
                and np.isfinite(p_value)
                and abs(strength) > abs(best[0])
            ):
                best = (float(strength), lag, float(p_value), len(aligned))
        return best


correlation_service = CorrelationService()
