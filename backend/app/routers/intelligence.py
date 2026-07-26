"""Evidence, data-control, scenario, and explanation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import RecipeConstraint
from app.schemas.domain import (
    DataOverviewSchema,
    DataValidationRequestSchema,
    DataValidationResponseSchema,
    ExplanationRequestSchema,
    ExplanationResponseSchema,
    RecipeConstraintSchema,
    ScenarioRequestSchema,
    ScenarioResultSchema,
)
from app.services.counterfactual_service import counterfactual_service
from app.services.data_intelligence_service import data_intelligence_service
from app.services.explanation_service import explanation_service

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.get("/data/overview", response_model=DataOverviewSchema)
def get_data_overview(db: Session = Depends(get_db)):
    return data_intelligence_service.overview(db)


@router.post(
    "/data/validate",
    response_model=DataValidationResponseSchema,
)
def validate_data(request: DataValidationRequestSchema):
    return data_intelligence_service.validate_upload(
        request.file_name, request.columns, request.rows
    )


@router.get(
    "/recipes/{grade_id}",
    response_model=list[RecipeConstraintSchema],
)
def get_recipe_constraints(
    grade_id: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(RecipeConstraint)
        .filter(RecipeConstraint.grade_id == grade_id)
        .order_by(RecipeConstraint.parameter)
        .all()
    )


@router.post("/scenarios/run", response_model=ScenarioResultSchema)
def run_scenario(
    request: ScenarioRequestSchema,
    db: Session = Depends(get_db),
):
    result = counterfactual_service.simulate_scenario(
        request.event_id,
        request.timestamp,
        [item.model_dump() for item in request.adjustments],
        db,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Scenario requires one to four unique supported parameters "
                "and a complete 60-second history window."
            ),
        )
    return result


@router.post("/explain", response_model=ExplanationResponseSchema)
def explain_state(
    request: ExplanationRequestSchema,
    db: Session = Depends(get_db),
):
    result = explanation_service.explain(
        request.event_id,
        request.timestamp,
        db,
        recommendation_id=request.recommendation_id,
        prefer_llm=request.prefer_llm,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "A complete 60-second history window is required before "
                "the current state can be explained."
            ),
        )
    return result
