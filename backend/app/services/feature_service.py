"""Build unified and ML-ready features from infrastructure and workload inputs."""

from __future__ import annotations

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.unified_schema import FeatureVector, UnifiedConfiguration
from app.schemas.workload_schema import TrafficLevel, WorkloadProfile

APPLICATION_TYPE_CODES: dict[str, int] = {
    "web-application": 1,
    "e-commerce": 2,
    "rest-api": 3,
    "database": 4,
    "machine-learning": 5,
    "ai-inference": 6,
    "streaming": 7,
    "batch": 8,
    "microservices": 9,
}

TRAFFIC_SCORES: dict[TrafficLevel, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "variable": 4,
}


def build_unified_configuration(
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
) -> UnifiedConfiguration:
    """Merge parsed infrastructure with workload profile fields."""
    cpu = configuration.cpu_request if configuration.cpu_request is not None else 0.0
    memory_gb = (
        configuration.memory_request_gb
        if configuration.memory_request_gb is not None
        else 0.0
    )

    return UnifiedConfiguration(
        application_type=workload.application_type,
        expected_users=workload.expected_users,
        traffic_level=workload.traffic_level,
        max_latency_ms=workload.max_latency_ms,
        availability_target=workload.availability_target,
        cpu=cpu,
        memory_gb=memory_gb,
        replicas=configuration.replicas,
        storage_gb=None,
        autoscaling_enabled=configuration.autoscaling_enabled,
        source_type=configuration.source_type,
    )


def extract_features(
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
) -> FeatureVector:
    """Produce a flat feature vector for ML from infra + workload."""
    unified = build_unified_configuration(configuration, workload)
    replicas = max(unified.replicas, 1)

    return FeatureVector(
        application_type=unified.application_type,
        application_type_code=APPLICATION_TYPE_CODES[unified.application_type],
        expected_users=unified.expected_users,
        traffic_level=unified.traffic_level,
        traffic_score=TRAFFIC_SCORES[unified.traffic_level],
        max_latency_ms=unified.max_latency_ms,
        availability_target=unified.availability_target,
        cpu=unified.cpu,
        memory_gb=unified.memory_gb,
        replicas=unified.replicas,
        storage_gb=unified.storage_gb,
        autoscaling_enabled=unified.autoscaling_enabled,
        autoscaling_enabled_int=int(unified.autoscaling_enabled),
        source_type=unified.source_type,
        total_cpu_capacity=unified.cpu * unified.replicas,
        total_memory_capacity=unified.memory_gb * unified.replicas,
        users_per_replica=unified.expected_users / replicas,
    )
