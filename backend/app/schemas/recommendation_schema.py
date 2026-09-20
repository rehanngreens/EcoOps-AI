from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.score_schema import SustainabilityScore


class RecommendationStatus(str, Enum):
    """Outcome of one optimization run."""

    recommended = "recommended"
    no_recommendation = "no_recommendation"


class RecommendationItem(BaseModel):
    """One parameter change inside a recommendation set (design doc section 19)."""

    parameter: str
    current_value: str
    suggested_value: str
    reason: str


class EstimationTotals(BaseModel):
    """Estimated cost/energy/carbon totals for one configuration."""

    estimated_cost_usd: float = Field(..., ge=0)
    estimated_energy_kwh: float = Field(..., ge=0)
    estimated_carbon_kg_co2e: float = Field(..., ge=0)


class RecommendationTotals(BaseModel):
    """Baseline vs optimized totals with reductions."""

    baseline: EstimationTotals
    optimized: EstimationTotals
    cost_reduction_usd: float = Field(..., ge=0)
    energy_reduction_kwh: float = Field(..., ge=0)
    carbon_reduction_kg_co2e: float = Field(..., ge=0)


class RejectedCandidate(BaseModel):
    """A rejected candidate kept for transparency."""

    summary: str
    reason: str


class RecommendationSet(BaseModel):
    """Full result of one optimization run."""

    status: RecommendationStatus
    baseline_configuration: dict
    optimized_configuration: dict | None = None
    totals: RecommendationTotals | None = None
    items: list[RecommendationItem] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    explanation: str
    disclaimer: str


class OptimizationScores(BaseModel):
    """Sustainability score before and after the accepted recommendation.

    `optimized` is None when no candidate was accepted — the dashboard
    should then show only the baseline score.
    """

    baseline: SustainabilityScore
    optimized: SustainabilityScore | None = None
    improvement: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="optimized score minus baseline score; positive means the recommendation improves sustainability",
    )


class OptimizeResponse(BaseModel):
    analysis_id: str
    recommendation_set: RecommendationSet
    scores: OptimizationScores


class AnalysisRecommendationsResponse(BaseModel):
    analysis_id: str
    recommendation_set: RecommendationSet
    scores: OptimizationScores
