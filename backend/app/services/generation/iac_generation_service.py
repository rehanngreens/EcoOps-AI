"""Phase 16 IaC generation service (design doc section 44.6).

Renders the selected Mode B candidate through the deterministic templates
and MANDATORILY validates every artifact by parsing it back through the
SAME parser that handles user uploads of that format. The re-parsed
normalized configuration must reproduce the selected candidate's resource
fields exactly; any mismatch is a generation failure and nothing
unvalidated is returned. Execution remains forbidden (section 29) — this
validation is the strongest correctness guarantee available without
running anything.
"""

from __future__ import annotations

from uuid import uuid4

from app.parsers.docker_compose_parser import (
    DockerComposeParserError,
    parse_docker_compose,
)
from app.parsers.kubernetes_parser import (
    KubernetesParserError,
    parse_kubernetes_yaml,
)
from app.parsers.terraform_parser import TerraformParserError, parse_terraform

# A parser that RAISES is also a failed round trip; ValueError covers the
# templates' documented refusals (undersized/unrenderable shapes).
_PARSER_ERRORS = (
    KubernetesParserError,
    TerraformParserError,
    DockerComposeParserError,
    ValueError,
)
from app.schemas.generation_schema import (
    GeneratedArtifact,
    GenerationResult,
    TargetSelection,
)
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.services.generation.iac_templates import (
    render_docker_compose,
    render_kubernetes,
    render_terraform,
    render_terraform_plus_kubernetes,
)

DISCLAIMER = (
    "Generated configurations are advisory prototypes: review before use. "
    "EcoOps AI never deploys anything, and estimates shown alongside remain "
    "heuristic predictions, not guarantees."
)

# Fields compared after the round trip, per target (the fields each parser
# actually emits). Storage is Terraform-only; Compose/Terraform have no
# autoscaling semantics, so it must be False there.
_K8S_ROUND_TRIP_FIELDS = (
    "application",
    "namespace",
    "replicas",
    "cpu_request",
    "cpu_limit",
    "memory_request_gb",
    "memory_limit_gb",
    "autoscaling_enabled",
)
_TF_ROUND_TRIP_FIELDS = (
    "application",
    "replicas",
    "cpu_request",
    "memory_request_gb",
    "storage_gb",
)
_COMPOSE_ROUND_TRIP_FIELDS = (
    "application",
    "replicas",
    "cpu_request",
    "cpu_limit",
    "memory_request_gb",
    "memory_limit_gb",
)


class IaCGenerationError(RuntimeError):
    """Raised when a rendered artifact fails its round-trip validation."""


def _mismatches(
    parsed: dict,
    expected: InfrastructureConfiguration,
    fields: tuple[str, ...],
) -> list[str]:
    diffs: list[str] = []
    for field in fields:
        expected_value = getattr(expected, field)
        actual_value = parsed.get(field)
        if actual_value != expected_value:
            diffs.append(f"{field}: expected {expected_value!r}, round-trip gave {actual_value!r}")
    return diffs


def _validate_kubernetes(content: str, expected: InfrastructureConfiguration) -> list[str]:
    parsed = parse_kubernetes_yaml(content)
    return _mismatches(parsed, expected, _K8S_ROUND_TRIP_FIELDS)


def _validate_terraform(content: str, expected: InfrastructureConfiguration) -> list[str]:
    parsed = parse_terraform(content)
    diffs = _mismatches(parsed, expected, _TF_ROUND_TRIP_FIELDS)
    if parsed.get("autoscaling_enabled"):
        diffs.append("autoscaling_enabled: Terraform target must not claim autoscaling")
    return diffs


def _validate_docker_compose(content: str, expected: InfrastructureConfiguration) -> list[str]:
    parsed = parse_docker_compose(content)
    diffs = _mismatches(parsed, expected, _COMPOSE_ROUND_TRIP_FIELDS)
    if parsed.get("autoscaling_enabled"):
        diffs.append("autoscaling_enabled: Docker Compose target must not claim autoscaling")
    return diffs


