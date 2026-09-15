"""Tests for the Phase 13 Docker Compose parser."""

import pytest

from app.parsers.docker_compose_parser import (
    DockerComposeParserError,
    parse_docker_compose,
    validate_docker_compose,
)
from tests.conftest import load_compose

WELL_EXPECTED = {
    "source_type": "docker_compose",
    "application": "api-backend",
    "namespace": "default",
    "replicas": 2,
    "cpu_request": 0.5,
    "cpu_limit": 1.0,
    "memory_request_gb": 0.5,
    "memory_limit_gb": 1.0,
    "autoscaling_enabled": False,
    "container_image": "ecommerce/api-backend:1.0.0",
    "storage_gb": None,
}

HEAVY_EXPECTED = {
    "source_type": "docker_compose",
    "application": "api-backend",
    "namespace": "default",
    "replicas": 8,
    "cpu_request": 8.0,
    "cpu_limit": 8.0,
    "memory_request_gb": 16.0,
    "memory_limit_gb": 16.0,
    "autoscaling_enabled": False,
    "container_image": "ecommerce/api-backend:1.0.0",
    "storage_gb": None,
    # Multi-service demo: the primary-service choice must be visible.
    "parser_warnings": [
        "Multi-service Compose file: analyzed the primary service "
        "'api-backend' (first service with resource constraints); "
        "all services: api-backend, redis. EcoOps AI normalizes "
        "one service per analysis."
    ],
}


@pytest.mark.parametrize(
    ("manifest_name", "expected"),
    [
        ("compose-well-provisioned.yaml", WELL_EXPECTED),
        ("compose-heavy-overprovisioned.yaml", HEAVY_EXPECTED),
    ],
)
def test_parse_sample_configurations(manifest_name: str, expected: dict) -> None:
    assert parse_docker_compose(load_compose(manifest_name)) == expected


def test_moderate_demo_parses() -> None:
    result = parse_docker_compose(load_compose("compose-moderate-overprovisioned.yaml"))
    assert result["replicas"] == 4
    assert result["cpu_request"] == 2.0
    assert result["memory_request_gb"] == 4.0


def test_multi_service_file_records_primary_service_warning() -> None:
    result = parse_docker_compose(load_compose("compose-heavy-overprovisioned.yaml"))
    warnings = result["parser_warnings"]
    assert len(warnings) == 1
    assert "api-backend" in warnings[0]
    assert "redis" in warnings[0]
    assert "resource constraints" in warnings[0]


def test_v2_style_syntax_maps_to_limits() -> None:
    compose_text = """
services:
  worker:
    image: worker:1.0
    cpus: 2
    mem_limit: 4g
"""
    result = parse_docker_compose(compose_text)
    assert result["cpu_limit"] == 2.0
    assert result["cpu_request"] is None
    assert result["memory_limit_gb"] == 4.0
    assert result["memory_request_gb"] is None
    assert result["replicas"] == 1
    assert "parser_warnings" not in result


def test_memory_unit_variants_are_binary() -> None:
    compose_text = """
services:
  app:
    image: app:1.0
    mem_limit: 1073741824
"""
    assert parse_docker_compose(compose_text)["memory_limit_gb"] == 1.0

    compose_text = """
services:
  app:
    image: app:1.0
    mem_limit: 1gb
"""
    assert parse_docker_compose(compose_text)["memory_limit_gb"] == 1.0

    compose_text = """
services:
  app:
    image: app:1.0
    mem_limit: 512M
"""
    assert parse_docker_compose(compose_text)["memory_limit_gb"] == 0.5


def test_version_key_is_ignored() -> None:
    compose_text = """
version: "3.8"
services:
  app:
    image: app:1.0
    deploy:
      replicas: 3
"""
    result = parse_docker_compose(compose_text)
    assert result["replicas"] == 3
    assert result["container_image"] == "app:1.0"


def test_single_unconstrained_service_is_primary() -> None:
    compose_text = """
services:
  web:
    image: web:1.0
"""
    result = parse_docker_compose(compose_text)
    assert result["application"] == "web"
    assert result["cpu_limit"] is None
    assert result["memory_limit_gb"] is None


def test_constrained_service_wins_over_first() -> None:
    compose_text = """
services:
  sidecar:
    image: sidecar:1.0
  app:
    image: app:1.0
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4g
"""
    result = parse_docker_compose(compose_text)
    assert result["application"] == "app"
    assert result["cpu_limit"] == 2.0


def test_invalid_memory_value_is_rejected() -> None:
    compose_text = """
services:
  app:
    image: app:1.0
    mem_limit: lots
"""
    with pytest.raises(DockerComposeParserError, match="Invalid memory value"):
        parse_docker_compose(compose_text)


def test_invalid_cpu_value_is_rejected() -> None:
    compose_text = """
services:
  app:
    image: app:1.0
    cpus: many
"""
    with pytest.raises(DockerComposeParserError, match="Invalid CPU value"):
        parse_docker_compose(compose_text)


def test_non_positive_cpu_is_rejected() -> None:
    compose_text = """
services:
  app:
    image: app:1.0
    cpus: 0
"""
    with pytest.raises(DockerComposeParserError, match="positive"):
        parse_docker_compose(compose_text)


def test_bad_replicas_is_rejected() -> None:
    compose_text = """
services:
  app:
    image: app:1.0
    deploy:
      replicas: zero
"""
    with pytest.raises(DockerComposeParserError, match="replicas"):
        parse_docker_compose(compose_text)


def test_no_services_section_is_rejected() -> None:
    with pytest.raises(DockerComposeParserError, match="'services' section"):
        parse_docker_compose("version: '3.8'\nvolumes:\n  data:\n")


def test_empty_services_is_rejected() -> None:
    with pytest.raises(DockerComposeParserError, match="empty"):
        parse_docker_compose("services: {}\n")


def test_non_mapping_document_is_rejected() -> None:
    with pytest.raises(DockerComposeParserError, match="YAML mapping"):
        parse_docker_compose("- just\n- a\n- list\n")


def test_invalid_yaml_is_rejected() -> None:
    with pytest.raises(DockerComposeParserError, match="Invalid YAML syntax"):
        parse_docker_compose("services: [unclosed")


def test_validate_returns_error_list() -> None:
    assert validate_docker_compose("not: a: valid: compose: file: with: no services") != []
    compose_text = """
services:
  app:
    image: app:1.0
"""
    assert validate_docker_compose(compose_text) == []
