"""Phase 17 generation orchestration (design doc sections 44, 27).

Wires the Phase 14-16 modules into the API contract: evaluate requirements
-> generate candidates -> evaluate -> rank -> select target -> render IaC
with round-trip validation -> persist everything (eligible AND rejected
candidates) -> return a replayable record. The infeasible path is a 422 at
the route layer, never a "best effort" violating configuration.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.generation import GenerationRecord, new_generation_id
from app.schemas.generation_schema import (
    GenerationEvaluation,
    GenerationResult,
    ResourceRequirementsModel,
    TargetSelection,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.evaluation_service import evaluate_generation
from app.services.generation.iac_generation_service import (
    IaCGenerationError,
    build_generation_result,
)
from app.services.generation.requirement_engine import estimate_requirements
from app.services.generation.target_selector import select_target
from app.services.generation.candidate_generator import GenerationPreferences


class GenerationNotFoundError(LookupError):
    pass


def _record_to_result(record: GenerationRecord) -> GenerationResult:
    """Rebuild the API response from a stored row without re-running the pipeline."""
    from app.schemas.generation_schema import GeneratedArtifact

    artifacts = (
        [GeneratedArtifact.model_validate(item) for item in record.artifacts or []]
    )
    return GenerationResult(
        generation_id=record.id,
        evaluation=GenerationEvaluation.model_validate(record.evaluation),
        target_selection=TargetSelection(
            target=record.target,
            source=record.target_source,
            explanation=record.target_explanation,
        ),
        artifacts=artifacts,
        selected_configuration=(
            # Absent for infeasible generations.
            _config_from_json(record.selected_configuration)
            if record.selected_configuration
            else None
        ) or _first_candidate_configuration(record),
        disclaimer=record.disclaimer,
    )


def _config_from_json(payload: dict):
    from app.schemas.infrastructure_schema import InfrastructureConfiguration

    return InfrastructureConfiguration.model_validate(payload)


def _first_candidate_configuration(record: GenerationRecord):
    candidates = (record.evaluation or {}).get("candidates") or []
    if not candidates:
        return None
    return _config_from_json(candidates[0]["plan"]["configuration"])


def create_generation(
    db: Session,
    workload: WorkloadProfile,
    requested_target: str | None,
    preferences: GenerationPreferences | None = None,
) -> GenerationResult:
    """Full Mode B pipeline: evaluate, select, render, persist."""
    evaluation = evaluate_generation(workload, preferences=preferences)
    target_selection = select_target(requested_target, workload)

    if evaluation.status == "infeasible":
        result = GenerationResult(
            generation_id=new_generation_id(),
            evaluation=evaluation,
            target_selection=target_selection,
            artifacts=[],
            selected_configuration=_first_candidate_config_from_evaluation(evaluation),
            disclaimer=evaluation.disclaimer,
        )
    else:
        # A template/round-trip failure is a server fault by design
        # (section 44.6); the route maps IaCGenerationError to a 500.
        result = build_generation_result(evaluation, target_selection)

    record = GenerationRecord(
        id=result.generation_id,
        status=result.evaluation.status,
        workload=workload.model_dump(),
        requirements=result.evaluation.requirements.model_dump(),
        target=target_selection.target,
        target_source=target_selection.source,
        target_explanation=target_selection.explanation,
        evaluation=evaluation.model_dump(),
        artifacts=[artifact.model_dump() for artifact in result.artifacts] or None,
        selected_configuration=(
            result.selected_configuration.model_dump()
            if result.selected_configuration
            else None
        ),
        disclaimer=result.disclaimer,
    )
    db.add(record)
    db.commit()
    return result


def _first_candidate_config_from_evaluation(evaluation: GenerationEvaluation):
    if not evaluation.candidates:
        return None
    return evaluation.candidates[0].plan.configuration


def get_generation(db: Session, generation_id: str) -> GenerationResult:
    record = db.get(GenerationRecord, generation_id)
    if record is None:
        raise GenerationNotFoundError(generation_id)
    return _record_to_result(record)


def get_generation_requirements(db: Session, generation_id: str) -> ResourceRequirementsModel:
    record = db.get(GenerationRecord, generation_id)
    if record is None:
        raise GenerationNotFoundError(generation_id)
    return ResourceRequirementsModel.model_validate(record.requirements)
