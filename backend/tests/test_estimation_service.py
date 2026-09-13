import pytest

from app.schemas.unified_schema import FeatureVector, UtilizationPrediction
from app.services.estimation_service import EstimationParameters, estimate_sustainability


def _features() -> FeatureVector:
    return FeatureVector(
        application_type="rest-api",
        application_type_code=3,
        expected_users=1000,
        traffic_level="medium",
        traffic_score=2,
        max_latency_ms=200,
        availability_target=99.0,
        cpu=1.0,
        memory_gb=2.0,
        replicas=2,
        autoscaling_enabled=False,
        autoscaling_enabled_int=0,
        source_type="kubernetes",
        total_cpu_capacity=2.0,
        total_memory_capacity=4.0,
        users_per_replica=500.0,
    )


def _parameters() -> EstimationParameters:
    return EstimationParameters(
        period_hours=730,
        cpu_cost_per_vcpu_hour_usd=0.04,
        memory_cost_per_gb_hour_usd=0.005,
        cpu_power_watts_per_active_vcpu=15,
        memory_power_watts_per_active_gb=0.5,
        data_center_pue=1.4,
        carbon_intensity_gco2_per_kwh=430,
    )


def test_estimate_sustainability_uses_allocation_for_cost_and_utilization_for_energy() -> None:
    prediction = UtilizationPrediction(
        cpu_utilization=0.5,
        memory_utilization=0.25,
        model_type="RandomForestRegressor",
    )

    estimate = estimate_sustainability(_features(), prediction, _parameters())

    assert estimate.active_cpu_vcpus == 1.0
    assert estimate.active_memory_gb == 1.0
    assert estimate.estimated_cost_usd == pytest.approx(73.0)
    assert estimate.estimated_energy_kwh == pytest.approx(15.841)
    assert estimate.estimated_carbon_kg_co2e == pytest.approx(6.81163)
    assert "not measured usage" in estimate.disclaimer


def test_zero_utilization_has_zero_energy_and_carbon_but_retains_provisioned_cost() -> None:
    prediction = UtilizationPrediction(
        cpu_utilization=0,
        memory_utilization=0,
        model_type="RandomForestRegressor",
    )

    estimate = estimate_sustainability(_features(), prediction, _parameters())

    assert estimate.estimated_cost_usd == pytest.approx(73.0)
    assert estimate.estimated_energy_kwh == 0
    assert estimate.estimated_carbon_kg_co2e == 0


def test_estimation_parameters_reject_invalid_pue() -> None:
    with pytest.raises(ValueError, match="at least one"):
        EstimationParameters(
            period_hours=730,
            cpu_cost_per_vcpu_hour_usd=0.04,
            memory_cost_per_gb_hour_usd=0.005,
            cpu_power_watts_per_active_vcpu=15,
            memory_power_watts_per_active_gb=0.5,
            data_center_pue=0.9,
            carbon_intensity_gco2_per_kwh=430,
        )
