"""Tests for the weighted sustainability score (design doc section 23)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.constraint_schema import (
    ConstraintCheck,
    ConstraintEvaluation,
    ConstraintStatus,
)
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.score_schema import SustainabilityScore
from app.schemas.unified_schema import (
    EstimationAssumptions,
    FeatureVector,
    UtilizationPrediction,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services import score_service


def _configuration(**overrides: object) -> InfrastructureConfiguration:
    base = {
        "source_type": "kubernetes",
        "application": "api-backend",
        "replicas": 4,
        "cpu_request": 2.0,
        "cpu_limit": 2.0,
        "memory_request_gb": 4.0,
        "memory_limit_gb": 4.0,
        "autoscaling_enabled": False,
    }
    base.update(overrides)
    return InfrastructureConfiguration.model_validate(base)


def _workload(**overrides: object) -> WorkloadProfile:
    base = {
        "application_type": "rest-api",
        "expected_users": 5000,
        "traffic_level": "medium",
    }
    base.update(overrides)
    return WorkloadProfile.model_validate(base)


def _features(
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
) -> FeatureVector:
    from app.services.feature_service import extract_features

    return extract_features(configuration, workload)


def _prediction(cpu: float = 0.5, memory: float = 0.6) -> UtilizationPrediction:
    return UtilizationPrediction(
        cpu_utilization=cpu,
        memory_utilization=memory,
        model_type="RandomForestRegressor",
        model_created_at=None,
    )


def _estimation(features: FeatureVector, prediction: UtilizationPrediction):
    from app.services.estimation_service import estimate_sustainability

    return estimate_sustainability(features, prediction)


def _constraints(passed: int, total: int = 5) -> ConstraintEvaluation:
    checks = [
        ConstraintCheck(
            name=f"check_{index}",
            status=ConstraintStatus.pass_ if index < passed else ConstraintStatus.fail,
            required="required",
            actual="actual",
            explanation="explanation",
        )
        for index in range(total)
    ]
    return ConstraintEvaluation(
        satisfied=passed == total,
        checks=checks,
        disclaimer="test",
    )


def _score(**kwargs: object) -> SustainabilityScore:
    configuration = kwargs.pop("configuration", _configuration())
    workload = kwargs.pop("workload", _workload())
    prediction = kwargs.pop("prediction", _prediction())
    features = kwargs.pop("features", None) or _features(configuration, workload)
    estimation = kwargs.pop(
        "estimation", _estimation(features, prediction)
    )
    return score_service.compute_score(
        configuration=configuration,
        workload=workload,
        features=features,
        prediction=prediction,
        estimation=estimation,
        constraints=kwargs.pop("constraints", _constraints(5)),
        **kwargs,
    )


def test_score_is_weighted_mean_of_five_components() -> None:
    result = _score()
    assert len(result.components) == 5
    total_weight = sum(component.weight for component in result.components)
    assert total_weight == pytest.approx(1.0)
    expected = sum(component.score * component.weight for component in result.components)
    assert result.score == pytest.approx(round(expected, 4))


def test_score_components_carry_weight_and_explanation() -> None:
    result = _score()
    names = {component.name for component in result.components}
    assert names == {
        "resource_efficiency",
        "energy_efficiency",
        "carbon_impact",
        "cost_efficiency",
        "constraint_compliance",
    }
    for component in result.components:
        assert 0.0 <= component.score <= 1.0
        assert component.weight >= 0.0
        assert component.explanation


def test_higher_utilization_improves_resource_component() -> None:
    low = _score(prediction=_prediction(cpu=0.2))
    high = _score(prediction=_prediction(cpu=0.8))
    resource_low = next(
        c for c in low.components if c.name == "resource_efficiency"
    )
    resource_high = next(
        c for c in high.components if c.name == "resource_efficiency"
    )
    assert resource_high.score > resource_low.score
    assert high.score > low.score


def test_constraint_compliance_tracks_passed_checks() -> None:
    all_pass = _score(constraints=_constraints(5))
    some_fail = _score(constraints=_constraints(2))
    compliance_all = next(
        c for c in all_pass.components if c.name == "constraint_compliance"
    )
    compliance_some = next(
        c for c in some_fail.components if c.name == "constraint_compliance"
    )
    assert compliance_all.score == 1.0
    assert compliance_some.score == pytest.approx(0.4)
    assert all_pass.score > some_fail.score


def test_zero_utilization_scores_worst_on_footprint_components() -> None:
    """Every footprint component measures productive share of provisioned
    capacity, so an idle deployment wastes everything it provisions: all
    footprint components score 0. Fully-loaded scores 1 on each."""
    idle = _score(prediction=_prediction(cpu=0.0, memory=0.0))
    loaded = _score(prediction=_prediction(cpu=1.0, memory=1.0))
    for name in ("resource_efficiency", "energy_efficiency", "carbon_impact", "cost_efficiency"):
        idle_component = next(c for c in idle.components if c.name == name)
        loaded_component = next(c for c in loaded.components if c.name == name)
        assert idle_component.score == pytest.approx(0.0), name
        assert loaded_component.score == pytest.approx(1.0), name
    assert loaded.score > idle.score


def test_cost_efficiency_tracks_active_share_not_absolute_cost() -> None:
    """Larger allocation with the same predicted utilization wastes more
    provisioned cost, so its cost-efficiency share is identical but the
    composite reflects the wasted absolute dollars via raw_value disclosure.
    The share itself is utilization-driven; what changes with allocation is
    the absolute waste. Verify the share logic directly:"""
    small = _score(configuration=_configuration(cpu_request=1.0, memory_request_gb=2.0))
    large = _score(configuration=_configuration(cpu_request=8.0, memory_request_gb=16.0))
    cost_small = next(c for c in small.components if c.name == "cost_efficiency")
    cost_large = next(c for c in large.components if c.name == "cost_efficiency")
    # Same predicted utilization -> same productive share...
    assert cost_small.score == pytest.approx(cost_large.score)
    # ...but the large one discloses far more absolute cost.
    assert float(cost_large.raw_value.lstrip("$").split("/")[0]) > float(
        cost_small.raw_value.lstrip("$").split("/")[0]
    )


def test_custom_weights_are_renormalized() -> None:
    custom = score_service.ScoreWeights(
        resource_efficiency=2.0,
        energy_efficiency=2.0,
        carbon_impact=2.0,
        cost_efficiency=2.0,
        constraint_compliance=2.0,
    ).normalized()
    weights = score_service.weights_from_settings(
        Settings(
            score_weight_resource_efficiency=0.5,
            score_weight_energy_efficiency=0.5,
            score_weight_carbon_impact=0.0,
            score_weight_cost_efficiency=0.0,
            score_weight_constraint_compliance=0.0,
            _env_file=None,
        )
    )
    assert weights.resource_efficiency == pytest.approx(0.5)
    assert weights.energy_efficiency == pytest.approx(0.5)
    assert custom.resource_efficiency == pytest.approx(0.2)


def test_grade_bands() -> None:
    assert score_service._grade(0.9) == "A"
    assert score_service._grade(0.75) == "B"
    assert score_service._grade(0.6) == "C"
    assert score_service._grade(0.45) == "D"
    assert score_service._grade(0.1) == "F"


def test_score_always_discloses_methodology_and_disclaimer() -> None:
    result = _score()
    assert "weighted" in result.methodology.lower()
    assert "not a scientifically validated" in result.disclaimer.lower()
