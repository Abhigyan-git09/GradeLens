import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from app.models.domain import TimeseriesPoint, GradeChangeEvent
from app.database import SessionLocal

class RiskPredictor:
    def __init__(self):
        self.model = KNeighborsClassifier(n_neighbors=3)
        self.is_trained = False
        self._train_model()

    def _train_model(self):
        """Train the model using historical Grade Change Events."""
        db = SessionLocal()
        events = db.query(GradeChangeEvent).all()
        
        X = []
        y = []
        
        for event in events:
            # Get latest 10 points for the event to form a feature vector
            points = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event.event_id).order_by(TimeseriesPoint.timestamp.desc()).limit(10).all()
            if len(points) < 10:
                continue
                
            # Feature engineering: we use basis weight deviation, stock flow, and steam pressure
            features = []
            for pt in points:
                features.extend([
                    pt.basis_weight_actual - pt.basis_weight_setpoint,
                    pt.stock_flow_actual,
                    pt.steam_pressure_actual
                ])
                
            X.append(features)
            # Label: 1 if failure, 0 otherwise
            y.append(1 if event.transition_outcome == "failure" else 0)
            
        db.close()
        
        if len(X) >= 2: # Need at least some samples to train
            # If we only have one class, KNN will throw an error, so ensure both exist or mock it
            if len(set(y)) < 2:
                # Mock a synthetic opposite class for training robustness in demo
                X.append([f * 1.1 for f in X[0]])
                y.append(1 - y[0])
            
            self.model.fit(X, y)
            self.is_trained = True

    def predict_risk(self, recent_points: list) -> dict:
        """
        Predict risk probability given recent TimeseriesPoints.
        Expects a list of the 10 most recent points.
        """
        if not self.is_trained or len(recent_points) < 10:
            # Fallback to a heuristic if model isn't trained or not enough data
            if not recent_points:
                return {"probability": 0.1, "direction": "none", "time_to_violation_seconds": None, "risk_level": "low"}
                
            latest = recent_points[0]
            dev = abs(latest.basis_weight_actual - latest.basis_weight_setpoint)
            prob = min(0.99, max(0.1, dev / 2.0))
            direction = "upper" if latest.basis_weight_actual > latest.basis_weight_setpoint else "lower"
            
            risk_level = "low"
            if prob > 0.75: risk_level = "critical"
            elif prob > 0.5: risk_level = "high"
            elif prob > 0.25: risk_level = "moderate"
            
            return {
                "probability": prob,
                "direction": direction,
                "time_to_violation_seconds": 120.0 if prob > 0.5 else None,
                "risk_level": risk_level
            }

        # Format features for the model
        features = []
        for pt in recent_points: # assume ordered desc
            features.extend([
                pt.basis_weight_actual - pt.basis_weight_setpoint,
                pt.stock_flow_actual,
                pt.steam_pressure_actual
            ])
            
        # Predict probability
        probs = self.model.predict_proba([features])[0]
        failure_prob = float(probs[1]) if len(probs) > 1 else 0.1
        
        # Determine direction based on latest point
        latest = recent_points[0]
        direction = "upper" if latest.basis_weight_actual > latest.basis_weight_setpoint else "lower"
        
        risk_level = "low"
        if failure_prob > 0.75: risk_level = "critical"
        elif failure_prob > 0.5: risk_level = "high"
        elif failure_prob > 0.25: risk_level = "moderate"
        
        time_to_violation = None
        if failure_prob > 0.5:
            # Rough heuristic for time to violation based on probability
            time_to_violation = max(30.0, 300.0 * (1.0 - failure_prob))
            
        return {
            "probability": failure_prob,
            "direction": direction,
            "time_to_violation_seconds": time_to_violation,
            "risk_level": risk_level
        }

# Singleton instance
risk_predictor_service = RiskPredictor()