def _normalize_for_render(config: InfrastructureConfiguration, target: str) -> InfrastructureConfiguration:
    """Per-target normalization so the round trip can succeed at all.

    - Autoscaling: only Kubernetes supports it — for other targets the flag
      is dropped (the artifact notes the limitation).
    - Container targets declare limits equal to requests (the templates'
      documented convention). VM-shaped candidates carry limits=None, so
      normalization synthesizes limit == request for container targets;
      the round trip then compares like with like.
    - Storage is Terraform-only (root_block_device) and is compared only
      for Terraform artifacts.
    """
    update: dict = {}
    if target in {"kubernetes", "docker_compose"}:
        if config.cpu_limit is None and config.cpu_request is not None:
            update["cpu_limit"] = config.cpu_request
        if config.memory_limit_gb is None and config.memory_request_gb is not None:
            update["memory_limit_gb"] = config.memory_request_gb
    if target in {"terraform", "docker_compose"} and config.autoscaling_enabled:
        update["autoscaling_enabled"] = False
    return config.model_copy(update=update) if update else config


def generate_artifacts(
    configuration: InfrastructureConfiguration,
    target_selection: TargetSelection,
) -> list[GeneratedArtifact]:
    """Render + round-trip-validate artifacts for the selected target."""
    target = target_selection.target
    validators = {
        "kubernetes": (_validate_kubernetes, "deployment.yaml"),
        "terraform": (_validate_terraform, "main.tf"),
        "docker_compose": (_validate_docker_compose, "docker-compose.yaml"),
    }

    artifacts: list[GeneratedArtifact] = []

    if target == "terraform+kubernetes":
        # One candidate, two artifacts: Terraform for provider resources
        # (VM shapes), Kubernetes for the workload. Each is validated with
        # its own parser. The K8s side mirrors the candidate's container
        # sizing; the Terraform side mirrors the VM-sized fields when the
        # candidate is a VM, else the same request values.
        tf_config = _normalize_for_render(configuration, "terraform")
        for filename, content in render_terraform_plus_kubernetes(tf_config):
            try:
                if filename.endswith(".tf"):
                    diffs = _validate_terraform(content, tf_config)
                else:
                    diffs = _validate_kubernetes(content, configuration)
            except _PARSER_ERRORS as exc:
                raise IaCGenerationError(
                    f"Round-trip validation failed for {filename}: {exc}"
                ) from exc
            if diffs:
                raise IaCGenerationError(
                    f"Round-trip validation failed for {filename}: " + "; ".join(diffs)
                )
            artifacts.append(
                GeneratedArtifact(
                    target="terraform+kubernetes",
                    filename=filename,
                    content=content,
                    round_trip_valid=True,
                )
            )
        return artifacts

    if target not in validators:
        raise IaCGenerationError(f"Unsupported generation target: {target}")

    validator, filename = validators[target]
    render_config = _normalize_for_render(configuration, target)
    if target == "kubernetes":
        content = render_kubernetes(render_config)
    elif target == "terraform":
        content = render_terraform(render_config)
    else:
        content = render_docker_compose(render_config)

    # A parser that RAISES is also a failed round trip: wrap it so callers
    # see one consistent generation-failure type.
    try:
        diffs = validator(content, render_config)
    except _PARSER_ERRORS as exc:
        raise IaCGenerationError(
            f"Round-trip validation failed for {filename}: {exc}"
        ) from exc
    if diffs:
        raise IaCGenerationError(
            f"Round-trip validation failed for {filename}: " + "; ".join(diffs)
        )

    notes: list[str] = []
    if configuration.autoscaling_enabled and target in {"terraform", "docker_compose"}:
        notes.append(
            "The selected candidate enables autoscaling, but this target has "
            "no autoscaling semantics; the artifact provisions fixed "
            "replicas at the availability minimum instead."
        )
    if configuration.storage_gb and target in {"kubernetes", "docker_compose"}:
        notes.append(
            f"The {configuration.storage_gb:g} GB storage requirement is a "
            "Terraform-level (volume) setting; container targets note it "
            "here but do not claim a persistent volume."
        )

    return [
        GeneratedArtifact(
            target=target,
            filename=filename,
            content=content,
            round_trip_valid=True,
            notes=notes,
        )
    ]


def build_generation_result(
    evaluation,
    target_selection: TargetSelection,
) -> GenerationResult:
    """Assemble the full Phase 15+16 result for the winning candidate."""
    if evaluation.status != "recommended" or evaluation.selected_index is None:
        raise IaCGenerationError(
            "No eligible candidate to generate infrastructure from; the "
            "generation failed as infeasible upstream of IaC rendering"
        )

    selected = evaluation.candidates[evaluation.selected_index]
    artifacts = generate_artifacts(selected.plan.configuration, target_selection)

    return GenerationResult(
        generation_id=str(uuid4()),
        evaluation=evaluation,
        target_selection=target_selection,
        artifacts=artifacts,
        selected_configuration=selected.plan.configuration,
        disclaimer=DISCLAIMER,
    )
