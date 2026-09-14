"""Sustainability score (design doc section 23).

Composite score = weighted mean of five normalized components:

- resource efficiency: predicted CPU utilization — the share of provisioned
  CPU capacity actually doing work.
- energy efficiency: predicted active energy share = active vCPUs/GB weighted
  demand over total provisioned demand capacity (the utilizable part of the
  energy footprint; idle waste reduces it).
- carbon impact: same active-share principle applied to the carbon footprint.
- cost efficiency: share of provisioned cost backed by predicted active
  demand (cost is billed while provisioned, so idle capacity is pure waste).
- constraint compliance: share of the five Phase 8 checks that pass.

All four footprint components therefore measure *productive share of a
provisioned footprint* — rewarding right-sizing (smaller allocation, same
work) and penalizing idle waste — so the composite is coherent: every
component moves the same direction. Every curve, bound, and weight is
disclosed in the response, per the design doc's rule that the methodology
must be clearly defined and never presented as scientifically accurate.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.score_schema import ScoreComponent, SustainabilityScore
from app.schemas.unified_schema import (
    ConstraintEvaluation,
    FeatureVector,
    SustainabilityEstimation,
    UtilizationPrediction,
)
from app.services import estimation_service
from app.services.feature_service import extract_features
from app.schemas.workload_schema import WorkloadProfile

METHODOLOGY = (
    "Weighted mean of five normalized components (resource efficiency, energy "
    "efficiency, carbon impact, cost efficiency, constraint compliance). "
    "Resource efficiency is predicted CPU utilization. Energy, carbon, and "
    "cost components each measure the productive share of their provisioned "
    "footprint (predicted active demand over provisioned capacity). "
    "Constraint compliance is the fraction of checks passed. Weights are "
    "configurable prototype defaults, not scientifically calibrated values."
)

DISCLAIMER = (
    "Prototype heuristic score. It is a transparent weighted average of "
    "configurable normalized metrics and is not a scientifically validated "
    "or industrially benchmarked sustainability measure."
)

GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
    (0.0, "F"),
)


@dataclass(frozen=True)
class ScoreWeights:
    resource_efficiency: float
    energy_efficiency: float
    carbon_impact: float
    cost_efficiency: float
    constraint_compliance: float

    def normalized(self) -> "ScoreWeights":
        total = (
            self.resource_efficiency
            + self.energy_efficiency
            + self.carbon_impact
            + self.cost_efficiency
            + self.constraint_compliance
        )
        if total <= 0:
            raise ValueError("at least one score weight must be positive")
        if abs(total - 1.0) < 1e-9:
            return self
        return ScoreWeights(
            resource_efficiency=self.resource_efficiency / total,
            energy_efficiency=self.energy_efficiency / total,
            carbon_impact=self.carbon_impact / total,
            cost_efficiency=self.cost_efficiency / total,
            constraint_compliance=self.constraint_compliance / total,
        )


def weights_from_settings(settings: Settings | None = None) -> ScoreWeights:
    values = settings or get_settings()
    return ScoreWeights(
        resource_efficiency=values.score_weight_resource_efficiency,
        energy_efficiency=values.score_weight_energy_efficiency,
        carbon_impact=values.score_weight_carbon_impact,
        cost_efficiency=values.score_weight_cost_efficiency,
        constraint_compliance=values.score_weight_constraint_compliance,
    ).normalized()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _grade(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def _active_share(
    active: float,
    total: float,
) -> float:
    """Productive share of a provisioned footprint: 0 (all waste) to 1 (fully used).

    The active and total quantities are in the same units (vCPU-hours,
    GB-hours, watt-hours...), so the ratio is dimensionless. A degenerate
    scale (total 0) cannot discriminate and scores 0 rather than overrating.
    """
    if total <= 0:
        return 0.0
    return _clamp01(active / total)


def compute_score(
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
    features: FeatureVector,
    prediction: UtilizationPrediction,
    estimation: SustainabilityEstimation,
    constraints: ConstraintEvaluation,
    weights: ScoreWeights | None = None,
    settings: Settings | None = None,
) -> SustainabilityScore:
    """Compute the composite score with full methodology disclosure."""
    settings = settings or get_settings()
    weights = (weights or weights_from_settings(settings)).normalized()

    total_checks = len(constraints.checks) or 1
    constraint_score = (
        sum(1 for check in constraints.checks if check.status.value == "pass")
        / total_checks
    )

    # Energy and carbon are utilization-proportional in the Phase 7 model, so
    # their productive share is the active-demand share of provisioned
    # capacity (the same ratio that produced the estimate, made explicit).
    # Cost is allocation-proportional, so its productive share compares
    # estimated active cost against total provisioned cost.
    provisioned_cost = estimation.assumptions.period_hours * (
        features.total_cpu_capacity * settings.cpu_cost_per_vcpu_hour_usd
        + features.total_memory_capacity * settings.memory_cost_per_gb_hour_usd
    )
    active_cost = estimation.assumptions.period_hours * (
        estimation.active_cpu_vcpus * settings.cpu_cost_per_vcpu_hour_usd
        + estimation.active_memory_gb * settings.memory_cost_per_gb_hour_usd
    )

    resource_component = ScoreComponent(
        name="resource_efficiency",
        raw_value=f"predicted cpu utilization {prediction.cpu_utilization:.1%}",
        score=_clamp01(prediction.cpu_utilization),
        weight=weights.resource_efficiency,
        explanation=(
            "Fraction of provisioned CPU capacity predicted to be active. "
            "Higher utilization of the same allocation means less waste."
        ),
    )
    energy_component = ScoreComponent(
        name="energy_efficiency",
        raw_value=f"{estimation.estimated_energy_kwh:.2f} kWh/period",
        score=_active_share(
            estimation.active_cpu_vcpus * settings.cpu_power_watts_per_active_vcpu
            + estimation.active_memory_gb * settings.memory_power_watts_per_active_gb,
            features.total_cpu_capacity * settings.cpu_power_watts_per_active_vcpu
            + features.total_memory_capacity * settings.memory_power_watts_per_active_gb,
        ),
        weight=weights.energy_efficiency,
        explanation=(
            "Predicted active energy demand as a share of the provisioned "
            "energy capacity for this deployment shape; idle provisioned "
            "capacity is wasted energy headroom."
        ),
    )
    carbon_component = ScoreComponent(
        name="carbon_impact",
        raw_value=f"{estimation.estimated_carbon_kg_co2e:.2f} kgCO2e/period",
        score=_active_share(
            estimation.active_cpu_vcpus * settings.cpu_power_watts_per_active_vcpu
            + estimation.active_memory_gb * settings.memory_power_watts_per_active_gb,
            features.total_cpu_capacity * settings.cpu_power_watts_per_active_vcpu
            + features.total_memory_capacity * settings.memory_power_watts_per_active_gb,
        ),
        weight=weights.carbon_impact,
        explanation=(
            "Productive share of the carbon footprint: predicted active "
            "demand over provisioned capacity at the configured carbon "
            "intensity. Right-sizing cuts the footprint without cutting work."
        ),
    )
    cost_component = ScoreComponent(
        name="cost_efficiency",
        raw_value=f"${estimation.estimated_cost_usd:.2f}/period",
        score=_active_share(active_cost, provisioned_cost),
        weight=weights.cost_efficiency,
        explanation=(
            "Share of provisioned cost backed by predicted active demand. "
            "Cost is billed while provisioned, so a mostly-idle deployment "
            "wastes most of what it pays for."
        ),
    )
    constraint_component = ScoreComponent(
        name="constraint_compliance",
        raw_value=(
            f"{sum(1 for c in constraints.checks if c.status.value == 'pass')}"
            f"/{len(constraints.checks)} checks passed"
        ),
        score=constraint_score,
        weight=weights.constraint_compliance,
        explanation=(
            "Fraction of the five feasibility checks (headroom, latency, "
            "availability, user capacity, autoscaling coverage) satisfied."
        ),
    )

    components = [
        resource_component,
        energy_component,
        carbon_component,
        cost_component,
        constraint_component,
    ]
    composite = sum(component.score * component.weight for component in components)

    return SustainabilityScore(
        score=round(_clamp01(composite), 4),
        grade=_grade(_clamp01(composite)),
        components=components,
        methodology=METHODOLOGY,
        disclaimer=DISCLAIMER,
    )
