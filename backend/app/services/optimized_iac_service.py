"""Phase 18 full integration: optimized IaC for Terraform and Docker Compose.

Phase 10 shipped optimized-manifest generation for Kubernetes sources only;
Terraform and Docker Compose analyses were rejected with an explicit 400
"until Phase 16". Phase 16 now provides exactly the missing machinery —
deterministic per-target templates and mandatory round-trip validation
through the same parser that handles user uploads — so this service closes
the gap by REUSE, not reimplementation:

- Terraform: the stored optimized configuration is rendered through the
  Phase 16 Terraform template (instance type via the shared metadata
  selector, count → replicas, root volume → storage) and re-parsed through
  the Phase 12 parser.
- Docker Compose: rendered through the Phase 16 Compose template
  (deploy.replicas, v3 deploy.resources) and re-parsed through the Phase
  13 parser.
- Kubernetes: the existing Phase 10 path is untouched.

The Phase 10 guarantees are inherited unchanged: the original upload text is
NEVER modified (the diff is computed against the stored original), and an
artifact that fails its round trip raises instead of being returned.
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field

from app.parsers.aws_instance_metadata import (
    get_instance_type,
    smallest_covering_instance_type,
)
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.services.generation.iac_generation_service import (
    _COMPOSE_ROUND_TRIP_FIELDS,
    _K8S_ROUND_TRIP_FIELDS,
    _TF_ROUND_TRIP_FIELDS,
    _normalize_for_render,
    _validate_docker_compose,
    _validate_kubernetes,
    _validate_terraform,
)
from app.services.generation.iac_templates import (
    render_docker_compose,
    render_terraform,
)

# Public aliases: the per-target field sets each parser actually emits,
# re-exported so tests and callers can share the Phase 16 definitions.
SOURCE_ROUND_TRIP_FIELDS = {
    "kubernetes": _K8S_ROUND_TRIP_FIELDS,
    "terraform": _TF_ROUND_TRIP_FIELDS,
    "docker_compose": _COMPOSE_ROUND_TRIP_FIELDS,
}

_RENDERABLE_SOURCES = ("kubernetes", "terraform", "docker_compose")

OPTIMIZED_IAC_DISCLAIMER = (
    "The optimized configuration is a proposal generated from advisory "
    "estimates. The original configuration is preserved unchanged; review "
    "the diff and deploy manually only if you accept it."
)


class OptimizedIaCError(RuntimeError):
    """Raised when an optimized artifact fails its round-trip validation."""


@dataclass(frozen=True)
class RenderedOptimizedIaC:
    """One rendered optimized artifact, validated but not yet diffed."""

    filename: str
    content: str
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedIaC:
    """The route-level result: artifact text, diff against the original, changes."""

    filename: str
    optimized_text: str
    diff_lines: list[str]
    notes: list[str] = field(default_factory=list)


def validate_rendered_for_source(
    content: str,
    expected: InfrastructureConfiguration,
    source_type: str,
) -> None:
    """Round-trip `content` through the source's parser and compare field sets.

    Delegates to the Phase 16 per-target validators (which already define the
    compared field sets and the autoscaling rules for non-Kubernetes targets).
    Raises OptimizedIaCError on any mismatch or parser failure.
    """
    try:
        if source_type == "kubernetes":
            mismatches = _validate_kubernetes(content, expected)
        elif source_type == "terraform":
            mismatches = _validate_terraform(content, expected)
        elif source_type == "docker_compose":
            mismatches = _validate_docker_compose(content, expected)
        else:
            raise OptimizedIaCError(
                f"Optimized configuration generation supports sources "
                f"{', '.join(_RENDERABLE_SOURCES)}; got '{source_type}'"
            )
    except OptimizedIaCError:
        raise
    except Exception as exc:  # parser errors are round-trip failures too
        raise OptimizedIaCError(
            f"Round-trip validation failed for {source_type}: {exc}"
        ) from exc
    if mismatches:
        raise OptimizedIaCError(
            f"Round-trip validation failed for {source_type}: " + "; ".join(mismatches)
        )


def _terraform_render_config(
    optimized: InfrastructureConfiguration,
) -> tuple[InfrastructureConfiguration, list[str]]:
    """Adapt a Mode A optimized configuration for Terraform rendering.

    The Phase 16 template emits literal instance-type values, and the Phase
    12 parser maps the type back to its EXACT metadata spec, so the render
    shape must be instance-shaped: the instance type must cover the sizing
    (re-selected when it does not) and cpu/memory are snapped to that
    type's discrete spec. Fractional storage is rounded up. Autoscaling is
    dropped (no Terraform semantics) via the shared Phase 16 normalizer.
    Every adaptation is returned as a visible note.
    """
    notes: list[str] = []
    update: dict = {}
    if optimized.autoscaling_enabled:
        update["autoscaling_enabled"] = False
        notes.append(
            "Autoscaling has no Terraform (aws_instance) semantics; the "
            "artifact provisions the recommended fixed replica count."
        )

    cpu = optimized.cpu_request
    memory = optimized.memory_request_gb
    instance_type = optimized.instance_type
    covered = False
    if instance_type:
        resolved = get_instance_type(instance_type)
        if resolved is not None:
            spec, warning = resolved
            if cpu is not None and spec.vcpu >= cpu and memory is not None and spec.memory_gib >= memory:
                covered = True
                if warning:
                    notes.append(warning)
            else:
                notes.append(
                    f"Instance type '{instance_type}' ({spec.vcpu} vCPU / "
                    f"{spec.memory_gib} GiB) does not cover the optimized "
                    "sizing; the smallest listed type covering it was "
                    "selected instead."
                )
        else:
            notes.append(
                f"Instance type '{instance_type}' is not in the metadata "
                "table; the smallest listed type covering the optimized "
                "sizing was selected."
            )

    if not covered:
        if cpu is None or memory is None:
            raise OptimizedIaCError(
                "The optimized configuration has no CPU/memory sizing to "
                "select a Terraform instance type from"
            )
        replacement = smallest_covering_instance_type(cpu, memory)
        if replacement is None:
            raise OptimizedIaCError(
                f"No instance type in the metadata table covers "
                f"{cpu:g} vCPU / {memory:g} GiB; refusing to emit an "
                "undersized Terraform configuration"
            )
        update["instance_type"] = replacement
        instance_type = replacement

    assert instance_type is not None
    spec = get_instance_type(instance_type)[0]  # type: ignore[index]
    if optimized.cpu_request != float(spec.vcpu) or optimized.memory_request_gb != float(
        spec.memory_gib
    ):
        notes.append(
            f"Per-replica sizing was mapped onto the discrete instance "
            f"type '{instance_type}' ({spec.vcpu} vCPU / {spec.memory_gib} "
            f"GiB); instance types are not continuously scalable."
        )
        update["cpu_request"] = float(spec.vcpu)
        update["memory_request_gb"] = float(spec.memory_gib)

    if optimized.storage_gb and optimized.storage_gb != int(optimized.storage_gb):
        update["storage_gb"] = float(math.ceil(optimized.storage_gb))
        notes.append(
            f"Storage was rounded up to a whole-number volume size "
            f"({math.ceil(optimized.storage_gb):g} GB)."
        )

    safe_name = (re.sub(r"[^A-Za-z0-9_-]", "-", optimized.application) or "app").strip("-") or "app"
    if safe_name != optimized.application:
        update["application"] = safe_name
        notes.append(
            f"The application name was mapped to the Terraform-resource-safe "
            f"identifier '{safe_name}'."
        )

    return (optimized.model_copy(update=update) if update else optimized), notes


def render_optimized_for_source(
    optimized: InfrastructureConfiguration,
    source_type: str,
) -> RenderedOptimizedIaC:
    """Render the optimized configuration as IaC for its own source format.

    Terraform and Docker Compose go through the Phase 16 templates; the
    templates' documented refusals (no covering instance type, non-AWS
    provider) propagate as OptimizedIaCError. Kubernetes rendering stays in
    the Phase 10 service (manifest-preserving rewrite), so it is out of
    scope here.
    """
    notes: list[str] = []
    if source_type == "terraform":
        render_config, notes = _terraform_render_config(optimized)
        try:
            content = render_terraform(render_config)
        except ValueError as exc:
            raise OptimizedIaCError(str(exc)) from exc
        filename = "main-optimized.tf"
    elif source_type == "docker_compose":
        render_config = _normalize_for_render(optimized, "docker_compose")
        if optimized.autoscaling_enabled:
            notes.append(
                "Autoscaling has no Docker Compose semantics; the artifact "
                "provisions the recommended fixed replica count."
            )
        if optimized.storage_gb:
            notes.append(
                f"The {optimized.storage_gb:g} GB storage setting is not "
                "expressible in a Compose service definition; it is noted "
                "here but not claimed."
            )
        content = render_docker_compose(render_config)
        filename = "docker-compose-optimized.yaml"
    else:
        raise OptimizedIaCError(
            f"Optimized configuration generation supports sources "
            f"{', '.join(_RENDERABLE_SOURCES)}; got '{source_type}'"
        )

    # Mandatory round-trip guarantee, identical in spirit to Mode B:
    # nothing unvalidated is ever returned. The comparison target is the
    # RENDER config — the artifact encodes the adapted values.
    validate_rendered_for_source(content, render_config, source_type)
    return RenderedOptimizedIaC(
        filename=filename, content=content, notes=notes
    )


def generate_optimized_iac(
    original_text: str | None,
    optimized: InfrastructureConfiguration,
    baseline: InfrastructureConfiguration,
    source_type: str,
) -> GeneratedIaC:
    """Render, round-trip-validate, and diff the optimized artifact.

    `original_text` is the stored upload; it is never modified — the diff is
    computed against it verbatim (empty-diff canonical fallback follows the
    Phase 10 convention when the stored text is missing/empty).
    """
    if source_type == "kubernetes":
        raise OptimizedIaCError(
            "Kubernetes optimized generation belongs to the Phase 10 service; "
            "this service handles Terraform and Docker Compose"
        )

    rendered = render_optimized_for_source(optimized, source_type)

    original = (original_text or "").strip()
    if original:
        diff_lines = list(
            difflib.unified_diff(
                (original_text or "").splitlines(),
                rendered.content.splitlines(),
                fromfile="original",
                tofile=f"optimized ({rendered.filename})",
                lineterm="",
            )
        )
    else:
        # Same legacy-analysis convention as Phase 10: no stored original
        # means the canonical view equals the optimized artifact.
        diff_lines = []

    return GeneratedIaC(
        filename=rendered.filename,
        optimized_text=rendered.content,
        diff_lines=diff_lines,
        notes=rendered.notes,
    )


__all__ = [
    "SOURCE_ROUND_TRIP_FIELDS",
    "GeneratedIaC",
    "OPTIMIZED_IAC_DISCLAIMER",
    "OptimizedIaCError",
    "RenderedOptimizedIaC",
    "generate_optimized_iac",
    "render_optimized_for_source",
    "validate_rendered_for_source",
]
