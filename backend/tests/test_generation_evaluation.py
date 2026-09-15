"""Tests for Phase 15: candidate evaluation and ranking (sections 44.3, 44.5).

The predictor is mocked throughout: CI runners have no trained model
artifacts (ml/models/ is gitignored), and these assertions are about the
evaluation loop's reuse, gating, ranking, and disclosure — not the model.
"""

import pytest

from app.schemas.unified_schema import UtilizationPrediction
from app.schemas.workload_schema import WorkloadProfile
from app.services import prediction_service
from app.services.generation import evaluation_service
from app.services.generation.candidate_generator import plans_for_workload
from app.services.generation.evaluation_service import (
    evaluate_candidate,
    evaluate_generation,
    weights_for_priorities,
)

_WEIGHT_COMPONENTS = (
    "resource_efficiency",
    "energy_efficiency",
    "carbon_impact",
    "cost_efficiency",
    "constraint_compliance",
)


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "e-commerce",
        "expected_users": 5000,
        "traffic_level": "medium",
        "max_latency_ms": 200,
        "availability_target": 99.9,
        "average_rps": 300.0,
        "peak_rps": 600.0,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


def _prediction(cpu: float = 0.35, memory: float = 0.40) -> UtilizationPrediction:
    return UtilizationPrediction(
        cpu_utilization=cpu,
        memory_utilization=memory,
        model_type="mock",
        model_created_at=None,
    )


@pytest.fixture()
def mock_predictor(monkeypatch: pytest.MonkeyPatch):
    """Replace the model-backed predictor with a configurable fake."""

    def _install(cpu: float = 0.35, memory: float = 0.40):
        monkeypatch.setattr(
            prediction_service,
            "predict_utilization",
            lambda features: _prediction(cpu, memory),
        )

    return _install


class TestPriorityWeights:
    def test_weights_normalize_to_one(self) -> None:
        weights = weights_for_priorities(_workload())
        assert set(weights) == set(_WEIGHT_COMPONENTS)
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_high_sustainability_boosts_energy_and_carbon(self) -> None:
        baseline = weights_for_priorities(_workload())
        boosted = weights_for_priorities(_workload(sustainability_priority="high"))
        assert boosted["energy_efficiency"] > baseline["energy_efficiency"]
        assert boosted["carbon_impact"] > baseline["carbon_impact"]
        assert boosted["cost_efficiency"] < baseline["cost_efficiency"]

    def test_high_performance_boosts_resource_and_compliance(self) -> None:
        boosted = weights_for_priorities(_workload(performance_priority="high"))
        baseline = weights_for_priorities(_workload())
        assert boosted["resource_efficiency"] > baseline["resource_efficiency"]
        assert boosted["constraint_compliance"] > baseline["constraint_compliance"]

    def test_high_cost_boosts_cost_component(self) -> None:
        boosted = weights_for_priorities(_workload(cost_priority="high"))
        baseline = weights_for_priorities(_workload())
        assert boosted["cost_efficiency"] > baseline["cost_efficiency"]

    def test_all_medium_matches_settings_baseline(self) -> None:
        weights = weights_for_priorities(_workload())  # all priorities medium
        from app.services import score_service

        base = score_service.weights_from_settings()
        for name in _WEIGHT_COMPONENTS:
            assert weights[name] == pytest.approx(getattr(base, name))


class TestEvaluateCandidate:
    def test_candidate_flows_full_existing_pipeline(self, mock_predictor) -> None:
        mock_predictor()
        workload = _workload()
        _, plans = plans_for_workload(workload)
        weights = weights_for_priorities(workload)
        evaluation = evaluate_candidate(plans[0], workload, weights)

        assert evaluation.prediction.model_type == "mock"
        assert evaluation.estimation.estimated_cost_usd > 0
        assert evaluation.estimation.estimated_energy_kwh > 0
        assert evaluation.estimation.estimated_carbon_kg_co2e > 0
        assert len(evaluation.constraints.checks) == 5
        assert evaluation.score.components  # weighted score computed

    def test_eligible_when_all_checks_pass(self, mock_predictor) -> None:
        mock_predictor(cpu=0.30, memory=0.35)
        workload = _workload()
        _, plans = plans_for_workload(workload)
        evaluation = evaluate_candidate(plans[1], workload, weights_for_priorities(workload))
        assert evaluation.eligible is True
        assert evaluation.rejection_reasons == []

    def test_ineligible_when_a_check_fails_with_reasons(self, mock_predictor) -> None:
        # Saturated CPU fails cpu_headroom, latency_feasibility, and the
        # score's constraint compliance plummets — but the pipeline still
        # produces a complete, persisted-style evaluation.
        mock_predictor(cpu=0.98, memory=0.40)
        workload = _workload()
        _, plans = plans_for_workload(workload)
        evaluation = evaluate_candidate(plans[0], workload, weights_for_priorities(workload))
        assert evaluation.eligible is False
        assert evaluation.rejection_reasons
        assert any("cpu_headroom" in reason for reason in evaluation.rejection_reasons)


