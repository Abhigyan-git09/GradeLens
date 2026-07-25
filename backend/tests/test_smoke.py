import os
import sys

# Add backend dir to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from ml.risk_predictor import risk_predictor_service
from ml.stabilization_service import stabilization_service
from app.services.recommendation_engine import recommendation_engine
from app.services.correlation_service import correlation_service
from app.services.rootcause_service import rootcause_service

def test_risk_math():
    print("Testing Risk Math (LightGBM)...")
    # Synthetic feature vector
    features = {
        "bw_deviation": 1.2,
        "bw_slope": 0.05,
        "stock_flow_ramp": 2.0,
        "interaction_feature": 1.5,
        "current_bw": 65.2
    }
    res = risk_predictor_service.predict_risk(features)
    assert "probability" in res, "Missing probability"
    assert 0.0 <= res["probability"] <= 1.0, "Probability out of bounds"
    print("[OK] Risk Predictor OK")

def test_constraint_validation():
    print("Testing Constraint Validation (Recommendation Engine)...")
    db = SessionLocal()
    # Try generating a recommendation for the demo event
    rec = recommendation_engine.generate("EVT-003-RECOVERABLE", db)
    
    if rec:
        # Verify it respects constraints (G-200 stock flow: min 950, max 1100)
        if rec.parameter_name == "Stock Flow":
            assert 950.0 <= rec.recommended_value <= 1100.0, "Recommendation violated recipe constraints!"
    db.close()
    print("[OK] Constraint Validation OK")
    
def test_correlation_discovery():
    print("Testing Correlation Discovery...")
    db = SessionLocal()
    correlation_service.discover_relationships("EVT-003-RECOVERABLE", db)
    db.close()
    print("[OK] Correlation Discovery OK")

def test_root_cause():
    print("Testing Root Cause Engine...")
    db = SessionLocal()
    causes = rootcause_service.get_root_causes("EVT-003-RECOVERABLE", db)
    if causes:
        # Ensure percentages sum close to 1.0
        total = sum(c.contribution_pct for c in causes)
        assert 0.95 <= total <= 1.05, "Contributions do not sum to ~100%"
    db.close()
    print("[OK] Root Cause Engine OK")

if __name__ == "__main__":
    init_db()
    test_risk_math()
    test_constraint_validation()
    test_correlation_discovery()
    test_root_cause()
    print("All smoke tests passed successfully!")
