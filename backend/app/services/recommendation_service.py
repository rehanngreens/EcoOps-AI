"""Phase 9 recommendation engine: candidates -> evaluate -> rank -> persist.

The engine is deliberately model-limitation-aware. Ranking is driven by
estimated cost/energy/carbon savings (allocation-based, Phase 7), not by
predicted utilization, which is used only as a headroom veto guard. This
keeps recommendations sound even while the Phase 5 model is insensitive to
allocation changes; a better model slots in with no code change here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.recommendation import (
    RecommendationItemRecord,
    RecommendationSetRecord,
    new_recommendation_item_id,
    new_recommendation_set_id,
)
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.recommendation_schema import (
    EstimationTotals,
    OptimizationScores,
    OptimizeResponse,
    RejectedCandidate,
    RecommendationItem,
    RecommendationSet,
    RecommendationStatus,
    RecommendationTotals,
)
from app.schemas.unified_schema import SustainabilityEstimation, UtilizationPrediction
from app.services import analysis_service, candidate_service, constraint_service, estimation_service, prediction_service, score_service
from app.services.candidate_service import Candidate
from app.services.feature_service import extract_features

DISCLAIMER = (
    "Recommendations are advisory prototype estimates. Savings are computed "
    "from configurable pricing and power assumptions and predicted "
    "utilization comes from a prototype model that is currently insensitive "
    "to allocation changes; a qualified engineer must review every "
    "suggestion before deployment."
)

# Predicted-utilization guard. Historical note: while the Phase 5 model was
# allocation-insensitive, the veto compared against baseline + tolerance and
# every candidate tied the baseline, so it never fired. Now that the model
# responds to allocation, any real scale-down raises predicted utilization —
# comparing against the baseline would reject every legitimate candidate.
# The veto therefore rejects only candidates predicted to saturate a
# resource outright; the constraint engine (headroom/latency/capacity
# checks) remains the authoritative feasibility gate.
SATURATION_LIMIT = 0.95


def _scores_for(
    configuration: InfrastructureConfiguration,
    workload,
) -> tuple:
    """Compute the sustainability score for one configuration.

    Score components are deterministic given the configuration, workload,
    and current model artifacts, so they are computed on demand rather than
    persisted — always consistent with the score endpoint, no migration.
    Returns (score, features, prediction, estimation) so callers can reuse
    the pipeline outputs.
    """
    features = extract_features(configuration, workload)
    prediction = prediction_service.predict_utilization(features)
    estimation = estimation_service.estimate_sustainability(features, prediction)
    constraints = constraint_service.evaluate_constraints(features, prediction)
    score = score_service.compute_score(
        configuration=configuration,
        workload=workload,
        features=features,
        prediction=prediction,
        estimation=estimation,
        constraints=constraints,
    )
    return score, features, prediction, estimation


def _summary(configuration: InfrastructureConfiguration) -> str:
    cpu = f"{configuration.cpu_request:g}c" if configuration.cpu_request is not None else "?"
    memory = f"{configuration.memory_request_gb:g}Gi" if configuration.memory_request_gb is not None else "?"
    autoscaling = "autoscale" if configuration.autoscaling_enabled else "fixed"
    return f"{configuration.replicas}x {cpu}/{memory} ({autoscaling})"


def _totals(estimation: SustainabilityEstimation) -> EstimationTotals:
    return EstimationTotals(
        estimated_cost_usd=round(estimation.estimated_cost_usd, 4),
        estimated_energy_kwh=round(estimation.estimated_energy_kwh, 4),
        estimated_carbon_kg_co2e=round(estimation.estimated_carbon_kg_co2e, 4),
    )


def _headroom_margin(prediction: UtilizationPrediction) -> float:
    """Smallest distance to any utilization ceiling; larger is safer."""
    return min(1.0 - prediction.cpu_utilization, 1.0 - prediction.memory_utilization)


def _evaluate_candidate(
    candidate: Candidate,
    workload,
    baseline_cpu: float,
    baseline_memory: float,
) -> tuple[bool, str, SustainabilityEstimation | None, UtilizationPrediction | None]:
    """Run one candidate through the full pipeline. Returns (passed, reason, estimation, prediction)."""
    features = extract_features(candidate.configuration, workload)
    prediction = prediction_service.predict_utilization(features)

    # Saturation veto: never propose a candidate predicted to run a resource
    # at >= 95% utilization. The five constraint checks remain the primary
    # feasibility gate; this veto only blocks candidates the checks might
    # tolerate but no engineer should ship.
    if (
        prediction.cpu_utilization >= SATURATION_LIMIT
        or prediction.memory_utilization >= SATURATION_LIMIT
    ):
        return False, (
            f"predicted utilization (cpu {prediction.cpu_utilization:.1%}, "
            f"memory {prediction.memory_utilization:.1%}) would saturate a resource"
        ), None, prediction

    estimation = estimation_service.estimate_sustainability(features, prediction)
    evaluation = constraint_service.evaluate_constraints(features, prediction)
    if not evaluation.satisfied:
        failed = [check.name for check in evaluation.checks if check.status.value == "fail"]
        return False, f"failed constraint check(s): {', '.join(failed)}", estimation, prediction

    return True, "all constraints satisfied", estimation, prediction


def _items_for(
    baseline: InfrastructureConfiguration,
    optimized: InfrastructureConfiguration,
    workload,
) -> list[RecommendationItem]:
    items: list[RecommendationItem] = []

    if optimized.cpu_request is not None and baseline.cpu_request is not None and optimized.cpu_request != baseline.cpu_request:
        items.append(
            RecommendationItem(
                parameter="cpu_request",
                current_value=f"{baseline.cpu_request:g} cores",
                suggested_value=f"{optimized.cpu_request:g} cores",
                reason=(
                    "Estimated savings with all constraints satisfied; predicted "
                    "utilization remains within configured headroom thresholds."
                ),
            )
        )

    if (
        optimized.memory_request_gb is not None
        and baseline.memory_request_gb is not None
        and optimized.memory_request_gb != baseline.memory_request_gb
    ):
        items.append(
            RecommendationItem(
                parameter="memory_request_gb",
                current_value=f"{baseline.memory_request_gb:g} GiB",
                suggested_value=f"{optimized.memory_request_gb:g} GiB",
                reason=(
                    "Estimated savings with all constraints satisfied; predicted "
                    "utilization remains within configured headroom thresholds."
                ),
            )
        )

    if optimized.replicas != baseline.replicas:
        items.append(
            RecommendationItem(
                parameter="replicas",
                current_value=str(baseline.replicas),
                suggested_value=str(optimized.replicas),
                reason=(
                    "Replica floor respects the availability tier for the "
                    "workload target; all constraints remain satisfied."
                ),
            )
        )

    if optimized.autoscaling_enabled != baseline.autoscaling_enabled:
        items.append(
            RecommendationItem(
                parameter="autoscaling_enabled",
                current_value=str(baseline.autoscaling_enabled).lower(),
                suggested_value=str(optimized.autoscaling_enabled).lower(),
                reason=(
                    "Autoscaling lets replicas follow load instead of a fixed "
                    "peak allocation; availability checks pass with scaling enabled."
                ),
            )
        )

    return items


def run_optimization(db: Session, analysis_id: str) -> OptimizeResponse:
    """Run the full optimization for a stored analysis and persist the result."""
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise KeyError(analysis_id)

    baseline_configuration = analysis_service.to_configuration(record)
    workload = analysis_service.to_workload(record)

    baseline_score, baseline_features, baseline_prediction, baseline_estimation = _scores_for(
        baseline_configuration, workload
    )

    rejected: list[RejectedCandidate] = []
    passing: list[tuple[Candidate, SustainabilityEstimation, UtilizationPrediction]] = []

    for candidate in candidate_service.generate_candidates(baseline_configuration, workload):
        passed, reason, estimation, prediction = _evaluate_candidate(
            candidate,
            workload,
            baseline_prediction.cpu_utilization,
            baseline_prediction.memory_utilization,
        )
        if passed and estimation is not None and prediction is not None:
            passing.append((candidate, estimation, prediction))
        else:
            rejected.append(
                RejectedCandidate(summary=_summary(candidate.configuration), reason=reason)
            )

    # Rank: lowest estimated cost first; tie-break toward larger headroom margin.
    passing.sort(key=lambda entry: (entry[1].estimated_cost_usd, -_headroom_margin(entry[2])))

    set_id = new_recommendation_set_id()

    if not passing:
        explanation = (
            "No scale-down candidate satisfied all constraints for this "
            "workload profile; the current configuration is kept."
        )
        db.add(
            RecommendationSetRecord(
                id=set_id,
                analysis_id=record.id,
                status=RecommendationStatus.no_recommendation.value,
                baseline_configuration=baseline_configuration.model_dump(),
                optimized_configuration=None,
                totals={
                    "baseline": _totals(baseline_estimation).model_dump(),
                },
                rejected_candidates=[item.model_dump() for item in rejected],
                explanation=explanation,
            )
        )
        db.commit()
        return OptimizeResponse(
            analysis_id=record.id,
            recommendation_set=RecommendationSet(
                status=RecommendationStatus.no_recommendation,
                baseline_configuration=baseline_configuration.model_dump(),
                totals=None,
                items=[],
                rejected_candidates=rejected,
                explanation=explanation,
                disclaimer=DISCLAIMER,
            ),
            scores=OptimizationScores(baseline=baseline_score),
        )

    best, best_estimation, best_prediction = passing[0]
    optimized_configuration = best.configuration
    totals = RecommendationTotals(
        baseline=_totals(baseline_estimation),
        optimized=_totals(best_estimation),
        cost_reduction_usd=round(
            max(baseline_estimation.estimated_cost_usd - best_estimation.estimated_cost_usd, 0.0), 4
        ),
        energy_reduction_kwh=round(
            max(baseline_estimation.estimated_energy_kwh - best_estimation.estimated_energy_kwh, 0.0), 4
        ),
        carbon_reduction_kg_co2e=round(
            max(baseline_estimation.estimated_carbon_kg_co2e - best_estimation.estimated_carbon_kg_co2e, 0.0), 4
        ),
    )
    items = _items_for(baseline_configuration, optimized_configuration, workload)
    explanation = (
        f"Selected candidate '{best.summary}' with predicted utilization "
        f"(cpu {best_prediction.cpu_utilization:.1%}, memory "
        f"{best_prediction.memory_utilization:.1%}); all constraints "
        f"satisfied. {len(rejected)} candidate(s) rejected for transparency."
    )

    db.add(
        RecommendationSetRecord(
            id=set_id,
            analysis_id=record.id,
            status=RecommendationStatus.recommended.value,
            baseline_configuration=baseline_configuration.model_dump(),
            optimized_configuration=optimized_configuration.model_dump(),
            totals=totals.model_dump(),
            rejected_candidates=[item.model_dump() for item in rejected],
            explanation=explanation,
        )
    )
    for item in items:
        db.add(
            RecommendationItemRecord(
                id=new_recommendation_item_id(),
                recommendation_set_id=set_id,
                parameter=item.parameter,
                current_value=item.current_value,
                suggested_value=item.suggested_value,
                reason=item.reason,
            )
        )
    db.commit()

    optimized_score = score_service.compute_score(
        configuration=optimized_configuration,
        workload=workload,
        features=extract_features(optimized_configuration, workload),
        prediction=best_prediction,
        estimation=best_estimation,
        constraints=constraint_service.evaluate_constraints(
            extract_features(optimized_configuration, workload), best_prediction
        ),
    )
    scores = OptimizationScores(
        baseline=baseline_score,
        optimized=optimized_score,
        improvement=round(optimized_score.score - baseline_score.score, 4),
    )

    return OptimizeResponse(
        analysis_id=record.id,
        recommendation_set=RecommendationSet(
            status=RecommendationStatus.recommended,
            baseline_configuration=baseline_configuration.model_dump(),
            optimized_configuration=optimized_configuration.model_dump(),
            totals=totals,
            items=items,
            rejected_candidates=rejected,
            explanation=explanation,
            disclaimer=DISCLAIMER,
        ),
        scores=scores,
    )


def get_recommendations(db: Session, analysis_id: str) -> OptimizeResponse | None:
    """Return the persisted recommendation set for one analysis, if any."""
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise KeyError(analysis_id)

    stored = (
        db.query(RecommendationSetRecord)
        .filter(RecommendationSetRecord.analysis_id == analysis_id)
        .order_by(RecommendationSetRecord.created_at.desc())
        .first()
    )
    if stored is None:
        return None

    stored_items = (
        db.query(RecommendationItemRecord)
        .filter(RecommendationItemRecord.recommendation_set_id == stored.id)
        .all()
    )

    totals = None
    if stored.totals and "optimized" in stored.totals:
        baseline_totals = EstimationTotals.model_validate(stored.totals["baseline"])
        optimized_totals = EstimationTotals.model_validate(stored.totals["optimized"])
        totals = RecommendationTotals(
            baseline=baseline_totals,
            optimized=optimized_totals,
            cost_reduction_usd=round(baseline_totals.estimated_cost_usd - optimized_totals.estimated_cost_usd, 4),
            energy_reduction_kwh=round(
                baseline_totals.estimated_energy_kwh - optimized_totals.estimated_energy_kwh, 4
            ),
            carbon_reduction_kg_co2e=round(
                baseline_totals.estimated_carbon_kg_co2e - optimized_totals.estimated_carbon_kg_co2e, 4
            ),
        )

    baseline_configuration = InfrastructureConfiguration.model_validate(
        stored.baseline_configuration
    )
    baseline_score, _, _, _ = _scores_for(
        baseline_configuration, analysis_service.to_workload(record)
    )

    scores = OptimizationScores(baseline=baseline_score)
    if stored.optimized_configuration is not None:
        optimized_configuration = InfrastructureConfiguration.model_validate(
            stored.optimized_configuration
        )
        optimized_score, _, _, _ = _scores_for(
            optimized_configuration, analysis_service.to_workload(record)
        )
        scores = OptimizationScores(
            baseline=baseline_score,
            optimized=optimized_score,
            improvement=round(optimized_score.score - baseline_score.score, 4),
        )

    return OptimizeResponse(
        analysis_id=stored.analysis_id,
        recommendation_set=RecommendationSet(
            status=RecommendationStatus(stored.status),
            baseline_configuration=stored.baseline_configuration,
            optimized_configuration=stored.optimized_configuration,
            totals=totals,
            items=[
                RecommendationItem(
                    parameter=item.parameter,
                    current_value=item.current_value,
                    suggested_value=item.suggested_value,
                    reason=item.reason,
                )
                for item in stored_items
            ],
            rejected_candidates=[
                RejectedCandidate.model_validate(entry) for entry in (stored.rejected_candidates or [])
            ],
            explanation=stored.explanation,
            disclaimer=DISCLAIMER,
        ),
        scores=scores,
    )