class TestEvaluateGeneration:
    def test_recommended_path_selects_ranked_winner(self, mock_predictor) -> None:
        mock_predictor()
        result = evaluate_generation(_workload())
        assert result.status == "recommended"
        assert result.selected_index == 0
        winner = result.candidates[result.selected_index]
        assert winner.eligible is True
        assert result.infeasibility_explanation is None
        assert "Selected the" in result.ranking_explanation

    def test_all_candidates_present_including_rejected(self, mock_predictor) -> None:
        mock_predictor()
        result = evaluate_generation(_workload())
        _, plans = plans_for_workload(_workload())
        assert len(result.candidates) == len(plans)
        eligible = [c for c in result.candidates if c.eligible]
        # Eligible candidates appear first, in rank order (scores non-increasing).
        scores = [c.score.score for c in eligible]
        assert scores == sorted(scores, reverse=True)

    def test_weights_disclosed_in_result(self, mock_predictor) -> None:
        mock_predictor()
        result = evaluate_generation(_workload(sustainability_priority="high"))
        assert set(result.weights_used) == set(_WEIGHT_COMPONENTS)
        assert sum(result.weights_used.values()) == pytest.approx(1.0)
        assert "weights" in result.ranking_explanation.lower()

    def test_infeasible_when_every_candidate_rejected(self, mock_predictor, monkeypatch) -> None:
        # The predictor is mocked too: CI has no model artifacts, and the
        # infeasible path is about constraint gating, not predictions.
        mock_predictor()

        # Force every check to fail for every candidate.
        def _always_fail(features, prediction):
            from app.schemas.constraint_schema import ConstraintCheck, ConstraintEvaluation, ConstraintStatus

            checks = [
                ConstraintCheck(
                    name="cpu_headroom",
                    status=ConstraintStatus.fail,
                    required="predicted utilization <= 70%",
                    actual="98.0%",
                    explanation="Mocked total failure for the infeasible path.",
                )
            ]
            return ConstraintEvaluation(
                satisfied=False, checks=checks, disclaimer="mock"
            )

        monkeypatch.setattr(
            evaluation_service.constraint_service,
            "evaluate_constraints",
            _always_fail,
        )
        result = evaluate_generation(_workload())
        assert result.status == "infeasible"
        assert result.selected_index is None
        assert result.infeasibility_explanation is not None
        assert "cpu_headroom" in result.infeasibility_explanation
        assert "does not return constraint-violating" in result.infeasibility_explanation
        assert all(not c.eligible for c in result.candidates)

    def test_requirements_echoed_with_notes(self, mock_predictor) -> None:
        mock_predictor()
        result = evaluate_generation(_workload())
        assert result.requirements.cpu_cores > 0
        assert result.requirements.notes  # Phase 14 explainability carries through
        assert result.disclaimer  # every number is labeled an estimate

    def test_ranking_is_deterministic(self, mock_predictor) -> None:
        mock_predictor()
        workload = _workload()
        first = evaluate_generation(workload)
        second = evaluate_generation(workload)
        assert first.selected_index == second.selected_index
        assert [c.plan.variant for c in first.candidates] == [
            c.plan.variant for c in second.candidates
        ]
        assert first.ranking_explanation == second.ranking_explanation

    def test_scores_differ_across_candidates(self, monkeypatch) -> None:
        # Realistic mock: predicted utilization falls as the allocation grows
        # (a fixed workload spread over more capacity). A constant mock
        # cannot differentiate because the score is efficiency-based.
        def _features_aware(features):
            cpu = max(0.05, min(0.95, 2.0 / features.total_cpu_capacity))
            memory = max(0.05, min(0.95, 2.0 / features.total_memory_capacity))
            return _prediction(cpu, memory)

        monkeypatch.setattr(
            prediction_service, "predict_utilization", _features_aware
        )
        result = evaluate_generation(_workload())
        scores = {round(c.score.score, 6) for c in result.candidates}
        assert len(scores) > 1
