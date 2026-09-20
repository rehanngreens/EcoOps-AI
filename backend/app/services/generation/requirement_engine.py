"""Phase 14 Workload Requirement Engine (design doc section 44.1).

Turns a Mode B workload profile (WorkloadProfile v2 fields) into a
deterministic, explainable resource-requirement estimate. This module is
PURE: functions in, dataclass out — no DB, no I/O, no ML. The estimate is
an intermediate input to candidate generation (Phase 15), never itself an
infrastructure configuration.

Design rules from the design doc:

- Every constant lives in REQUIREMENT_RULES (a documented table), not
  scattered through the code. The values are starting points documented as
  estimates, refined during Phase 14 testing — honest heuristics, not
  measurements.
- Latency and availability requirements are RECORDED, not consumed here:
  they are constraint-engine inputs (Phase 8 services) later in the
  pipeline. Storage is passed through, never invented.
- Replica minimums reuse the constraint engine's availability tiers AND
  its user-capacity formula as the single source of truth, so Mode B
  candidates cannot be born failing the Phase 8 availability or
  user-capacity checks.
- Do NOT train a second ML model to size infrastructure; the existing
  utilization model provides evidence downstream (section 44.1).

Traffic-pattern note: v2 "bursty" must never reach v1 traffic_level (the
ML feature mapping would KeyError). The engine translates patterns into a
peak_factor instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.schemas.workload_schema import WorkloadProfile
from app.services.constraint_service import (
    _AVAILABILITY_FALLBACK_REPLICAS,
    _AVAILABILITY_TIERS,
)

# Discrete sizing ladders (cores / GiB). Sizing rounds UP to the next step;
# the round-up result is clamped to the ladder bounds.
CPU_LADDER: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
MEMORY_LADDER: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)

# Peak-intensity defaults when peak_rps/average_rps cannot be derived
# directly (no RPS numbers given): keyed by v2 traffic_pattern.
DEFAULT_PEAK_FACTORS: dict[str, float] = {
    "low": 1.2,
    "medium": 1.5,
    "high": 2.0,
    "variable": 2.5,
    "bursty": 3.0,
}

# Per-application-type sizing table (documented estimates, section 44.1):
# rps_per_core      — peak requests-per-second one CPU core is assumed to
#                     serve for this app type (concurrency factor).
# memory_gb_per_core — memory ratio (database/streaming are memory-dominant,
#                     ML/AI compute-dominant with big working sets).
# users_rps_share   — assumed average requests/second per active user when
#                     only expected_users is given (no RPS numbers).
# default_peak_factor — used when no traffic_pattern is supplied either.
REQUIREMENT_RULES: dict[str, dict[str, float]] = {
    "web-application": {"rps_per_core": 120.0, "memory_gb_per_core": 2.0, "users_rps_share": 0.2, "default_peak_factor": 1.5},
    "e-commerce": {"rps_per_core": 80.0, "memory_gb_per_core": 2.0, "users_rps_share": 0.3, "default_peak_factor": 2.0},
    "rest-api": {"rps_per_core": 150.0, "memory_gb_per_core": 1.5, "users_rps_share": 0.2, "default_peak_factor": 1.5},
    "database": {"rps_per_core": 50.0, "memory_gb_per_core": 4.0, "users_rps_share": 0.1, "default_peak_factor": 1.5},
    "machine-learning": {"rps_per_core": 10.0, "memory_gb_per_core": 8.0, "users_rps_share": 0.05, "default_peak_factor": 2.0},
    "ai-inference": {"rps_per_core": 10.0, "memory_gb_per_core": 4.0, "users_rps_share": 0.2, "default_peak_factor": 2.0},
    "streaming": {"rps_per_core": 40.0, "memory_gb_per_core": 4.0, "users_rps_share": 0.4, "default_peak_factor": 2.5},
    "batch": {"rps_per_core": 20.0, "memory_gb_per_core": 2.0, "users_rps_share": 0.0, "default_peak_factor": 1.2},
    "microservices": {"rps_per_core": 100.0, "memory_gb_per_core": 2.0, "users_rps_share": 0.2, "default_peak_factor": 2.0},
}

# Fall back to a conservative rest-api-like profile for anything unmapped.
_FALLBACK_RULE = REQUIREMENT_RULES["rest-api"]


@dataclass(frozen=True)
class ResourceRequirements:
    """Deterministic resource-requirement estimate for Mode B (section 44.1).

    This is an INTERMEDIATE artifact: it feeds candidate generation and is
    persisted with the generation record for explainability; it is not an
    infrastructure configuration.
    """

    cpu_cores: float
    memory_gb: float
    replica_estimate: int
    replica_minimum: int
    storage_gb: float | None
    autoscaling_required: bool
    peak_factor: float
    notes: list[str] = field(default_factory=list)


def _rule_for(application_type: str) -> dict[str, float]:
    return REQUIREMENT_RULES.get(application_type, _FALLBACK_RULE)


def _round_up_ladder(value: float, ladder: tuple[float, ...]) -> float:
    """Round up to the next ladder step, clamped to the ladder bounds."""
    for step in ladder:
        if value <= step:
            return step
    return ladder[-1]


def availability_minimum_replicas(availability_target: float, autoscaling: bool) -> int:
    """Replica floor from the constraint engine's tiers (single source of truth)."""
    required = _AVAILABILITY_FALLBACK_REPLICAS
    for tier_target, tier_replicas in _AVAILABILITY_TIERS:
        if availability_target <= tier_target:
            required = tier_replicas
            break
    if autoscaling:
        # Autoscaling still needs a floor of 2 to survive one instance dying.
        return max(required, 2)
    return required


