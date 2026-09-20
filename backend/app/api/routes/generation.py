"""Phase 17 Mode B API (design doc section 27, section 44.7).

POST /api/v1/generate                    -> run the full generation pipeline
GET  /api/v1/generation/{id}             -> replay a stored generation
GET  /api/v1/generation/{id}/configuration -> selected architecture summary
POST /api/v1/generation/{id}/optimize    -> re-run candidate evaluation/ranking

The infeasible path is an explicit 422 with per-check explanations — the
system never returns a constraint-violating configuration "as a best
effort". No artifact is ever executed; generation only renders text.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.generation_schema import (
    CandidateEvaluation,
    GeneratedArtifact,
    GenerationEvaluation,
    GenerationResult,
    ResourceRequirementsModel,
    TargetSelection,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.candidate_generator import GenerationPreferences
from app.services.generation.iac_generation_service import IaCGenerationError
from app.services.generation_service import (
    GenerationNotFoundError,
    create_generation,
    get_generation,
)
from app.services.prediction_service import (
    ModelArtifactsUnavailableError,
    ModelCompatibilityError,
)

router = APIRouter(prefix="/api/v1")


class GenerateRequest(BaseModel):
    """Mode B request body (section 4/44): workload + optional target."""

    workload: WorkloadProfile
    target: str | None = Field(
        default=None,
        description=(
            "'kubernetes' | 'terraform' | 'docker_compose' | "
            "'terraform+kubernetes' | 'auto'/None to let the rules choose"
        ),
    )
    preferences: GenerationPreferences | None = None


class GenerateResponse(BaseModel):
    """202-style creation response carrying the full replayable result."""

    generation_id: str
    status: str
    selected_configuration: object | None = None
    target_selection: TargetSelection
    requirements: ResourceRequirementsModel
    artifacts: list[GeneratedArtifact]
    evaluation: GenerationEvaluation


class GenerationResponse(BaseModel):
    generation_id: str
    status: str
    target_selection: TargetSelection
    requirements: ResourceRequirementsModel
    artifacts: list[GeneratedArtifact]
    evaluation: GenerationEvaluation


class GenerationConfigurationResponse(BaseModel):
    """Architecture summary for the result screen (section 44.7)."""

    generation_id: str
    status: str
    application: str | None = None
    source_type: str | None = None
    cpu_per_replica: float | None = None
    memory_per_replica_gb: float | None = None
    replicas: int | None = None
    storage_gb: float | None = None
    autoscaling_enabled: bool | None = None
    instance_type: str | None = None
    instance_count: int | None = None
    cloud_provider: str | None = None
    region: str | None = None


class GenerationOptimizeResponse(BaseModel):
    """Re-ranked evaluation for an existing generation."""

    generation_id: str
    status: str
    candidates: list[CandidateEvaluation]
    selected_index: int | None
    weights_used: dict[str, float]
    ranking_explanation: str
    infeasibility_explanation: str | None = None


def _generation_or_404(db: Session, generation_id: str) -> GenerationResult:
    try:
        return get_generation(db, generation_id)
    except GenerationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' was not found",
        ) from None


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
def generate(request: GenerateRequest, db: Session = Depends(get_db)):
    try:
        result = create_generation(db, request.workload, request.target, request.preferences)
    except ValueError as exc:
        # Invalid explicit target (target_selector raises ValueError).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ModelArtifactsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ModelCompatibilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except IaCGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IaC generation failed validation: {exc}",
        ) from exc

    evaluation = result.evaluation
    if evaluation.status == "infeasible":
        # Explicit, explained refusal (section 44.3): nothing violating the
        # constraints is returned as a best effort.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "generation_id": result.generation_id,
                "error": "infeasible",
                "explanation": evaluation.infeasibility_explanation,
            },
        )

    return GenerateResponse(
        generation_id=result.generation_id,
        status=evaluation.status,
        selected_configuration=result.selected_configuration,
        target_selection=result.target_selection,
        requirements=evaluation.requirements,
        artifacts=result.artifacts,
        evaluation=evaluation,
    )


@router.get("/generation/{generation_id}", response_model=GenerationResponse)
def get_generation_record(generation_id: str, db: Session = Depends(get_db)):
    result = _generation_or_404(db, generation_id)
    return GenerationResponse(
        generation_id=result.generation_id,
        status=result.evaluation.status,
        target_selection=result.target_selection,
        requirements=result.evaluation.requirements,
        artifacts=result.artifacts,
        evaluation=result.evaluation,
    )


@router.get(
    "/generation/{generation_id}/configuration",
    response_model=GenerationConfigurationResponse,
)
def get_generation_configuration(generation_id: str, db: Session = Depends(get_db)):
    result = _generation_or_404(db, generation_id)
    config = result.selected_configuration
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This generation has no selected configuration (infeasible)",
        )
    return GenerationConfigurationResponse(
        generation_id=result.generation_id,
        status=result.evaluation.status,
        application=config.application,
        source_type=config.source_type,
        cpu_per_replica=config.cpu_request,
        memory_per_replica_gb=config.memory_request_gb,
        replicas=config.replicas,
        storage_gb=config.storage_gb,
        autoscaling_enabled=config.autoscaling_enabled,
        instance_type=config.instance_type,
        instance_count=config.instance_count,
        cloud_provider=config.cloud_provider,
        region=config.region,
    )


@router.post(
    "/generation/{generation_id}/optimize",
    response_model=GenerationOptimizeResponse,
)
def optimize_generation(generation_id: str, db: Session = Depends(get_db)):
    """Re-run candidate evaluation/ranking with fresh priorities (same record id)."""
    stored = _generation_or_404(db, generation_id)
    workload = WorkloadProfile.model_validate(
        stored.evaluation.requirements.model_dump() and _stored_workload(db, generation_id)
    )
    try:
        reevaluated = create_generation(db, workload, stored.target_selection.target)
    except ModelArtifactsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    evaluation = reevaluated.evaluation
    return GenerationOptimizeResponse(
        generation_id=generation_id,
        status=evaluation.status,
        candidates=evaluation.candidates,
        selected_index=evaluation.selected_index,
        weights_used=evaluation.weights_used,
        ranking_explanation=evaluation.ranking_explanation,
        infeasibility_explanation=evaluation.infeasibility_explanation,
    )


def _stored_workload(db: Session, generation_id: str) -> dict:
    from app.models.generation import GenerationRecord

    record = db.get(GenerationRecord, generation_id)
    return (record.workload if record else {}) or {}
