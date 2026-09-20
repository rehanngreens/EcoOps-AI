"""Phase 13 Docker Compose parser: services -> normalized features.

Converts a Docker Compose file into the same normalized representation the
Kubernetes and Terraform parsers produce, so the downstream ML prediction,
estimation, constraint, and scoring pipeline stays source-agnostic (design
doc section 8).

Documented subset:

- ``services.<name>`` -> application name; ``image:`` -> container_image;
  ``source_type: "docker_compose"``.
- Replicas from ``deploy.replicas`` (Compose v3), default 1. Compose has no
  built-in autoscaling, so ``autoscaling_enabled`` is always ``false``.
- Resource limits/requests, two syntax generations:
  * v3: ``deploy.resources.limits.cpus/.memory`` and
    ``deploy.resources.reservations.cpus/.memory``
  * v2 style (still accepted): top-level ``cpus:`` and ``mem_limit:``
- Memory values follow Docker semantics: ``512M``, ``1g``, ``1gb``, or a
  plain byte count (``1073741824``). Suffixes are interpreted as BINARY
  units (``1g`` = 1 GiB = 1073741824 bytes), which matches how Docker
  enforces ``mem_limit``. CPU values are decimal cores (``"1.5"``).

Multi-service files are the Compose norm (app + db + redis), so unlike the
Terraform parser we do NOT reject them. A single analysis normalizes ONE
service: the PRIMARY service is the first one declaring any resource
constraint (cpus / mem_limit / deploy.resources), else the first service.
The choice is recorded in ``parser_warnings`` together with the full
service list, so it is never silent.

``version:`` is an obsolete no-op and is ignored. Named volumes carry no
size information, so storage stays ``None`` (no invention).
"""

from __future__ import annotations

import re
from typing import Any

import yaml

_MEMORY_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([kmgt]?)(b?)$", re.IGNORECASE)

# Binary multipliers, as Docker interprets memory suffixes.
_MEMORY_MULTIPLIERS: dict[str, int] = {
    "": 1,
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    "t": 1024**4,
}


class DockerComposeParserError(ValueError):
    """Raised when a Compose file cannot be parsed into normalized features."""


def parse_docker_compose(compose_text: str) -> dict[str, Any]:
    """Parse Compose YAML text and return normalized infrastructure features."""
    document = _load_document(compose_text)
    services = _extract_services(document)
    service_name, service = _select_primary_service(services)
    return _parse_service(service_name, service, services)


def validate_docker_compose(compose_text: str) -> list[str]:
    """Return a list of validation errors; empty list means the file is valid."""
    try:
        parse_docker_compose(compose_text)
    except DockerComposeParserError as exc:
        return [str(exc)]
    return []


def _load_document(compose_text: str) -> dict[str, Any]:
    if not compose_text.strip():
        raise DockerComposeParserError("Compose content is empty")

    try:
        document = yaml.safe_load(compose_text)
    except yaml.YAMLError as exc:
        raise DockerComposeParserError(f"Invalid YAML syntax: {exc}") from exc

    if not isinstance(document, dict):
        raise DockerComposeParserError(
            "Compose file must be a YAML mapping with a 'services' section"
        )
    return document


def _extract_services(document: dict[str, Any]) -> dict[str, Any]:
    services = document.get("services")
    if services is None:
        raise DockerComposeParserError(
            "No 'services' section found in Compose file"
        )
    if not isinstance(services, dict):
        raise DockerComposeParserError("'services' must be a mapping of service names")
    if not services:
        raise DockerComposeParserError("'services' section is empty")
    return services


def _select_primary_service(services: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Pick the analyzed service: first with resource constraints, else first."""
    constrained = [
        (name, service)
        for name, service in services.items()
        if isinstance(service, dict) and _has_resource_constraints(service)
    ]
    if constrained:
        return constrained[0]

    for name, service in services.items():
        if isinstance(service, dict):
            return name, service
    raise DockerComposeParserError(
        "No valid service definitions found under 'services'"
    )


def _has_resource_constraints(service: dict[str, Any]) -> bool:
    deploy = service.get("deploy") or {}
    resources = deploy.get("resources") or {}
    if resources.get("limits") or resources.get("reservations"):
        return True
    return "cpus" in service or "mem_limit" in service


def _parse_service(
    service_name: str,
    service: dict[str, Any],
    services: dict[str, Any],
) -> dict[str, Any]:
    deploy = service.get("deploy") or {}
    resources = deploy.get("resources") or {}
    limits = resources.get("limits") or {}
    reservations = resources.get("reservations") or {}

    replicas = deploy.get("replicas", 1)
    if not isinstance(replicas, int) or replicas < 1:
        raise DockerComposeParserError(
            f"Service '{service_name}': deploy.replicas must be a positive integer "
            f"(got {replicas!r})"
        )

    cpu_limit = _first_cpu(limits.get("cpus"), service.get("cpus"))
    cpu_request = _first_cpu(reservations.get("cpus"))
    memory_limit_gb = _first_memory(limits.get("memory"), service.get("mem_limit"))
    memory_request_gb = _first_memory(reservations.get("memory"))

    image = service.get("image")

    warnings: list[str] = []
    all_names = list(services.keys())
    if len(all_names) > 1:
        analyzed = "first service with resource constraints" if _has_resource_constraints(service) else "first service"
        warnings.append(
            f"Multi-service Compose file: analyzed the primary service "
            f"'{service_name}' ({analyzed}); all services: {', '.join(all_names)}. "
            "EcoOps AI normalizes one service per analysis."
        )

    result: dict[str, Any] = {
        "source_type": "docker_compose",
        "application": service_name,
        "namespace": "default",
        "replicas": replicas,
        "cpu_request": cpu_request,
        "cpu_limit": cpu_limit,
        "memory_request_gb": memory_request_gb,
        "memory_limit_gb": memory_limit_gb,
        # Compose has no native autoscaling; nothing to detect honestly.
        "autoscaling_enabled": False,
        "container_image": image if isinstance(image, str) else None,
        "storage_gb": None,
    }
    if warnings:
        result["parser_warnings"] = warnings
    return result


def _first_cpu(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        return _parse_cpu(value)
    return None


def _first_memory(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        return _parse_memory_gb(value)
    return None


def _parse_cpu(value: Any) -> float:
    if isinstance(value, (int, float)):
        cores = float(value)
    else:
        try:
            cores = float(str(value).strip())
        except ValueError as exc:
            raise DockerComposeParserError(
                f"Invalid CPU value: {value!r} (expected decimal cores, e.g. 1.5)"
            ) from exc
    if cores <= 0:
        raise DockerComposeParserError(
            f"CPU value must be positive (got {value!r})"
        )
    return cores


def _parse_memory_gb(value: Any) -> float:
    """Parse a Docker-style memory value into GiB (binary suffix semantics)."""
    if isinstance(value, (int, float)):
        return float(value) / _MEMORY_MULTIPLIERS["g"]

    raw = str(value).strip()
    match = _MEMORY_PATTERN.match(raw)
    if match is None:
        raise DockerComposeParserError(
            f"Invalid memory value: {value!r} (expected forms like 512M, 1g, 1gb, "
            "or a byte count)"
        )
    amount = float(match.group(1))
    suffix = match.group(2).lower()
    bytes_value = amount * _MEMORY_MULTIPLIERS[suffix]
    return bytes_value / _MEMORY_MULTIPLIERS["g"]
