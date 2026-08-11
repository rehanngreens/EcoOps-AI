import json

import pytest
from pydantic import ValidationError

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile
from app.services.feature_service import build_unified_configuration, extract_features
from tests.conftest import load_manifest
from app.parsers.kubernetes_parser import parse_kubernetes_yaml

HEAVY_WORKLOAD = WorkloadProfile(
    application_type="e-commerce",
    expected_users=10000,
    traffic_level="medium",
    max_latency_ms=150,
    availability_target=99.9,
)


def _infra_from_manifest(name: str) -> InfrastructureConfiguration:
    return InfrastructureConfiguration.model_validate(parse_kubernetes_yaml(load_manifest(name)))


def test_workload_profile_rejects_negative_users() -> None:
    with pytest.raises(ValidationError):
        WorkloadProfile(expected_users=-1)


def test_workload_profile_rejects_invalid_traffic_level() -> None:
    with pytest.raises(ValidationError):
        WorkloadProfile(traffic_level="extreme")  # type: ignore[arg-type]


def test_workload_profile_rejects_invalid_latency() -> None:
    with pytest.raises(ValidationError):
        WorkloadProfile(max_latency_ms=0)


def test_workload_profile_normalizes_enums() -> None:
    profile = WorkloadProfile.model_validate(
        {
            "application_type": "E-Commerce",
            "traffic_level": "HIGH",
        }
    )
    assert profile.application_type == "e-commerce"
    assert profile.traffic_level == "high"


def test_build_unified_configuration_maps_parser_fields() -> None:
    configuration = _infra_from_manifest("deployment-well-provisioned.yaml")
    unified = build_unified_configuration(configuration, HEAVY_WORKLOAD)

    assert unified.application_type == "e-commerce"
    assert unified.expected_users == 10000
    assert unified.traffic_level == "medium"
    assert unified.cpu == 0.5
    assert unified.memory_gb == 0.5
    assert unified.replicas == 2
    assert unified.autoscaling_enabled is False
    assert unified.source_type == "kubernetes"


def test_extract_features_heavy_overprovisioned_scenario() -> None:
    configuration = _infra_from_manifest("deployment-heavy-overprovisioned.yaml")
    features = extract_features(configuration, HEAVY_WORKLOAD)

    assert features.application_type == "e-commerce"
    assert features.application_type_code == 2
    assert features.expected_users == 10000
    assert features.traffic_level == "medium"
    assert features.traffic_score == 2
    assert features.cpu == 8.0
    assert features.memory_gb == 16.0
    assert features.replicas == 8
    assert features.total_cpu_capacity == 64.0
    assert features.total_memory_capacity == 128.0
    assert features.users_per_replica == 1250.0
    assert features.autoscaling_enabled_int == 0


def test_extract_features_uses_defaults_for_missing_resource_requests() -> None:
    configuration = InfrastructureConfiguration(
        source_type="kubernetes",
        application="minimal-app",
        replicas=1,
    )
    workload = WorkloadProfile()
    features = extract_features(configuration, workload)

    assert features.cpu == 0.0
    assert features.memory_gb == 0.0
    assert features.total_cpu_capacity == 0.0
    assert features.users_per_replica == 1000.0