def user_capacity_minimum_replicas(workload: WorkloadProfile, settings=None) -> int:
    """Replica floor from the Phase 8 user-capacity check (single source of truth).

    The constraint engine's user_capacity check requires replicas x
    max_users_per_replica x traffic_multiplier >= expected_users. The engine
    applies the same formula here so Mode B candidates are not born failing
    that check.
    """
    from app.services.constraint_service import parameters_from_settings

    parameters = parameters_from_settings(settings)
    multiplier = parameters.traffic_multipliers.get(workload.traffic_level, 1.0)
    per_replica = parameters.max_users_per_replica * multiplier
    if per_replica <= 0:
        return 1
    return max(1, math.ceil(workload.expected_users / per_replica))


def estimate_requirements(
    workload: WorkloadProfile, settings=None
) -> ResourceRequirements:
    """Derive deterministic resource requirements from a v2 workload profile."""
    rule = _rule_for(workload.application_type)
    notes: list[str] = []

    # --- Traffic inputs: prefer explicit RPS, derive from users otherwise. ---
    average_rps = workload.average_rps
    peak_rps = workload.peak_rps
    if average_rps is None and peak_rps is not None:
        average_rps = peak_rps / 2.0
        notes.append(
            f"average_rps not provided; estimated as peak_rps/2 = {average_rps:g}"
        )
    if average_rps is None:
        average_rps = workload.expected_users * rule["users_rps_share"]
        notes.append(
            f"No RPS provided; estimated average_rps = expected_users "
            f"({workload.expected_users:g}) x users_rps_share "
            f"({rule['users_rps_share']:g}) = {average_rps:g} for "
            f"'{workload.application_type}'"
        )

    peak_factor: float
    if peak_rps is not None and average_rps > 0:
        peak_factor = max(peak_rps / average_rps, 1.0)
        notes.append(f"peak_factor derived from RPS ratio = {peak_factor:g}")
    elif workload.traffic_pattern is not None:
        peak_factor = DEFAULT_PEAK_FACTORS[workload.traffic_pattern]
        notes.append(
            f"peak_factor {peak_factor:g} from traffic_pattern "
            f"'{workload.traffic_pattern}'"
        )
    else:
        peak_factor = float(rule["default_peak_factor"])
        notes.append(
            f"peak_factor {peak_factor:g} from the '{workload.application_type}' default"
        )

    # --- CPU sizing: size for peak demand, rounded UP the ladder. ---
    sizing_rps = average_rps * peak_factor
    raw_cpu = sizing_rps / rule["rps_per_core"]
    cpu_cores = _round_up_ladder(raw_cpu, CPU_LADDER)
    notes.append(
        f"CPU: sizing demand {sizing_rps:g} rps (average x peak) / "
        f"{rule['rps_per_core']:g} rps-per-core = {raw_cpu:g} -> {cpu_cores:g} cores "
        f"(ladder round-up)"
    )

    # --- Memory sizing: app-type ratio over CPU, rounded UP the ladder. ---
    raw_memory = cpu_cores * rule["memory_gb_per_core"]
    memory_gb = _round_up_ladder(raw_memory, MEMORY_LADDER)
    notes.append(
        f"Memory: {cpu_cores:g} cores x {rule['memory_gb_per_core']:g} GiB/core = "
        f"{raw_memory:g} -> {memory_gb:g} GiB (ladder round-up)"
    )

    # --- Replicas: availability tiers + user capacity + autoscaling floor. ---
    autoscaling_required = bool(workload.autoscaling_required)
    replica_minimum = availability_minimum_replicas(
        workload.availability_target, autoscaling_required
    )
    notes.append(
        f"Replica minimum {replica_minimum} from availability target "
        f"{workload.availability_target:g}%"
        + (" with autoscaling floor 2" if autoscaling_required else "")
    )

    user_floor = user_capacity_minimum_replicas(workload, settings)
    if user_floor > replica_minimum:
        replica_minimum = user_floor
        notes.append(
            f"Replica minimum raised to {replica_minimum} by the user-capacity "
            f"rule ({workload.expected_users:g} users / "
            f"max_users_per_replica x traffic multiplier)"
        )

    per_replica_rps = rule["rps_per_core"] * cpu_cores
    if per_replica_rps > 0 and autoscaling_required:
        # With autoscaling, min replicas must absorb average demand; peak is
        # the autoscaler's job. At least 2 so a single failure is survivable.
        throughput_replicas = max(2, math.ceil(average_rps / per_replica_rps))
        notes.append(
            f"Autoscaling replicas: ceil(average {average_rps:g} rps / "
            f"{per_replica_rps:g} rps-per-replica) = {throughput_replicas} (floor 2)"
        )
    elif per_replica_rps > 0:
        # Fixed fleet: size for peak demand.
        throughput_replicas = max(1, math.ceil(sizing_rps / per_replica_rps))
        notes.append(
            f"Fixed replicas: ceil(peak {sizing_rps:g} rps / "
            f"{per_replica_rps:g} rps-per-replica) = {throughput_replicas}"
        )
    else:
        throughput_replicas = 1

    replica_estimate = max(replica_minimum, throughput_replicas)
    if replica_estimate == replica_minimum and replica_minimum > throughput_replicas:
        notes.append(
            f"Replica estimate raised to the availability minimum "
            f"({replica_minimum}) over the throughput estimate "
            f"({throughput_replicas})"
        )

    return ResourceRequirements(
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        replica_estimate=replica_estimate,
        replica_minimum=replica_minimum,
        storage_gb=workload.storage_gb,
        autoscaling_required=autoscaling_required,
        peak_factor=peak_factor,
        notes=notes,
    )


def validate_workload_requirements(workload: WorkloadProfile) -> list[str]:
    """Human-readable problems with a Mode B request (empty list = valid).

    The schema already rejects impossible values (peak < average, negative
    numbers); this layer adds cross-field advisory checks for the Phase 17
    endpoint to surface as 422s.
    """
    problems: list[str] = []

    if workload.traffic_pattern == "bursty" and (
        workload.peak_rps is None or workload.average_rps is None
    ):
        problems.append(
            "traffic_pattern 'bursty' without average_rps and peak_rps: provide "
            "both RPS values so burst intensity can be modeled explicitly"
        )

    if workload.application_type == "batch" and workload.max_latency_ms < 1000:
        problems.append(
            "application_type 'batch' with max_latency_ms < 1000: batch workloads "
            "are throughput-oriented; a sub-second latency target suggests "
            "'rest-api' or 'web-application' instead"
        )

    if workload.storage_gb is not None and workload.application_type in {
        "database",
        "streaming",
    } and workload.storage_gb <= 0:
        problems.append(
            f"application_type '{workload.application_type}' expects a positive "
            "storage_gb requirement"
        )

    return problems
