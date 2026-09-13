import pytest

from app.schemas.unified_schema import FeatureVector, UtilizationPrediction
from app.schemas.workload_schema import TrafficLevel
from app.services.constraint_service import (
    ConstraintParameters,
    evaluate_constraints,
    parameters_from_settings,
)


def _features(
    *,
    replicas: int = 2,
    expected_users: int = 1000,
    traffic_level: TrafficLevel = "medium",
    max_latency_ms: int = 200,
    availability_target: float = 99.0,
    autoscaling_enabled: bool = False,
    total_cpu_capacity: float = 4.0,
    total_memory_capacity: float = 8.0,
) -> FeatureVector:
    cpu = total_cpu_capacity / replicas
    memory_gb = total_memory_capacity / replicas
    return FeatureVector(
        application_type="rest-api",
        application_type_code=3,
        expected_users=expected_users,
        traffic_level=traffic_level,
        traffic_score={"low": 1, "medium": 2, "high": 3, "variable": 4}[traffic_level],
        max_latency_ms=max_latency_ms,
        availability_target=availability_target,
        cpu=cpu,
        memory_gb=memory_gb,
        replicas=replicas,
        storage_gb=None,
        autoscaling_enabled=autoscaling_enabled,
        autoscaling_enabled_int=int(autoscaling_enabled),
        source_type="kubernetes",
        total_cpu_capacity=total_cpu_capacity,
        total_memory_capacity=total_memory_capacity,
        users_per_replica=expected_users / max(replicas, 1),
    )


def _prediction(cpu: float = 0.25, memory: float = 0.5) -> UtilizationPrediction:
    return UtilizationPrediction(
        cpu_utilization=cpu,
        memory_utilization=memory,
        model_type="RandomForestRegressor",
    )


def _parameters(**overrides: object) -> ConstraintParameters:
    values = {
        "cpu_headroom_threshold": 0.70,
        "memory_headroom_threshold": 0.85,
        "latency_base_ms": 50.0,
        "max_users_per_replica": 2000.0,
        "traffic_multipliers": {"low": 0.5, "medium": 1.0, "high": 2.0, "variable": 1.25},
    }
    values.update(overrides)
    return ConstraintParameters(**values)  # type: ignore[arg-type]


def _check_map(evaluation):
    return {check.name: check for check in evaluation.checks}


def test_parameters_from_settings_reads_configured_defaults() -> None:
    parameters = parameters_from_settings()
    assert parameters.cpu_headroom_threshold == 0.70
    assert parameters.memory_headroom_threshold == 0.85
    assert parameters.latency_base_ms == 50.0
    assert parameters.max_users_per_replica == 2000.0
    assert parameters.traffic_multipliers["medium"] == 1.0


def test_parameters_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="cpu_headroom_threshold"):
        _parameters(cpu_headroom_threshold=1.5)
    with pytest.raises(ValueError, match="memory_headroom_threshold"):
        _parameters(memory_headroom_threshold=-0.1)
    with pytest.raises(ValueError, match="latency_base_ms"):
        _parameters(latency_base_ms=0)
    with pytest.raises(ValueError, match="max_users_per_replica"):
        _parameters(max_users_per_replica=0)
    with pytest.raises(ValueError, match="traffic multipliers"):
        _parameters(traffic_multipliers={"low": 0.0, "medium": 1.0, "high": 2.0, "variable": 1.25})


def test_healthy_configuration_passes_all_checks() -> None:
    evaluation = evaluate_constraints(_features(), _prediction(), _parameters())

    checks = _check_map(evaluation)
    assert evaluation.satisfied is True
    assert all(check.status.value == "pass" for check in checks.values())
    assert set(checks) == {
        "cpu_headroom",
        "memory_headroom",
        "latency_feasibility",
        "availability_replicas",
        "user_capacity",
    }
    assert "not measured performance" in evaluation.disclaimer


def test_cpu_headroom_fails_above_threshold_and_passes_at_boundary() -> None:
    parameters = _parameters()

    failing = evaluate_constraints(
        _features(), _prediction(cpu=0.71), parameters
    )
    assert failing.satisfied is False
    assert _check_map(failing)["cpu_headroom"].status.value == "fail"

    boundary = evaluate_constraints(_features(), _prediction(cpu=0.70), parameters)
    assert _check_map(boundary)["cpu_headroom"].status.value == "pass"


def test_memory_headroom_fails_above_threshold() -> None:
    evaluation = evaluate_constraints(
        _features(), _prediction(memory=0.86), _parameters()
    )

    assert evaluation.satisfied is False
    assert _check_map(evaluation)["memory_headroom"].status.value == "fail"


