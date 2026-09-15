"""Mode B generation schemas (design doc sections 44.2-44.3, 44.5).

Phase 15 introduces the candidate/evaluation contracts as Pydantic models
so they are directly serializable for the Phase 17 API responses. The
Phase 14 engine keeps its frozen dataclass internally; a conversion helper
bridges the two.
"""

from pydantic import BaseModel, Field

from app.schemas.constraint_schema import ConstraintEvaluation
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.score_schema import SustainabilityScore
from app.schemas.unified_schema import SustainabilityEstimation, UtilizationPrediction

GenerationStatus = str  # "recommended" | "infeasible" (values documented below)


class ResourceRequirementsModel(BaseModel):
    """Serializable mirror of the Phase 14 engine's ResourceRequirements."""

    cpu_cores: float = Field(..., gt=0)
    memory_gb: float = Field(..., gt=0)
    replica_estimate: int = Field(..., ge=1)
    replica_minimum: int = Field(..., ge=1)
    storage_gb: float | None = None
    autoscaling_required: bool
    peak_factor: float = Field(..., ge=1.0)
    notes: list[str] = Field(default_factory=list)


class CandidatePlan(BaseModel):
    """One concrete candidate configuration with a human-readable rationale."""

    variant: str
    summary: str
    configuration: InfrastructureConfiguration


class CandidateEvaluation(BaseModel):
    """The full pipeline result for one candidate (kept even when rejected)."""

    plan: CandidatePlan
    prediction: UtilizationPrediction
    estimation: SustainabilityEstimation
    constraints: ConstraintEvaluation
    score: SustainabilityScore
    eligible: bool
    rejection_reasons: list[str] = Field(default_factory=list)


class GenerationEvaluation(BaseModel):
    """Complete Mode B generation result (pre-IaC; rendering is Phase 16).

    status is "recommended" when at least one eligible candidate exists
    (selected_index points into candidates) or "infeasible" when every
    candidate failed an important constraint (selected_index is None and
    infeasibility_explanation says which constraints failed and why).
    """

    status: GenerationStatus
    requirements: ResourceRequirementsModel
    candidates: list[CandidateEvaluation]
    selected_index: int | None = None
    weights_used: dict[str, float]
    ranking_explanation: str
    infeasibility_explanation: str | None = None
    disclaimer: str
