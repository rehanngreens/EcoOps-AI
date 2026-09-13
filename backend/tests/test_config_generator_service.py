import pytest
import yaml

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.services.config_generator_service import (
    ConfigGenerationError,
    format_cpu,
    format_memory_gb,
    generate_optimized_config,
)

HEAVY_MANIFEST = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-backend
  namespace: ecommerce
spec:
  replicas: 8
  selector:
    matchLabels:
      app: api-backend
  template:
    metadata:
      labels:
        app: api-backend
    spec:
      containers:
        - name: api-backend
          image: ecommerce/api-backend:1.0.0
          resources:
            requests:
              cpu: "8"
              memory: 16Gi
            limits:
              cpu: "8"
              memory: 16Gi
"""


def _optimized(**overrides: object) -> InfrastructureConfiguration:
    # Defaults mirror what Phase 9 stores for the heavy baseline: requests
    # scaled to 4 cores, limits scaled proportionally (8 -> 4, 16 stays 16).
    values: dict = {
        "source_type": "kubernetes",
        "application": "api-backend",
        "namespace": "ecommerce",
        "replicas": 8,
        "cpu_request": 4.0,
        "cpu_limit": 4.0,
        "memory_request_gb": 16.0,
        "memory_limit_gb": 16.0,
        "autoscaling_enabled": False,
        "container_image": "ecommerce/api-backend:1.0.0",
    }
    values.update(overrides)
    return InfrastructureConfiguration(**values)  # type: ignore[arg-type]


def _baseline(**overrides: object) -> InfrastructureConfiguration:
    """Original heavy manifest as parsed (the limits authority)."""
    values: dict = {
        "source_type": "kubernetes",
        "application": "api-backend",
        "namespace": "ecommerce",
        "replicas": 8,
        "cpu_request": 8.0,
        "cpu_limit": 8.0,
        "memory_request_gb": 16.0,
        "memory_limit_gb": 16.0,
        "autoscaling_enabled": False,
        "container_image": "ecommerce/api-backend:1.0.0",
    }
    values.update(overrides)
    return InfrastructureConfiguration(**values)  # type: ignore[arg-type]


def test_format_cpu_variants() -> None:
    assert format_cpu(4.0) == "4"
    assert format_cpu(0.25) == "250m"
    assert format_cpu(0.5) == "500m"
    assert format_cpu(1.0) == "1"


def test_format_memory_variants() -> None:
    assert format_memory_gb(16.0) == "16Gi"
    assert format_memory_gb(0.5) == "512Mi"
    assert format_memory_gb(0.25) == "256Mi"
    assert format_memory_gb(8.0) == "8Gi"


def test_scaled_limit_never_below_request() -> None:
    from app.services.config_generator_service import _memory_scaled_limit, _scaled_limit

    assert _scaled_limit(8.0, 8.0, 4.0) == 4.0
    assert _scaled_limit(2.0, 8.0, 4.0) == 4.0  # clamped up to new request
    assert _scaled_limit(None, 8.0, 4.0) is None
    assert _memory_scaled_limit(16.0, 16.0, 8.0) == 8.0


def test_generate_applies_replica_change_and_produces_diff() -> None:
    optimized = _optimized(replicas=4)
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    assert "-  replicas: 8" in generated.diff_lines or "- replicas: 8" in generated.diff_lines
    assert any("replicas: 4" in line for line in generated.diff_lines if line.startswith("+"))
    parameters = [change["parameter"] for change in generated.changes]
    assert "replicas" in parameters


def test_generate_scales_limits_with_requests() -> None:
    optimized = _optimized(cpu_request=4.0, memory_request_gb=8.0, cpu_limit=4.0, memory_limit_gb=8.0)
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    document = yaml.safe_load(generated.optimized_yaml)
    resources = document["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"]["cpu"] == "4"
    assert resources["limits"]["cpu"] == "4"
    assert resources["requests"]["memory"] == "8Gi"
    assert resources["limits"]["memory"] == "8Gi"

    parameters = [change["parameter"] for change in generated.changes]
    assert "cpu_request" in parameters
    assert "cpu_limit" in parameters
    assert "memory_request_gb" in parameters
    assert "memory_limit_gb" in parameters


def test_limits_untouched_when_requests_equal_baseline() -> None:
    # A candidate that only reduces replicas leaves requests/limits alone.
    optimized = _optimized(
        replicas=4,
        cpu_request=8.0,
        cpu_limit=8.0,
        memory_request_gb=16.0,
        memory_limit_gb=16.0,
    )
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    parameters = [change["parameter"] for change in generated.changes]
    assert parameters == ["replicas"]
    document = yaml.safe_load(generated.optimized_yaml)
    resources = document["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"]["cpu"] == "8"
    assert resources["limits"]["cpu"] == "8"


def test_generate_millicore_and_mib_formatting() -> None:
    optimized = _optimized(cpu_request=0.5, cpu_limit=0.5, memory_request_gb=0.5, memory_limit_gb=0.5)
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    document = yaml.safe_load(generated.optimized_yaml)
    resources = document["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"]["cpu"] == "500m"
    assert resources["requests"]["memory"] == "512Mi"


def test_generate_autoscaling_annotation_round_trips() -> None:
    optimized = _optimized(autoscaling_enabled=True)
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    document = yaml.safe_load(generated.optimized_yaml)
    annotations = document["metadata"]["annotations"]
    assert annotations["ecoops.ai/autoscaling"] == "true"

    # Phase 2 parser must detect it.
    from app.parsers.kubernetes_parser import parse_kubernetes_yaml

    parsed = parse_kubernetes_yaml(generated.optimized_yaml)
    assert parsed["autoscaling_enabled"] is True


def test_round_trip_reproduces_optimized_configuration() -> None:
    optimized = _optimized(
        replicas=4, cpu_request=4.0, memory_request_gb=8.0, cpu_limit=4.0, memory_limit_gb=8.0
    )
    generated = generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())

    from app.parsers.kubernetes_parser import parse_kubernetes_yaml

    parsed = parse_kubernetes_yaml(generated.optimized_yaml)
    assert parsed == optimized.model_dump()

    from app.parsers.kubernetes_parser import parse_kubernetes_yaml

    parsed = parse_kubernetes_yaml(generated.optimized_yaml)
    assert parsed == optimized.model_dump()


def test_original_text_is_unchanged() -> None:
    optimized = _optimized(replicas=2)
    before = HEAVY_MANIFEST
    generate_optimized_config(HEAVY_MANIFEST, optimized, _baseline())
    assert HEAVY_MANIFEST == before


def test_multi_document_yaml_uses_first_deployment() -> None:
    multi = (
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: svc\n---\n" + HEAVY_MANIFEST
    )
    generated = generate_optimized_config(multi, _optimized(replicas=4), _baseline())
    document = yaml.safe_load(generated.optimized_yaml)
    assert document["kind"] == "Deployment"


def test_invalid_original_raises() -> None:
    with pytest.raises(ConfigGenerationError, match="no Deployment"):
        generate_optimized_config("kind: Service\nmetadata:\n  name: x", _optimized(), _baseline())


def test_canonical_fallback_for_legacy_analysis() -> None:
    optimized = _optimized()
    generated = generate_optimized_config(None, optimized)

    assert generated.diff_lines == []  # original == optimized in fallback
    assert yaml.safe_load(generated.optimized_yaml)["kind"] == "Deployment"
    from app.parsers.kubernetes_parser import parse_kubernetes_yaml

    assert parse_kubernetes_yaml(generated.optimized_yaml) == optimized.model_dump()
