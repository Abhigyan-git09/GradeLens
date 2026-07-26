from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import datetime
import uuid

from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now_naive():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

class GradeChangeEvent(Base):
    __tablename__ = "grade_change_events"

    event_id = Column(String, primary_key=True, default=generate_uuid)
    machine_id = Column(String, index=True)
    source_grade = Column(String)
    target_grade = Column(String)
    recipe_id = Column(String)
    start_time = Column(DateTime, default=utc_now_naive)
    end_time = Column(DateTime, nullable=True)
    bw_old_target = Column(Float)
    bw_new_target = Column(Float)
    stabilization_seconds = Column(Float, nullable=True)
    off_spec_seconds = Column(Float, nullable=True)
    max_deviation_pct = Column(Float, nullable=True)
    transition_outcome = Column(String, default="in_progress") # success, failure, in_progress

    timeseries = relationship("TimeseriesPoint", back_populates="event", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="event", cascade="all, delete-orphan")

class TimeseriesPoint(Base):
    __tablename__ = "timeseries_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now_naive, index=True)
    event_id = Column(String, ForeignKey("grade_change_events.event_id"), index=True)

    basis_weight_actual = Column(Float)
    basis_weight_setpoint = Column(Float)
    stock_flow_actual = Column(Float)
    stock_flow_setpoint = Column(Float)
    filler_flow_actual = Column(Float)
    filler_flow_setpoint = Column(Float)
    steam_pressure_actual = Column(Float)
    steam_pressure_setpoint = Column(Float)
    machine_speed_actual = Column(Float)
    machine_speed_setpoint = Column(Float)
    moisture_actual = Column(Float)
    moisture_setpoint = Column(Float)
    ash_actual = Column(Float)
    ash_setpoint = Column(Float)
    caliper_actual = Column(Float)
    caliper_setpoint = Column(Float)
    
    active_alarm_count = Column(Integer, default=0)
    scanner_quality_score = Column(Float, default=1.0)

    event = relationship("GradeChangeEvent", back_populates="timeseries")

class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(String, primary_key=True, default=generate_uuid)
    event_id = Column(String, ForeignKey("grade_change_events.event_id"), index=True)
    timestamp = Column(DateTime, default=utc_now_naive)
    
    parameter_name = Column(String)
    current_value = Column(Float)
    recommended_value = Column(Float)
    recommended_ramp_rate = Column(Float)
    
    risk_before = Column(Float)
    risk_after = Column(Float)
    stabilization_before = Column(Float)
    stabilization_after = Column(Float)
    
    confidence = Column(Float)
    rationale = Column(String)
    
    status = Column(String, default="pending") # pending, accepted, rejected, modified

    event = relationship("GradeChangeEvent", back_populates="recommendations")
    feedback = relationship("OperatorFeedback", back_populates="recommendation", uselist=False, cascade="all, delete-orphan")
    evidence_tags = relationship("EvidenceTag", back_populates="recommendation", cascade="all, delete-orphan")

class EvidenceTag(Base):
    __tablename__ = "evidence_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(String, ForeignKey("recommendations.recommendation_id"))
    tag = Column(String)
    source = Column(String)
    detail = Column(String)

    recommendation = relationship("Recommendation", back_populates="evidence_tags")

class OperatorFeedback(Base):
    __tablename__ = "operator_feedback"

    feedback_id = Column(String, primary_key=True, default=generate_uuid)
    recommendation_id = Column(String, ForeignKey("recommendations.recommendation_id"), unique=True)
    response = Column(String) # accept, reject, modify
    operator_selected_value = Column(Float, nullable=True)
    rejection_reason = Column(String, nullable=True)
    timestamp = Column(DateTime, default=utc_now_naive)

    recommendation = relationship("Recommendation", back_populates="feedback")

class RecipeConstraint(Base):
    __tablename__ = "recipe_constraints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grade_id = Column(String, index=True)
    parameter = Column(String)
    min_val = Column(Float)
    max_val = Column(Float)
    optimal_val = Column(Float)
    max_ramp_rate = Column(Float, nullable=True)

class DiscoveredRelationship(Base):
    __tablename__ = "discovered_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, index=True)
    source_parameter = Column(String)
    target_parameter = Column(String)
    strength = Column(Float)
    lag_seconds = Column(Integer)
    is_interaction = Column(Boolean)
    is_newly_discovered = Column(Boolean)
    sample_note = Column(String)
