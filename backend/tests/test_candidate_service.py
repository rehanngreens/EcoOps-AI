import pytest

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile
from app.services.candidate_service import generate_candidates


def _config(**overrides: object) -> InfrastructureConfiguration:
    values: dict = {
        "source_type": "kubernetes",
        "application": "demo",
        "replicas": 4,
        "cpu_request": 2.0,
        "memory_request_gb": 4.0,
        "autoscaling_enabled": False,
    }
    values.update(overrides)
    return InfrastructureConfiguration(**values)  # type: ignore[arg-type]


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "e-commerce",
        "expected_users": 10000,
        "traffic_level": "medium",
        "max_latency_ms": 150,
        "availability_target": 99.9,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


def test_generates_scale_down_candidates_for_heavy_config() -> None:
    candidates = generate_candidates(_config(replicas=8, cpu_request=8.0, memory_request_gb=16.0), _workload())
    summaries = [c.summary.lower() for c in candidates]

    # CPU step-downs at 50% and 25%
    assert any("cpu" in s and " to 4 " in s for s in summaries)
    assert any("cpu" in s and " to 2 " in s for s in summaries)
    # Memory step-downs
    assert any("memory" in s and " to 8 " in s for s in summaries)
    assert any("memory" in s and " to 4 " in s for s in summaries)
    # Replica reductions respecting floor 2 for 99.9%
    assert any("replicas from 8 to 2" in s for s in summaries)
    assert any("replicas from 8 to 4" in s for s in summaries)
    # Autoscaling candidate
    assert any("autoscaling" in s for s in summaries)
    # Combined candidate
    assert any("combine reductions" in s for s in summaries)
    assert len(candidates) == 8


def test_replica_floor_never_below_availability_tier() -> None:
    # 99.99% -> floor 3 replicas
    candidates = generate_candidates(_config(replicas=8), _workload(availability_target=99.99))
    replica_values = [
        c.configuration.replicas for c in candidates if c.configuration.replicas != 4
    ]
    assert all(value >= 3 for value in replica_values)

    # 99.999% -> fallback floor 4
    candidates = generate_candidates(_config(replicas=8), _workload(availability_target=99.999))
    replica_values = [
        c.configuration.replicas for c in candidates if c.configuration.replicas != 4
    ]
    assert all(value >= 4 for value in replica_values)


def test_no_replica_candidates_when_at_floor() -> None:
    # 2 replicas with 99.9% target (floor 2) -> no replica reductions
    candidates = generate_candidates(_config(replicas=2), _workload())
    assert all(c.configuration.replicas >= 2 for c in candidates)
    assert not any("replicas from 2" in c.summary for c in candidates)


def test_cpu_and_memory_floors_respected() -> None:
    candidates = generate_candidates(
        _config(cpu_request=0.3, memory_request_gb=0.3), _workload()
    )
    for candidate in candidates:
        if candidate.configuration.cpu_request is not None:
            assert candidate.configuration.cpu_request >= 0.25
        if candidate.configuration.memory_request_gb is not None:
            assert candidate.configuration.memory_request_gb >= 0.25


def test_autoscaling_candidate_skipped_when_already_enabled() -> None:
    candidates = generate_candidates(_config(autoscaling_enabled=True), _workload())
    assert not any("autoscaling" in c.summary for c in candidates)


def test_minimal_config_yields_no_candidates() -> None:
    # Tiny allocation, one replica, autoscaling on -> nothing sensible to propose
    candidates = generate_candidates(
        _config(replicas=1, cpu_request=0.25, memory_request_gb=0.25, autoscaling_enabled=True),
        _workload(availability_target=99.0),
    )
    assert candidates == []


def test_candidates_all_differ_from_current() -> None:
    config = _config()
    candidates = generate_candidates(config, _workload())
    current_key = config.model_dump_json()
    assert all(c.configuration.model_dump_json() != current_key for c in candidates)


def test_generation_is_deterministic() -> None:
    config, workload = _config(), _workload()
    first = generate_candidates(config, workload)
    second = generate_candidates(config, workload)
    assert [c.summary for c in first] == [c.summary for c in second]
