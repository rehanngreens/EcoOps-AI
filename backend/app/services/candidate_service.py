"""Phase 9 candidate generation: deterministic scale-down candidates.

Candidates are pure derived configurations; they are only proposed if they
differ from the current configuration. Reduction floors keep candidates in
sane Kubernetes territory (250m CPU, 256Mi memory). Replica floors respect the
Phase 8 availability-tier rule so availability is never proposed below its
minimum. Predicted utilization is deliberately NOT used here; it is applied
later as a headroom guard (see recommendation_service).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile

CPU_FLOOR_CORES = 0.25
MEMORY_FLOOR_GB = 0.25  # ~256Mi


@dataclass(frozen=True)
class Candidate:
    """One proposed configuration with a short human-readable summary."""

    configuration: InfrastructureConfiguration
    summary: str


def _round_cores(value: float) -> float:
    return max(round(value * 1000) / 1000, CPU_FLOOR_CORES)


def _round_memory(value: float) -> float:
    return max(round(value * 100) / 100, MEMORY_FLOOR_GB)


def _availability_floor(workload: WorkloadProfile) -> int:
    """Same tier logic as the Phase 8 availability check."""
    target = workload.availability_target
    if target <= 99.0:
        return 1
    if target <= 99.9:
        return 2
    if target <= 99.99:
        return 3
    return 4


def _candidate(
    base: InfrastructureConfiguration,
    summary: str,
    *,
    replicas: int | None = None,
    cpu_request: float | None = None,
    memory_request_gb: float | None = None,
    autoscaling_enabled: bool | None = None,
) -> Candidate:
    update: dict[str, object] = {
        "replicas": replicas if replicas is not None else base.replicas,
        "cpu_request": cpu_request if cpu_request is not None else base.cpu_request,
        "memory_request_gb": (
            memory_request_gb if memory_request_gb is not None else base.memory_request_gb
        ),
    }
    if autoscaling_enabled is not None:
        update["autoscaling_enabled"] = autoscaling_enabled
    configuration = base.model_copy(update=update)
    return Candidate(configuration=configuration, summary=summary)


def _scale_candidates(base: InfrastructureConfiguration) -> list[Candidate]:
    candidates: list[Candidate] = []

    if base.cpu_request and base.cpu_request > CPU_FLOOR_CORES:
        for fraction, label in ((0.5, "50%"), (0.25, "25%")):
            reduced = _round_cores(base.cpu_request * fraction)
            if reduced < base.cpu_request:
                candidates.append(
                    _candidate(
                        base,
                        f"reduce CPU request from {base.cpu_request:g} to {reduced:g} cores ({label})",
                        cpu_request=reduced,
                    )
                )

    if base.memory_request_gb and base.memory_request_gb > MEMORY_FLOOR_GB:
        for fraction, label in ((0.5, "50%"), (0.25, "25%")):
            reduced = _round_memory(base.memory_request_gb * fraction)
            if reduced < base.memory_request_gb:
                candidates.append(
                    _candidate(
                        base,
                        f"reduce memory request from {base.memory_request_gb:g} to {reduced:g} GiB ({label})",
                        memory_request_gb=reduced,
                    )
                )

    return candidates


def _replica_candidates(
    base: InfrastructureConfiguration, workload: WorkloadProfile
) -> list[Candidate]:
    floor = _availability_floor(workload)
    if base.replicas <= floor:
        return []

    candidates: list[Candidate] = []
    for target in (floor, max(floor, base.replicas // 2)):
        if target < base.replicas and all(
            target != candidate.configuration.replicas for candidate in candidates
        ):
            candidates.append(
                _candidate(
                    base,
                    f"reduce replicas from {base.replicas} to {target} (availability floor {floor})",
                    replicas=target,
                )
            )
    return candidates


def _autoscaling_candidate(base: InfrastructureConfiguration) -> list[Candidate]:
    if base.autoscaling_enabled:
        return []
    return [
        _candidate(
            base,
            "enable autoscaling so replicas can scale with load",
            autoscaling_enabled=True,
        )
    ]


def _combined_candidate(
    base: InfrastructureConfiguration, workload: WorkloadProfile
) -> list[Candidate]:
    cpu_reduced = (
        _round_cores(base.cpu_request * 0.25) if base.cpu_request and base.cpu_request > CPU_FLOOR_CORES else None
    )
    memory_reduced = (
        _round_memory(base.memory_request_gb * 0.25)
        if base.memory_request_gb and base.memory_request_gb > MEMORY_FLOOR_GB
        else None
    )
    replicas_reduced = min(
        (c.configuration.replicas for c in _replica_candidates(base, workload)),
        default=None,
    )

    if cpu_reduced is None and memory_reduced is None and replicas_reduced is None:
        return []

    parts: list[str] = []
    if cpu_reduced is not None:
        parts.append(f"CPU to {cpu_reduced:g} cores")
    if memory_reduced is not None:
        parts.append(f"memory to {memory_reduced:g} GiB")
    if replicas_reduced is not None:
        parts.append(f"replicas to {replicas_reduced}")

    return [
        _candidate(
            base,
            "combine reductions: " + ", ".join(parts),
            replicas=replicas_reduced,
            cpu_request=cpu_reduced,
            memory_request_gb=memory_reduced,
        )
    ]


def generate_candidates(
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
) -> list[Candidate]:
    """Produce all v1 scale-down candidates for one current configuration."""
    candidates: list[Candidate] = []
    candidates.extend(_scale_candidates(configuration))
    candidates.extend(_replica_candidates(configuration, workload))
    if not configuration.autoscaling_enabled:
        candidates.extend(_autoscaling_candidate(configuration))
    candidates.extend(_combined_candidate(configuration, workload))

    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        key = candidate.configuration.model_dump_json()
        unique.setdefault(key, candidate)

    current_key = configuration.model_dump_json()
    return [
        candidate
        for key, candidate in unique.items()
        if key != current_key
    ]
