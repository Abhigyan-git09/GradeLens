import pandas as pd
from typing import List
from sqlalchemy.orm import Session
from app.models.domain import TimeseriesPoint, DiscoveredRelationship
from ml.feature_service import feature_service

class CorrelationService:
    def discover_relationships(self, event_id: str, db: Session):
        pts = db.query(TimeseriesPoint).filter(TimeseriesPoint.event_id == event_id).order_by(TimeseriesPoint.timestamp.asc()).all()
        if len(pts) < 20:
            return
            
        # Convert to pandas for fast vectorized correlation
        data = []
        for p in pts:
            data.append({
                "timestamp": p.timestamp,
                "bw": p.basis_weight_actual,
                "stock": p.stock_flow_actual,
                "filler": p.filler_flow_actual,
                "steam": p.steam_pressure_actual,
                "speed": p.machine_speed_actual
            })
        
        df = pd.DataFrame(data)
        
        # Calculate lagged slopes to find the interaction
        # We need slope of steam over 9 points (45s) and ramp of filler over 9 points
        # But for simpler correlation discovery, we look at the interaction feature vs Basis Weight
        
        # 1. Discover basic correlations (0s lag)
        corr_matrix = df[['bw', 'stock', 'speed', 'filler', 'steam']].corr(method='spearman')
        
        relationships = []
        
        # Basic Stock Flow vs BW
        if abs(corr_matrix.loc['stock', 'bw']) > 0.25:
            relationships.append(DiscoveredRelationship(
                source_parameter="Stock Flow",
                target_parameter="Basis Weight",
                strength=float(corr_matrix.loc['stock', 'bw']),
                lag_seconds=15, # Hardcoded known physics lag
                is_interaction=False,
                is_newly_discovered=False,
                sample_note="Standard primary control relationship."
            ))
            
        # Basic Speed vs BW
        if abs(corr_matrix.loc['speed', 'bw']) > 0.25:
            relationships.append(DiscoveredRelationship(
                source_parameter="Machine Speed",
                target_parameter="Basis Weight",
                strength=float(corr_matrix.loc['speed', 'bw']),
                lag_seconds=5,
                is_interaction=False,
                is_newly_discovered=False,
                sample_note="Standard primary control relationship."
            ))
            
        # 2. Discover the hidden 45s lagged interaction
        # We slide a window and calculate the interaction feature from feature_service
        interaction_vals = []
        bw_future_vals = []
        
        for i in range(12, len(pts) - 10):
            window = pts[i-12:i]
            features = feature_service.extract_features(window)
            interaction_vals.append(features["interaction_feature"])
            
            # Future basis weight deviation
            future_bw_dev = pts[i+6].basis_weight_actual - pts[i+6].basis_weight_setpoint
            bw_future_vals.append(future_bw_dev)
            
        # Correlate the interaction feature with future BW deviation
        if len(interaction_vals) > 0:
            df_int = pd.DataFrame({"interaction": interaction_vals, "future_bw": bw_future_vals})
            int_corr = df_int['interaction'].corr(df_int['future_bw'])
            
            # Seeded interaction effect pushes BW in the same direction as the product,
            # so the correlation must be positive (not just abs > 0.4)
            if pd.notna(int_corr) and int_corr > 0.4:
                relationships.append(DiscoveredRelationship(
                    source_parameter="Filler Flow Ramp x Steam Pressure Slope",
                    target_parameter="Basis Weight",
                    strength=float(int_corr),
                    lag_seconds=45,
                    is_interaction=True,
                    is_newly_discovered=True,
                    sample_note="Compound anomaly: Filler flow changes are amplifying steam pressure fluctuations after a 45s lag."
                ))
                
        # Persist to DB
        if relationships:
            db.query(DiscoveredRelationship).filter(DiscoveredRelationship.event_id == event_id).delete()
            for r in relationships:
                r.event_id = event_id
            db.add_all(relationships)
            db.commit()

correlation_service = CorrelationService()
