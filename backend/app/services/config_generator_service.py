"""Phase 10 optimized configuration generation.

Generates an optimized Kubernetes manifest from the stored original upload
and the accepted Phase 9 recommendation. The original text is never modified;
the optimized manifest is a parsed copy with only the recommended changes
applied. Every generated manifest must round-trip through the Phase 2
Kubernetes parser and reproduce the stored optimized configuration exactly,
otherwise generation raises and the route returns 503 rather than shipping
an inconsistent artifact (design doc section 21: never silently overwrite;
section 43: review, download, deploy manually).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

import yaml

from app.parsers.kubernetes_parser import KubernetesParserError, parse_kubernetes_yaml
from app.schemas.infrastructure_schema import InfrastructureConfiguration

AUTOSCALING_ANNOTATION_KEY = "ecoops.ai/autoscaling"


class ConfigGenerationError(RuntimeError):
    """Raised when a generated manifest fails round-trip validation."""


@dataclass(frozen=True)
class GeneratedConfig:
    optimized_yaml: str
    diff_lines: list[str]
    changes: list[dict[str, str]]


def format_cpu(cores: float) -> str:
    """Format CPU cores as a Kubernetes quantity (millicores when fractional)."""
    if cores == int(cores):
        return str(int(cores))
    millis = round(cores * 1000)
    return f"{millis}m"


def format_memory_gb(gb: float) -> str:
    """Format GiB as a Kubernetes quantity (whole GiB, else Mi)."""
    if gb == int(gb):
        return f"{int(gb)}Gi"
    mib = round(gb * 1024)
    return f"{mib}Mi"


def _scaled_limit(limit: float | None, old_request: float | None, new_request: float | None) -> float | None:
    """Scale a limit proportionally; the limit never drops below the new request."""
    if limit is None or old_request in (None, 0) or new_request is None:
        return limit
    ratio = new_request / old_request
    return max(new_request, round(limit * ratio * 1000) / 1000)


def _memory_scaled_limit(
    limit: float | None, old_request: float | None, new_request: float | None
) -> float | None:
    if limit is None or old_request in (None, 0) or new_request is None:
        return limit
    ratio = new_request / old_request
    return max(new_request, round(limit * ratio * 100) / 100)


def _apply_changes_to_document(
    document: dict,
    optimized: InfrastructureConfiguration,
    baseline: InfrastructureConfiguration | None = None,
) -> list[dict[str, str]]:
    """Mutate one Deployment document in place; return the applied change list."""
    changes: list[dict[str, str]] = []
    spec = document.setdefault("spec", {})
    template = spec.setdefault("template", {})
    template_spec = template.setdefault("spec", {})
    containers = template_spec.setdefault("containers", [])
    if not containers:
        raise ConfigGenerationError("Original manifest has no containers to update")
    resources = containers[0].setdefault("resources", {})

    old_replicas = spec.get("replicas", 1)
    if optimized.replicas != old_replicas:
        spec["replicas"] = optimized.replicas
        changes.append(
            {"parameter": "replicas", "from": str(old_replicas), "to": str(optimized.replicas)}
        )

    old_cpu_request = resources.get("requests", {}).get("cpu")
    old_cpu_request_cores = _parse_cpu_quantity(old_cpu_request)
    old_memory_request = resources.get("requests", {}).get("memory")
    old_memory_request_gb = _parse_memory_quantity(old_memory_request)

    if optimized.cpu_request is not None:
        requests = resources.setdefault("requests", {})
        new_value = format_cpu(optimized.cpu_request)
        request_changed = requests.get("cpu") != new_value
        if request_changed:
            changes.append(
                {
                    "parameter": "cpu_request",
                    "from": str(requests.get("cpu", "unset")),
                    "to": new_value,
                }
            )
            requests["cpu"] = new_value

        # Limits are derived from the BASELINE configuration (the authority
        # for original limits), scaled only when the request changed.
        if request_changed and baseline is not None and baseline.cpu_limit is not None:
            scaled = _scaled_limit(
                baseline.cpu_limit,
                baseline.cpu_request if baseline.cpu_request else optimized.cpu_request,
                optimized.cpu_request,
            )
            if scaled is not None:
                new_limit_value = format_cpu(scaled)
                if resources["limits"].get("cpu") != new_limit_value:
                    changes.append(
                        {
                            "parameter": "cpu_limit",
                            "from": str(resources.get("limits", {}).get("cpu")),
                            "to": new_limit_value,
                        }
                    )
                    resources["limits"]["cpu"] = new_limit_value

    if optimized.memory_request_gb is not None:
        requests = resources.setdefault("requests", {})
        new_value = format_memory_gb(optimized.memory_request_gb)
        request_changed = requests.get("memory") != new_value
        if request_changed:
            changes.append(
                {
                    "parameter": "memory_request_gb",
                    "from": str(requests.get("memory", "unset")),
                    "to": new_value,
                }
            )
            requests["memory"] = new_value

        if request_changed and baseline is not None and baseline.memory_limit_gb is not None:
            scaled = _memory_scaled_limit(
                baseline.memory_limit_gb,
                baseline.memory_request_gb if baseline.memory_request_gb else optimized.memory_request_gb,
                optimized.memory_request_gb,
            )
            if scaled is not None:
                new_limit_value = format_memory_gb(scaled)
                if resources["limits"].get("memory") != new_limit_value:
                    changes.append(
                        {
                            "parameter": "memory_limit_gb",
                            "from": str(resources.get("limits", {}).get("memory")),
                            "to": new_limit_value,
                        }
                    )
                    resources["limits"]["memory"] = new_limit_value

    metadata = document.setdefault("metadata", {})
    annotations = metadata.get("annotations") or {}
    current_annotation = str(annotations.get(AUTOSCALING_ANNOTATION_KEY, "false")).lower()
    wanted_annotation = str(optimized.autoscaling_enabled).lower()
    if current_annotation != wanted_annotation:
        # Only create the annotations mapping when a change is actually
        # needed, to avoid emitting noisy empty annotations in the output.
        metadata["annotations"] = {**annotations, AUTOSCALING_ANNOTATION_KEY: wanted_annotation}
        changes.append(
            {
                "parameter": "autoscaling_enabled",
                "from": current_annotation,
                "to": wanted_annotation,
            }
        )

    return changes


def _parse_cpu_quantity(value: object) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw.endswith("m"):
        try:
            return float(raw[:-1]) / 1000
        except ValueError:
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_memory_quantity(value: object) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    multipliers = {"Gi": 1.0, "Mi": 1 / 1024, "Ki": 1 / (1024 * 1024)}
    for suffix, factor in multipliers.items():
        if raw.endswith(suffix):
            try:
                return float(raw[: -len(suffix)]) * factor
            except ValueError:
                return None
    try:
        return float(raw)
    except ValueError:
        return None


def _find_deployment_documents(raw_yaml: str) -> list[dict]:
    documents = list(yaml.safe_load_all(raw_yaml))
    return [doc for doc in documents if isinstance(doc, dict) and doc.get("kind") == "Deployment"]


def generate_optimized_config(
    original_yaml: str | None,
    optimized: InfrastructureConfiguration,
    baseline: InfrastructureConfiguration | None = None,
) -> GeneratedConfig:
    """Generate the optimized manifest and validate it round-trips."""
    if original_yaml and original_yaml.strip():
        documents = _find_deployment_documents(original_yaml)
        if not documents:
            raise ConfigGenerationError("Original upload contains no Deployment manifest")
        if len(documents) > 1:
            # Apply to the first Deployment; document which documents exist.
            pass
        deployment = documents[0]
        original_text = original_yaml
        source = "stored_original"
    else:
        # Canonical fallback for analyses stored before Phase 10: build the
        # manifest directly from the stored optimized configuration so the
        # round-trip guarantee still holds.
        deployment = _rebuild_original_from_baseline_needed(optimized)
        original_text = yaml.dump(deployment, sort_keys=False)
        source = "canonical"

    changes = _apply_changes_to_document(deployment, optimized, baseline)

    optimized_text = yaml.dump(deployment, sort_keys=False)
    diff_lines = list(
        difflib.unified_diff(
            original_text.splitlines(),
            optimized_text.splitlines(),
            fromfile="original",
            tofile="optimized",
            lineterm="",
        )
    )

    # Round-trip guarantee: the generated YAML must reproduce exactly the
    # stored optimized configuration through the Phase 2 parser.
    try:
        reparsed = parse_kubernetes_yaml(optimized_text)
    except KubernetesParserError as exc:
        raise ConfigGenerationError(f"Generated YAML failed to parse: {exc}") from exc

    expected = optimized.model_dump()
    mismatches = [
        f"{key}: generated={reparsed.get(key)!r} expected={value!r}"
        for key, value in expected.items()
        if reparsed.get(key) != value
    ]
    if mismatches:
        raise ConfigGenerationError(
            "Generated YAML does not match the accepted recommendation: "
            + "; ".join(mismatches)
        )

    return GeneratedConfig(
        optimized_yaml=optimized_text,
        diff_lines=diff_lines,
        changes=changes,
    )


def _rebuild_original_from_baseline_needed(
    optimized: InfrastructureConfiguration,
) -> dict:
    """Canonical original fallback: same shape but with current-values unknown.

    The stored optimized configuration is the only state available, so the
    canonical 'original' equals the optimized manifest; the diff will be
    empty. This preserves API shape for legacy analyses.
    """
    limits: dict[str, str] = {}
    if optimized.cpu_limit is not None:
        limits["cpu"] = format_cpu(optimized.cpu_limit)
    if optimized.memory_limit_gb is not None:
        limits["memory"] = format_memory_gb(optimized.memory_limit_gb)

    requests_section: dict[str, str] = {
        "cpu": format_cpu(optimized.cpu_request or 0.25),
        "memory": format_memory_gb(optimized.memory_request_gb or 0.25),
    }
    resources_section: dict[str, object] = {"requests": requests_section}
    if limits:
        resources_section["limits"] = limits

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": optimized.application,
            "namespace": optimized.namespace,
            "annotations": {AUTOSCALING_ANNOTATION_KEY: str(optimized.autoscaling_enabled).lower()},
        },
        "spec": {
            "replicas": optimized.replicas,
            "selector": {"matchLabels": {"app": optimized.application}},
            "template": {
                "metadata": {"labels": {"app": optimized.application}},
                "spec": {
                    "containers": [
                        {
                            "name": optimized.application,
                            "image": optimized.container_image or f"{optimized.application}:latest",
                            "resources": resources_section,
                        }
                    ]
                },
            },
        },
    }
