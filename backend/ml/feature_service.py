import numpy as np
from typing import List, Dict, Any

class FeatureService:
    @staticmethod
    def extract_features(points: List[Any]) -> Dict[str, float]:
        """
        Extracts machine learning features from a window of timeseries points.
        Assumes points are sorted in chronological order (oldest to newest),
        with at least 10 points (which covers 50 seconds at 5s intervals).
        """
        if not points or len(points) < 10:
            # Return zeroed features if not enough history
            return {
                "bw_deviation": 0.0,
                "bw_slope": 0.0,
                "stock_flow_ramp": 0.0,
                "steam_pressure_slope": 0.0,
                "interaction_feature": 0.0,
                "current_bw": 64.0
            }

        latest = points[-1]
        
        # 1. Basis Weight Deviation
        bw_deviation = latest.basis_weight_actual - latest.basis_weight_setpoint
        
        # 2. Basis Weight Slope (over last 5 points = 25 seconds)
        bw_slope = (latest.basis_weight_actual - points[-5].basis_weight_actual) / 25.0
        
        # 3. Stock Flow Ramp Rate
        stock_flow_ramp = (latest.stock_flow_actual - points[-5].stock_flow_actual) / 25.0
        
        # 4. Novel Interaction Feature: filler_flow_ramp_rate * steam_pressure_slope(t-45s)
        # 45 seconds lag = 9 points back. We need slope AT t-45s, which means from t-55s to t-45s.
        # Let's approximate: 
        # filler_flow_ramp_rate (current)
        filler_ramp = (latest.filler_flow_actual - points[-3].filler_flow_actual) / 10.0
        
        # steam_pressure_slope (lagged by 45s). Since we have 10 points minimum:
        # points[-1] is t=0. points[-10] is t=-45s.
        # Let's take slope from t=-50s to t=-40s if we have enough points, otherwise just use what we have.
        if len(points) >= 12:
            steam_slope_lagged = (points[-9].steam_pressure_actual - points[-11].steam_pressure_actual) / 10.0
        else:
            steam_slope_lagged = (points[-9].steam_pressure_actual - points[-10].steam_pressure_actual) / 5.0
            
        interaction_feature = filler_ramp * steam_slope_lagged
        
        return {
            "bw_deviation": bw_deviation,
            "bw_slope": bw_slope,
            "stock_flow_ramp": stock_flow_ramp,
            "steam_pressure_slope": steam_slope_lagged,
            "interaction_feature": interaction_feature,
            "current_bw": latest.basis_weight_actual
        }

feature_service = FeatureService()
