import numpy as np
from typing import List, Dict, Any

# Canonical feature order — must match training in seed_demo.py and inference in risk_predictor/trajectory/stabilization
FEATURE_NAMES = [
    "bw_deviation",
    "bw_slope",
    "stock_flow_ramp",
    "machine_speed_ramp",
    "steam_pressure_slope",
    "filler_flow_ramp",
    "interaction_feature",
]

class FeatureService:
    @staticmethod
    def extract_features(points: List[Any]) -> Dict[str, float]:
        """
        Extracts machine learning features from a window of timeseries points.
        Assumes points are sorted in chronological order (oldest to newest).
        Requires at least 12 points (60 seconds at 5s intervals) for the
        interaction feature's 45s trailing window to work correctly.
        """
        if not points or len(points) < 12:
            return {
                "bw_deviation": 0.0,
                "bw_slope": 0.0,
                "stock_flow_ramp": 0.0,
                "machine_speed_ramp": 0.0,
                "steam_pressure_slope": 0.0,
                "filler_flow_ramp": 0.0,
                "interaction_feature": 0.0,
                "current_bw": 64.0,
            }

        latest = points[-1]

        # 1. Basis Weight Deviation (from setpoint)
        bw_deviation = latest.basis_weight_actual - latest.basis_weight_setpoint

        # 2. Basis Weight Slope (over last 5 points = 25 seconds)
        bw_slope = (latest.basis_weight_actual - points[-5].basis_weight_actual) / 25.0

        # 3. Stock Flow Ramp Rate (over last 5 points = 25 seconds)
        stock_flow_ramp = (latest.stock_flow_actual - points[-5].stock_flow_actual) / 25.0

        # 4. Machine Speed Ramp Rate (NEW — over last 5 points)
        machine_speed_ramp = (latest.machine_speed_actual - points[-5].machine_speed_actual) / 25.0

        # 5. Steam Pressure Slope (over last 5 points)
        steam_pressure_slope = (latest.steam_pressure_actual - points[-5].steam_pressure_actual) / 25.0

        # 6. Filler Flow Ramp Rate (NEW — over last 5 points)
        filler_flow_ramp = (latest.filler_flow_actual - points[-5].filler_flow_actual) / 25.0

        # 7. Interaction Feature: filler_flow_ramp * steam_pressure_slope
        #    ALIGNED WITH seed_demo.py's seeded definition:
        #    Both use a trailing window from point[i-1] to point[i-10] (45s span),
        #    measured at the same instant.  points[-1] to points[-10] = 9 intervals = 45s.
        interaction_filler = (points[-1].filler_flow_actual - points[-10].filler_flow_actual)
        interaction_steam = (points[-1].steam_pressure_actual - points[-10].steam_pressure_actual)
        interaction_feature = interaction_filler * interaction_steam

        return {
            "bw_deviation": bw_deviation,
            "bw_slope": bw_slope,
            "stock_flow_ramp": stock_flow_ramp,
            "machine_speed_ramp": machine_speed_ramp,
            "steam_pressure_slope": steam_pressure_slope,
            "filler_flow_ramp": filler_flow_ramp,
            "interaction_feature": interaction_feature,
            "current_bw": latest.basis_weight_actual,
        }

feature_service = FeatureService()
