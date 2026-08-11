"""Parse Kubernetes Deployment manifests into normalized infrastructure features."""

from __future__ import annotations

import re
from typing import Any

import yaml

SUPPORTED_KIND = "Deployment"
PRIMARY_CONTAINER_INDEX = 0

_BINARY_MEMORY_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)?)(Ki|Mi|Gi|Ti|Pi|Ei)?$",
    re.IGNORECASE,
)
_DECIMAL_MEMORY_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)?)(K|M|G|T|P|E)?$",
    re.IGNORECASE,
)
_CPU_MILLICORES_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)m$", re.IGNORECASE)

_BINARY_MULTIPLIERS = {
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
}
_DECIMAL_MULTIPLIERS = {
    "K": 1000,
    "M": 1000**2,
    "G": 1000**3,
    "T": 1000**4,
    "P": 1000**5,
    "E": 1000**6,
}


class KubernetesParserError(ValueError):
    """Raised when a manifest cannot be parsed into normalized features."""


def parse_kubernetes_yaml(yaml_text: str) -> dict[str, Any]:
    """Parse YAML text for a Deployment and return normalized infrastructure features."""
    documents = _load_documents(yaml_text)
    deployment = _find_deployment(documents)
    return _parse_deployment(deployment)


def validate_kubernetes_yaml(yaml_text: str) -> list[str]:
    """Return a list of validation errors; empty list means the manifest is valid."""
    try:
        parse_kubernetes_yaml(yaml_text)
    except KubernetesParserError as exc:
        return [str(exc)]
    return []


def _load_documents(yaml_text: str) -> list[Any]:
    if not yaml_text.strip():
        raise KubernetesParserError("YAML content is empty")

    try:
        documents = list(yaml.safe_load_all(yaml_text))
    except yaml.YAMLError as exc:
        raise KubernetesParserError(f"Invalid YAML syntax: {exc}") from exc

    if not documents or all(doc is None for doc in documents):
        raise KubernetesParserError("YAML content is empty")

    return documents


def _find_deployment(documents: list[Any]) -> dict[str, Any]:
    for document in documents:
        if not isinstance(document, dict):
            continue
        if document.get("kind") == SUPPORTED_KIND:
            return document

    kinds = [
        doc.get("kind")
        for doc in documents
        if isinstance(doc, dict) and doc.get("kind")
    ]
    if kinds:
        raise KubernetesParserError(
            f"Unsupported resource kind(s): {', '.join(str(kind) for kind in kinds)}. "
            f"Only {SUPPORTED_KIND} is supported in the MVP parser."
        )
    raise KubernetesParserError(f"No {SUPPORTED_KIND} resource found in YAML")


def _parse_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
    metadata = deployment.get("metadata") or {}
    spec = deployment.get("spec") or {}
    template_spec = (spec.get("template") or {}).get("spec") or {}
    containers = template_spec.get("containers") or []

    application = metadata.get("name")
    if not application:
        raise KubernetesParserError("Deployment metadata.name is required")

    if not containers:
        raise KubernetesParserError("Deployment must define at least one container")

    primary_container = containers[PRIMARY_CONTAINER_INDEX]
    resources = primary_container.get("resources") or {}
    requests = resources.get("requests") or {}
    limits = resources.get("limits") or {}

    return {
        "source_type": "kubernetes",
        "application": application,
        "namespace": metadata.get("namespace") or "default",
        "replicas": spec.get("replicas", 1),
        "cpu_request": _parse_cpu(requests.get("cpu")),
        "cpu_limit": _parse_cpu(limits.get("cpu")),
        "memory_request_gb": _parse_memory_gb(requests.get("memory")),
        "memory_limit_gb": _parse_memory_gb(limits.get("memory")),
        "autoscaling_enabled": _detect_autoscaling(deployment),
        "container_image": primary_container.get("image"),
    }


def _detect_autoscaling(deployment: dict[str, Any]) -> bool:
    metadata = deployment.get("metadata") or {}
    annotations = metadata.get("annotations") or {}
    for key, value in annotations.items():
        if "autoscaling" in key.lower() and str(value).lower() in {"true", "enabled", "yes"}:
            return True
    return False


def _parse_cpu(value: str | int | float | None) -> float | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    millicores_match = _CPU_MILLICORES_PATTERN.match(raw)
    if millicores_match:
        return float(millicores_match.group(1)) / 1000

    try:
        return float(raw)
    except ValueError as exc:
        raise KubernetesParserError(f"Invalid CPU value: {value}") from exc


def _parse_memory_gb(value: str | int | float | None) -> float | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    binary_match = _BINARY_MEMORY_PATTERN.match(raw)
    if binary_match:
        amount = float(binary_match.group(1))
        suffix = binary_match.group(2)
        if suffix:
            normalized_suffix = suffix[0].upper() + suffix[1:].lower()
            if normalized_suffix not in _BINARY_MULTIPLIERS:
                raise KubernetesParserError(f"Invalid memory value: {value}")
            bytes_value = amount * _BINARY_MULTIPLIERS[normalized_suffix]
            return bytes_value / _BINARY_MULTIPLIERS["Gi"]
        return amount / _BINARY_MULTIPLIERS["Gi"]

    decimal_match = _DECIMAL_MEMORY_PATTERN.match(raw)
    if decimal_match:
        amount = float(decimal_match.group(1))
        suffix = decimal_match.group(2)
        if suffix:
            suffix = suffix.upper()
            if suffix not in _DECIMAL_MULTIPLIERS:
                raise KubernetesParserError(f"Invalid memory value: {value}")
            bytes_value = amount * _DECIMAL_MULTIPLIERS[suffix]
            return bytes_value / _BINARY_MULTIPLIERS["Gi"]
        return amount / _BINARY_MULTIPLIERS["Gi"]

    raise KubernetesParserError(f"Invalid memory value: {value}")
