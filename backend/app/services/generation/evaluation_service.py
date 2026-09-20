"""Phase 15 candidate evaluation and ranking (design doc sections 44.3, 44.5).

REUSE, not reimplementation: every candidate flows the EXISTING Mode A
pipeline — feature extraction, ML utilization prediction, energy/carbon/cost
estimation, the Phase 8 constraint engine, and the Phase 11 weighted
sustainability score. The only new logic here is:

- priority-derived score weights (section 44.5) built from the user's
  performance/cost/sustainability priorities via the existing configurable
  ScoreWeights mechanism, normalized and fully disclosed;
- eligibility gating: any failed important check makes a candidate
  ineligible regardless of score;
- deterministic ranking: score, then cost, energy, CPU as tie-breaks;
- the all-rejected path: status "infeasible" with per-check explanations —
  never a constraint-violating configuration "as a best effort".

The user's latency/availability/users/traffic requirements reach the Phase 8
checks through the workload side exactly as in Mode A (they are inputs to
feature extraction and the checks), so there is no second constraint engine.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.schemas.constraint_schema import ConstraintStatus
from app.schemas.generation_schema import (
    CandidateEvaluation,
    CandidatePlan,
    GenerationEvaluation,
    ResourceRequirementsModel,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services import (
    constraint_service,
    estimation_service,
    feature_service,
    prediction_service,
    score_service,
)
from app.services.generation.candidate_generator import (
    GenerationPreferences,
    requirements_from_estimate,
)
from app.services.generation.requirement_engine import (
    ResourceRequirements,
    estimate_requirements,
)

# Priority -> score-component multiplier (section 44.5). Documented starting
# values; applied to the settings-derived base weights and normalized, so
# the exact weights used are always computable and disclosable.
PRIORITY_MULTIPLIERS: dict[str, float] = {"low": 0.75, "medium": 1.0, "high": 1.5}

# Which score components each user priority tunes. Performance raises the
# utilization/compliance components; cost raises cost_efficiency;
# sustainability raises the energy/carbon components.
_PRIORITY_COMPONENTS: dict[str, tuple[str, ...]] = {
    "performance": ("resource_efficiency", "constraint_compliance"),
    "cost": ("cost_efficiency",),
    "sustainability": ("energy_efficiency", "carbon_impact"),
}

DISCLAIMER = (
    "All predictions, estimates, and scores are prototype heuristics, not "
    "measurements or guarantees. Candidates are advisory: nothing is "
    "deployed, and EcoOps AI never claims universally optimal infrastructure."
)


def weights_for_priorities(
    workload: WorkloadProfile,
    settings: Settings | None = None,
) -> dict[str, float]:
    """Priority-derived score weights (section 44.5), normalized, disclosed.

    Starts from the configurable base weights (Settings), multiplies the
    mapped components by the priority multipliers, and normalizes with the
    same ScoreWeights.normalized() used by the Mode A score endpoint.
    """
    base = score_service.weights_from_settings(settings)
    values = {
        "resource_efficiency": base.resource_efficiency,
        "energy_efficiency": base.energy_efficiency,
        "carbon_impact": base.carbon_impact,
        "cost_efficiency": base.cost_efficiency,
        "constraint_compliance": base.constraint_compliance,
    }
    for priority_attr, components in _PRIORITY_COMPONENTS.items():
        multiplier = PRIORITY_MULTIPLIERS[getattr(workload, f"{priority_attr}_priority")]
        for component in components:
            values[component] *= multiplier

    normalized = score_service.ScoreWeights(**values).normalized()
    return {
        "resource_efficiency": normalized.resource_efficiency,
        "energy_efficiency": normalized.energy_efficiency,
        "carbon_impact": normalized.carbon_impact,
        "cost_efficiency": normalized.cost_efficiency,
        "constraint_compliance": normalized.constraint_compliance,
    }


def evaluate_candidate(
    plan: CandidatePlan,
    workload: WorkloadProfile,
    weights: dict[str, float],
    settings: Settings | None = None,
) -> CandidateEvaluation:
    """Run one candidate through the existing Mode A pipeline (section 44.3)."""
    settings = settings or get_settings()
    configuration = plan.configuration

    features = feature_service.extract_features(configuration, workload)
    prediction = prediction_service.predict_utilization(features)
    estimation = estimation_service.estimate_sustainability(features, prediction)
    constraints = constraint_service.evaluate_constraints(features, prediction)
    score = score_service.compute_score(
        configuration,
        workload,
        features,
        prediction,
        estimation,
        constraints,
        weights=score_service.ScoreWeights(**weights),
        settings=settings,
    )

    reasons = [
        f"{check.name}: {check.explanation}"
        for check in constraints.checks
        if check.status is not ConstraintStatus.pass_
    ]
    return CandidateEvaluation(
        plan=plan,
        prediction=prediction,
        estimation=estimation,
        constraints=constraints,
        score=score,
        eligible=not reasons,
        rejection_reasons=reasons,
    )


def _ranking_key(evaluation: CandidateEvaluation) -> tuple:
    """Ranking objective: score desc, then cost/energy/CPU asc (section 44.5)."""
    return (
        -evaluation.score.score,
        evaluation.estimation.estimated_cost_usd,
        evaluation.estimation.estimated_energy_kwh,
        evaluation.plan.configuration.cpu_request or 0.0,
    )


def _infeasibility_explanation(rejected: list[CandidateEvaluation]) -> str:
    failed_names = sorted(
        {reason.split(":", 1)[0] for evaluation in rejected for reason in evaluation.rejection_reasons}
    )
    lines = [
        "No candidate satisfied all important constraints, so nothing was "
        "recommended (EcoOps AI does not return constraint-violating "
        "configurations as a best effort). Constraints that failed: "
        + ", ".join(failed_names)
        + ".",
        "Per-candidate reasons:",
    ]
    for evaluation in rejected:
        lines.append(f"- {evaluation.plan.variant} ({evaluation.plan.summary})")
        for reason in evaluation.rejection_reasons:
            lines.append(f"    * {reason}")
    lines.append(
        "Consider relaxing the requirements (latency, availability, users, "
        "or traffic) and retrying."
    )
    return "\n".join(lines)


def _ranking_explanation(
    ranked: list[CandidateEvaluation],
    weights: dict[str, float],
    tie_breaks: list[str],
) -> str:
    winner = ranked[0]
    parts = [
        f"Selected the '{winner.plan.variant}' candidate with score "
        f"{winner.score.score:.4f} ({winner.score.grade}).",
        "Ranking used the disclosed weights "
        + ", ".join(f"{name}={value:.3f}" for name, value in weights.items())
        + " derived from the stated priorities (section 44.5).",
    ]
    if tie_breaks:
        parts.append("Tie-breaks applied: " + "; ".join(tie_breaks) + ".")
    else:
        parts.append("No tie-breaks were needed.")
    if len(ranked) > 1:
        parts.append(
            "Runner-up: '" + ranked[1].plan.variant + "' at score "
            f"{ranked[1].score.score:.4f}."
        )
    rejected = [e for e in ranked if not e.eligible]
    if rejected:
        parts.append(
            f"{len(rejected)} candidate(s) were ineligible (failed checks): "
            + ", ".join(e.plan.variant for e in rejected)
            + "."
        )
    return " ".join(parts)


def evaluate_generation(
    workload: WorkloadProfile,
    requirements: ResourceRequirements | ResourceRequirementsModel | None = None,
    preferences: GenerationPreferences | None = None,
    settings: Settings | None = None,
) -> GenerationEvaluation:
    """Generate candidates, evaluate each, gate, rank, and select (44.2-44.3, 44.5)."""
    settings = settings or get_settings()
    del preferences  # consumed by Phase 16 target selection; reserved here for symmetry

    if requirements is None:
        estimate = estimate_requirements(workload)
    elif isinstance(requirements, ResourceRequirementsModel):
        estimate = ResourceRequirements(
            cpu_cores=requirements.cpu_cores,
            memory_gb=requirements.memory_gb,
            replica_estimate=requirements.replica_estimate,
            replica_minimum=requirements.replica_minimum,
            storage_gb=requirements.storage_gb,
            autoscaling_required=requirements.autoscaling_required,
            peak_factor=requirements.peak_factor,
            notes=list(requirements.notes),
        )
    else:
        estimate = requirements

    # Import here to avoid a circular import at module load.
    from app.services.generation.candidate_generator import generate_candidates

    plans = generate_candidates(workload, estimate)
    weights = weights_for_priorities(workload, settings)

    evaluations = [evaluate_candidate(plan, workload, weights, settings) for plan in plans]
    eligible = sorted((e for e in evaluations if e.eligible), key=_ranking_key)
    rejected = [e for e in evaluations if not e.eligible]

    if not eligible:
        return GenerationEvaluation(
            status="infeasible",
            requirements=requirements_from_estimate(estimate),
            candidates=evaluations,
            selected_index=None,
            weights_used=weights,
            ranking_explanation=(
                "No ranking was performed: every candidate failed at least "
                "one important constraint."
            ),
            infeasibility_explanation=_infeasibility_explanation(rejected),
            disclaimer=DISCLAIMER,
        )

    # Deterministic order: ranked eligible first (in rank order), then
    # rejected candidates in their original generation order.
    ordered = eligible + rejected
    selected_index = 0
    tie_breaks: list[str] = []
    if len(eligible) > 1:
        best = eligible[0]
        tied = [
            e
            for e in eligible[1:]
            if e.score.score == best.score.score
        ]
        if tied:
            tie_breaks = [
                f"'{best.plan.variant}' won the {len(tied) + 1}-way score tie "
                f"via the deterministic order lower cost, then lower energy, "
                f"then lower CPU"
            ]
    return GenerationEvaluation(
        status="recommended",
        requirements=requirements_from_estimate(estimate),
        candidates=ordered,
        selected_index=selected_index,
        weights_used=weights,
        ranking_explanation=_ranking_explanation(eligible, weights, tie_breaks),
        infeasibility_explanation=None,
        disclaimer=DISCLAIMER,
    )
