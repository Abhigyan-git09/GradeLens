import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

class TrajectoryForecaster:
    def __init__(self):
        # We use a degree 2 polynomial for smooth curves
        self.poly = PolynomialFeatures(degree=2)
        
    def forecast(self, recent_points: list, horizons_sec: list = [30, 60, 120, 300]) -> dict:
        """
        Given the most recent timeseries points, forecast future basis weight.
        Uses polynomial regression over the recent time window.
        """
        if len(recent_points) < 5:
            # Not enough data, return flat forecast based on current setpoint
            latest_sp = recent_points[0].basis_weight_setpoint if recent_points else 64.0
            return {
                "horizons": [
                    {"seconds": s, "predicted_bw": latest_sp, "lower_bound": latest_sp - 0.5, "upper_bound": latest_sp + 0.5}
                    for s in horizons_sec
                ]
            }
            
        # Extract features (time relative to latest) and target (basis weight)
        # Assuming points are sorted descending by timestamp
        latest_time = recent_points[0].timestamp.timestamp()
        
        X = []
        y = []
        
        for pt in recent_points:
            t = pt.timestamp.timestamp() - latest_time # Will be <= 0
            X.append([t])
            y.append(pt.basis_weight_actual)
            
        # Fit polynomial regression
        X_poly = self.poly.fit_transform(X)
        model = LinearRegression()
        model.fit(X_poly, y)
        
        # Predict for future horizons
        results = []
        for s in horizons_sec:
            x_future = self.poly.transform([[s]])
            pred_bw = float(model.predict(x_future)[0])
            
            # Estimate confidence bounds (widens over time)
            uncertainty = 0.2 + (s / 100.0) * 0.5
            
            results.append({
                "seconds": s,
                "predicted_bw": round(pred_bw, 2),
                "lower_bound": round(pred_bw - uncertainty, 2),
                "upper_bound": round(pred_bw + uncertainty, 2)
            })
            
        return {"horizons": results}

# Singleton instance
trajectory_forecaster_service = TrajectoryForecaster()