def test_latency_check_uses_queueing_heuristic() -> None:
    # base 50 ms / (1 - 0.5) = 100 ms <= 200 ms target -> pass.
    passing = evaluate_constraints(
        _features(max_latency_ms=200), _prediction(cpu=0.5), _parameters()
    )
    assert _check_map(passing)["latency_feasibility"].status.value == "pass"
    assert "100" in _check_map(passing)["latency_feasibility"].actual

    # base 50 ms / (1 - 0.75) = 200 ms <= 200 ms target -> boundary pass.
    boundary = evaluate_constraints(
        _features(max_latency_ms=200), _prediction(cpu=0.75), _parameters()
    )
    assert _check_map(boundary)["latency_feasibility"].status.value == "pass"

    # base 50 ms / (1 - 0.9) = 500 ms > 200 ms target -> fail.
    failing = evaluate_constraints(
        _features(max_latency_ms=200), _prediction(cpu=0.9), _parameters()
    )
    assert _check_map(failing)["latency_feasibility"].status.value == "fail"


def test_latency_check_fails_as_saturated_at_high_utilization() -> None:
    evaluation = evaluate_constraints(
        _features(max_latency_ms=100000), _prediction(cpu=0.99), _parameters()
    )

    check = _check_map(evaluation)["latency_feasibility"]
    assert check.status.value == "fail"
    assert check.actual == "saturated"


def test_availability_tiers_require_growing_replicas() -> None:
    parameters = _parameters()

    tiers = [
        (99.0, 1),
        (99.9, 2),
        (99.99, 3),
    ]
    for target, required in tiers:
        evaluation = evaluate_constraints(
            _features(availability_target=target, replicas=required),
            _prediction(),
            parameters,
        )
        check = _check_map(evaluation)["availability_replicas"]
        assert check.status.value == "pass", f"target {target} with {required} replicas"
        assert f">= {required} replica" in check.required

    # Below the covered tiers requires the strictest fallback count.
    failing = evaluate_constraints(
        _features(availability_target=99.999, replicas=3),
        _prediction(),
        parameters,
    )
    assert _check_map(failing)["availability_replicas"].status.value == "fail"

    passing = evaluate_constraints(
        _features(availability_target=99.999, replicas=4),
        _prediction(),
        parameters,
    )
    assert _check_map(passing)["availability_replicas"].status.value == "pass"


def test_availability_passes_with_autoscaling_even_with_few_replicas() -> None:
    evaluation = evaluate_constraints(
        _features(availability_target=99.99, replicas=1, autoscaling_enabled=True),
        _prediction(),
        _parameters(),
    )

    assert _check_map(evaluation)["availability_replicas"].status.value == "pass"
    assert "autoscaling enabled" in _check_map(evaluation)["availability_replicas"].actual


def test_user_capacity_uses_traffic_multipliers() -> None:
    parameters = _parameters()

    # 2 replicas * 2000 users * 1.0 (medium) = 4000 capacity.
    medium = evaluate_constraints(
        _features(expected_users=4000, traffic_level="medium", replicas=2),
        _prediction(),
        parameters,
    )
    assert _check_map(medium)["user_capacity"].status.value == "pass"

    # 2 replicas * 2000 users * 2.0 (high) = 8000 capacity.
    high = evaluate_constraints(
        _features(expected_users=8000, traffic_level="high", replicas=2),
        _prediction(),
        parameters,
    )
    assert _check_map(high)["user_capacity"].status.value == "pass"

    # 2 replicas * 2000 users * 0.5 (low) = 2000 capacity.
    low = evaluate_constraints(
        _features(expected_users=2001, traffic_level="low", replicas=2),
        _prediction(),
        parameters,
    )
    assert _check_map(low)["user_capacity"].status.value == "fail"


def test_explanations_state_predicted_values_not_bare_commands() -> None:
    evaluation = evaluate_constraints(
        _features(expected_users=100000, replicas=2),
        _prediction(cpu=0.9, memory=0.9),
        _parameters(),
    )

    checks = _check_map(evaluation)
    assert evaluation.satisfied is False
    assert "10%" in checks["latency_feasibility"].explanation  # 1 - 0.9 spare CPU
    assert "100000" in checks["user_capacity"].explanation
    assert "4000" in checks["user_capacity"].explanation  # 2 x 2000 x medium
    # Design doc principle: explain WHY, with numbers.
    for check in checks.values():
        assert check.explanation


def test_evaluation_is_deterministic() -> None:
    features = _features()
    prediction = _prediction()

    first = evaluate_constraints(features, prediction, _parameters())
    second = evaluate_constraints(features, prediction, _parameters())

    assert first == second
