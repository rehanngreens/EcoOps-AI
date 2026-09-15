import pytest

from app.schemas.unified_schema import FeatureVector, UtilizationPrediction
from app.services.recommendation_service import _headroom_margin, _totals


def _features(**overrides: object) -> FeatureVector:
    values: dict = {
        "application_type": "rest-api",
        "application_type_code": 3,
        "expected_users": 1000,
        "traffic_level": "medium",
        "traffic_score": 2,
        "max_latency_ms": 200,
        "availability_target": 99.0,
        "cpu": 1.0,
        "memory_gb": 2.0,
        "replicas": 2,
        "storage_gb": None,
        "autoscaling_enabled": False,
        "autoscaling_enabled_int": 0,
        "source_type": "kubernetes",
        "total_cpu_capacity": 2.0,
        "total_memory_capacity": 4.0,
        "users_per_replica": 500.0,
    }
    values.update(overrides)
    return FeatureVector(**values)  # type: ignore[arg-type]


def _prediction(cpu: float = 0.25, memory: float = 0.5) -> UtilizationPrediction:
    return UtilizationPrediction(
        cpu_utilization=cpu,
        memory_utilization=memory,
        model_type="RandomForestRegressor",
    )


def test_headroom_margin_uses_tightest_constraint() -> None:
    assert _headroom_margin(_prediction(cpu=0.25, memory=0.5)) == pytest.approx(0.5)
    assert _headroom_margin(_prediction(cpu=0.9, memory=0.5)) == pytest.approx(0.1)


def test_totals_rounds_values() -> None:
    from app.schemas.unified_schema import SustainabilityEstimation

    estimation = SustainabilityEstimation(
        estimated_cost_usd=73.123456789,
        estimated_energy_kwh=15.841111,
        estimated_carbon_kg_co2e=6.811163,
        active_cpu_vcpus=1.0,
        active_memory_gb=1.0,
        assumptions={
            "period_hours": 730,
            "cpu_cost_per_vcpu_hour_usd": 0.04,
            "memory_cost_per_gb_hour_usd": 0.005,
            "cpu_power_watts_per_active_vcpu": 15,
            "memory_power_watts_per_active_gb": 0.5,
            "data_center_pue": 1.4,
            "carbon_intensity_gco2_per_kwh": 430,
        },
        disclaimer="test",
    )

    totals = _totals(estimation)
    assert totals.estimated_cost_usd == pytest.approx(73.1235)
    assert totals.estimated_energy_kwh == pytest.approx(15.8411)
    assert totals.estimated_carbon_kg_co2e == pytest.approx(6.8112)


def test_features_helper_builds_valid_vector() -> None:
    features = _features()
    assert features.total_cpu_capacity == 2.0
    assert features.replicas == 2


def test_scores_for_includes_all_components_and_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.schemas.infrastructure_schema import InfrastructureConfiguration
    from app.schemas.workload_schema import WorkloadProfile
    from app.services import recommendation_service

    # CI runners have no trained model artifacts (ml/models/ is gitignored);
    # these assertions are about the score's shape, not the predictions.
    monkeypatch.setattr(
        recommendation_service.prediction_service,
        "predict_utilization",
        lambda _: _prediction(),
    )

    configuration = InfrastructureConfiguration.model_validate(
        {
            "source_type": "kubernetes",
            "application": "api-backend",
            "replicas": 2,
            "cpu_request": 1.0,
            "cpu_limit": 1.0,
            "memory_request_gb": 2.0,
            "memory_limit_gb": 2.0,
            "autoscaling_enabled": False,
        }
    )
    workload = WorkloadProfile(application_type="rest-api", expected_users=1000)

    score, features, prediction, estimation = recommendation_service._scores_for(
        configuration, workload
    )

    assert len(score.components) == 5
    assert sum(component.weight for component in score.components) == pytest.approx(1.0)
    assert features.total_cpu_capacity == 2.0
    assert 0.0 <= prediction.cpu_utilization <= 1.0
    assert estimation.estimated_cost_usd >= 0
