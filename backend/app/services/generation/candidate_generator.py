"""Phase 15 candidate generation (design doc section 44.2).

Turns a Phase 14 resource-requirement estimate into a SMALL, deterministic
set of concrete candidate configurations. Candidates vary along the three
design axes (sizing, replica strategy, storage) plus one platform-comparison
candidate (Terraform-style VM baseline). Every candidate is a NORMALIZED
InfrastructureConfiguration — the same schema Mode A parsers produce — so
downstream, candidates are indistinguishable from parsed infrastructure.

This module is PURE: functions in, list of plans out. No ML, no DB, no I/O.
Deduplication and the 3-6 bound follow section 44.2 ("target 3-6, never
more than ~10"). Deterministic given the same inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.parsers.aws_instance_metadata import (
    get_instance_type,
    smallest_covering_instance_type,
)
from app.schemas.generation_schema import CandidatePlan, ResourceRequirementsModel
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.requirement_engine import (
    CPU_LADDER,
    MEMORY_LADDER,
    ResourceRequirements,
    estimate_requirements,
)

# Minimum viable per-replica sizes (same floors as the Phase 9 generator).
CPU_FLOOR_CORES = 0.25
MEMORY_FLOOR_GB = 0.25

# VM baseline defaults (documented prototype constants; region has no
# existing setting, so it lives here rather than being invented per call).
VM_BASELINE_PROVIDER = "aws"
VM_BASELINE_REGION = "us-east-1"

# Application types that must keep full requested storage (section 44.2).
STORAGE_CRITICAL_TYPES = {"database", "streaming"}

# Instance families searched for the VM baseline live in
# aws_instance_metadata (_FAMILY_PREFERENCE) alongside the table itself.

# Storage steps for the economy variant (GB, documented ladder).
STORAGE_LADDER: tuple[float, ...] = (
    1.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0,
)


@dataclass(frozen=True)
class GenerationPreferences:
    """Optional cloud/deployment preferences for Mode B (Phase 17 form).

    Only the VM baseline consumes provider/region defaults today; the object
    exists so Phase 16 target selection and templates can reuse it.
    """

    cloud_provider: str | None = None
    region: str | None = None


def _ladder_step(ladder: tuple[float, ...], value: float, offset: int) -> float:
    """The ladder entry `offset` steps from the smallest entry >= value.

    offset=-1 rounds DOWN one step (floored at ladder[0]); offset=+1 rounds
    UP one step (clamped at the top). offset=0 is the round-up entry.
    """
    index = 0
    for i, step in enumerate(ladder):
        if value <= step:
            index = i
            break
    else:
        index = len(ladder) - 1
    index = max(0, min(len(ladder) - 1, index + offset))
    return ladder[index]


def _app_name(workload: WorkloadProfile) -> str:
    return f"{workload.application_type}-app"


def _kubernetes_candidate(
    workload: WorkloadProfile,
    name: str,
    summary: str,
    *,
    cpu_cores: float,
    memory_gb: float,
    replicas: int,
    autoscaling_enabled: bool = False,
    storage_gb: float | None = None,
) -> CandidatePlan:
    configuration = InfrastructureConfiguration(
        source_type="kubernetes",
        application=_app_name(workload),
        namespace="default",
        replicas=replicas,
        cpu_request=cpu_cores,
        cpu_limit=cpu_cores,  # generated configs keep limit == request: boring, predictable
        memory_request_gb=memory_gb,
        memory_limit_gb=memory_gb,
        autoscaling_enabled=autoscaling_enabled,
        storage_gb=storage_gb,
    )
    return CandidatePlan(variant=name, summary=summary, configuration=configuration)


def _autoscaling_ceiling(requirements: ResourceRequirements) -> int:
    """Peak-derived replica ceiling (documented heuristic, section 44.2)."""
    return max(
        requirements.replica_estimate + 2,
        int(round(requirements.replica_estimate * requirements.peak_factor)),
    )


def _vm_baseline_plan(
    workload: WorkloadProfile,
    requirements: ResourceRequirements,
) -> CandidatePlan | None:
    """Terraform-style VM baseline candidate, or None if nothing fits the table."""
    instance_type = smallest_covering_instance_type(
        requirements.cpu_cores, requirements.memory_gb
    )
    if instance_type is None:
        return None
    spec, _ = get_instance_type(instance_type)
    vcpu, memory_gib = spec.vcpu, spec.memory_gib
    # Fixed VM sizes rarely match the estimate exactly; call the headroom out
    # honestly in the summary instead of implying an exact fit.
    overprovisioned = (vcpu, memory_gib) != (
        requirements.cpu_cores,
        requirements.memory_gb,
    )
    note = (
        f" (smallest listed type covering {requirements.cpu_cores:g} cores / "
        f"{requirements.memory_gb:g} GiB — some headroom is inherent to fixed VM sizes)"
        if overprovisioned
        else ""
    )

    configuration = InfrastructureConfiguration(
        source_type="terraform",
        application=_app_name(workload),
        namespace="default",
        replicas=requirements.replica_estimate,
        cpu_request=float(vcpu),
        cpu_limit=None,
        memory_request_gb=float(memory_gib),
        memory_limit_gb=None,
        autoscaling_enabled=False,
        cloud_provider=VM_BASELINE_PROVIDER,
        region=VM_BASELINE_REGION,
        instance_type=instance_type,
        instance_count=requirements.replica_estimate,
        storage_gb=requirements.storage_gb,
    )
    return CandidatePlan(
        variant="vm-baseline",
        summary=(
            f"The required sizing rendered as fixed VMs ({instance_type}, "
            f"{vcpu} vCPU / {memory_gib} GiB each, "
            f"{requirements.replica_estimate} instance(s), {VM_BASELINE_PROVIDER} "
            f"{VM_BASELINE_REGION}){note} — the traditional-infrastructure "
            f"comparison point."
        ),
        configuration=configuration,
    )


def generate_candidates(
    workload: WorkloadProfile,
    requirements: ResourceRequirements,
) -> list[CandidatePlan]:
    """Produce the curated candidate set (deterministic, 3-6 plans)."""
    plans: list[CandidatePlan] = []

    lean_cpu = max(_ladder_step(CPU_LADDER, requirements.cpu_cores, -1), CPU_FLOOR_CORES)
    lean_memory = max(_ladder_step(MEMORY_LADDER, requirements.memory_gb, -1), MEMORY_FLOOR_GB)
    balanced_cpu = requirements.cpu_cores
    balanced_memory = requirements.memory_gb
    headroom_cpu = _ladder_step(CPU_LADDER, requirements.cpu_cores, +1)
    headroom_memory = _ladder_step(MEMORY_LADDER, requirements.memory_gb, +1)

    replica_estimate = requirements.replica_estimate
    replica_minimum = requirements.replica_minimum

    # 1. Lean: one sizing step down, replicas at the availability minimum.
    plans.append(
        _kubernetes_candidate(
            workload,
            "lean",
            f"Smallest sizing one ladder step below the requirement "
            f"({lean_cpu:g} cores / {lean_memory:g} GiB per replica) with "
            f"{replica_minimum} replica(s) at the availability minimum — "
            f"cost- and sustainability-leaning, least headroom.",
            cpu_cores=lean_cpu,
            memory_gb=lean_memory,
            replicas=replica_minimum,
        )
    )

    # 2. Balanced: the requirement estimate itself.
    plans.append(
        _kubernetes_candidate(
            workload,
            "balanced",
            f"The requirement estimate as-is ({balanced_cpu:g} cores / "
            f"{balanced_memory:g} GiB per replica, {replica_estimate} replica(s)) — "
            f"the default trade-off across performance, cost, and sustainability.",
            cpu_cores=balanced_cpu,
            memory_gb=balanced_memory,
            replicas=replica_estimate,
        )
    )

    # 3. Headroom: one sizing step up, same replicas (performance-leaning).
    plans.append(
        _kubernetes_candidate(
            workload,
            "headroom",
            f"One ladder step above the requirement ({headroom_cpu:g} cores / "
            f"{headroom_memory:g} GiB per replica, {replica_estimate} replica(s)) — "
            f"performance-leaning with room for traffic spikes.",
            cpu_cores=headroom_cpu,
            memory_gb=headroom_memory,
            replicas=replica_estimate,
        )
    )

    # 4. Elastic: required sizing with autoscaling enabled.
    ceiling = _autoscaling_ceiling(requirements)
    plans.append(
        _kubernetes_candidate(
            workload,
            "elastic",
            f"Required sizing with autoscaling enabled (min {replica_minimum}, "
            f"max {ceiling} replicas derived from the {requirements.peak_factor:g}x "
            f"peak factor) — pays for average load, scales for peaks.",
            cpu_cores=balanced_cpu,
            memory_gb=balanced_memory,
            replicas=max(replica_minimum, 2),
            autoscaling_enabled=True,
        )
    )

    # 5. Economy storage: only when storage was requested and the app type
    # tolerates it (never for database/streaming, section 44.2).
    if (
        requirements.storage_gb is not None
        and requirements.storage_gb > 0
        and workload.application_type not in STORAGE_CRITICAL_TYPES
    ):
        economy_storage = _ladder_step(STORAGE_LADDER, requirements.storage_gb, -1)
        if economy_storage < requirements.storage_gb:
            plans.append(
                _kubernetes_candidate(
                    workload,
                    "economy-storage",
                    f"Balanced sizing with storage reduced one ladder step "
                    f"({requirements.storage_gb:g} GB -> {economy_storage:g} GB) — "
                    f"cheaper storage tier at the same compute.",
                    cpu_cores=balanced_cpu,
                    memory_gb=balanced_memory,
                    replicas=replica_estimate,
                    storage_gb=economy_storage,
                )
            )

    # 6. VM baseline: the required sizing as a Terraform-style shape, for
    # platform comparison (section 44.2 rationale: Mode B candidates may
    # include Terraform-style normalized configurations).
    vm_plan = _vm_baseline_plan(workload, requirements)
    if vm_plan is not None:
        plans.append(vm_plan)

    # Dedup by configuration identity, preserving insertion order.
    unique: dict[str, CandidatePlan] = {}
    for plan in plans:
        unique.setdefault(plan.configuration.model_dump_json(), plan)
    return list(unique.values())


def requirements_from_estimate(estimate: ResourceRequirements) -> ResourceRequirementsModel:
    """Bridge the Phase 14 frozen dataclass into the serializable schema."""
    return ResourceRequirementsModel(
        cpu_cores=estimate.cpu_cores,
        memory_gb=estimate.memory_gb,
        replica_estimate=estimate.replica_estimate,
        replica_minimum=estimate.replica_minimum,
        storage_gb=estimate.storage_gb,
        autoscaling_required=estimate.autoscaling_required,
        peak_factor=estimate.peak_factor,
        notes=list(estimate.notes),
    )


def plans_for_workload(
    workload: WorkloadProfile,
    settings: object | None = None,
) -> tuple[ResourceRequirementsModel, list[CandidatePlan]]:
    """One-call helper: estimate requirements then generate candidates.

    Returns (requirements, plans). Pure and deterministic. `settings` is
    accepted for interface symmetry with the other generation services and
    ignored today.
    """
    del settings
    estimate = estimate_requirements(workload)
    return requirements_from_estimate(estimate), generate_candidates(workload, estimate)
