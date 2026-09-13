"""Phase 8 constraint engine: transparent, documented feasibility heuristics.

Every rule is a simple prototype heuristic with configurable thresholds. The
engine distinguishes PREDICTED utilization (from the Phase 5 model) from
ESTIMATED feasibility (from these heuristics) and never claims measured
performance. See design doc sections 14, 18, and 39.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.constraint_schema import (
    ConstraintCheck,
    ConstraintEvaluation,
    ConstraintStatus,
)
from app.schemas.unified_schema import FeatureVector, UtilizationPrediction
from app.schemas.workload_schema import TrafficLevel

DISCLAIMER = (
    "Constraint feasibility is a prototype heuristic based on predicted "
    "utilization and configurable thresholds; it is not measured performance "
    "or a guarantee of real-world latency, availability, or capacity."
)

# Availability tier: availability target -> minimum replicas.
# Targets above the highest covered tier fall back to the strictest requirement.
_AVAILABILITY_TIERS: tuple[tuple[float, int], ...] = (
    (99.0, 1),
    (99.9, 2),
    (99.99, 3),
)

_AVAILABILITY_FALLBACK_REPLICAS = 4


@dataclass(frozen=True)
class ConstraintParameters:
    """Configurable thresholds for the constraint heuristics."""

    cpu_headroom_threshold: float
    memory_headroom_threshold: float
    latency_base_ms: float
    max_users_per_replica: float
    traffic_multipliers: dict[TrafficLevel, float]

    def __post_init__(self) -> None:
        if not 0 <= self.cpu_headroom_threshold <= 1:
            raise ValueError("cpu_headroom_threshold must be between zero and one")
        if not 0 <= self.memory_headroom_threshold <= 1:
            raise ValueError("memory_headroom_threshold must be between zero and one")
        if self.latency_base_ms <= 0:
            raise ValueError("latency_base_ms must be greater than zero")
        if self.max_users_per_replica <= 0:
            raise ValueError("max_users_per_replica must be greater than zero")
        if any(multiplier <= 0 for multiplier in self.traffic_multipliers.values()):
            raise ValueError("traffic multipliers must be greater than zero")


def parameters_from_settings(settings: Settings | None = None) -> ConstraintParameters:
    """Extract constraint settings once into a small testable value object."""
    values = settings or get_settings()
    return ConstraintParameters(
        cpu_headroom_threshold=values.cpu_headroom_threshold,
        memory_headroom_threshold=values.memory_headroom_threshold,
        latency_base_ms=values.latency_base_ms,
        max_users_per_replica=values.max_users_per_replica,
        traffic_multipliers={
            "low": values.traffic_multiplier_low,
            "medium": values.traffic_multiplier_medium,
            "high": values.traffic_multiplier_high,
            "variable": values.traffic_multiplier_variable,
        },
    )


def _check(
    name: str,
    passed: bool,
    required: str,
    actual: str,
    explanation: str,
) -> ConstraintCheck:
    return ConstraintCheck(
        name=name,
        status=ConstraintStatus.pass_ if passed else ConstraintStatus.fail,
        required=required,
        actual=actual,
        explanation=explanation,
    )


def _cpu_headroom_check(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters,
) -> ConstraintCheck:
    threshold = parameters.cpu_headroom_threshold
    predicted = prediction.cpu_utilization
    passed = predicted <= threshold
    explanation = (
        f"Predicted CPU utilization is {predicted:.1%} of the "
        f"{features.total_cpu_capacity:g}-vCPU total allocation."
        if passed
        else (
            f"Predicted CPU utilization is {predicted:.1%}, above the "
            f"{threshold:.0%} headroom threshold; the allocation may be too "
            f"small for stable operation."
        )
    )
    return _check(
        "cpu_headroom",
        passed,
        required=f"predicted utilization <= {threshold:.0%}",
        actual=f"{predicted:.1%}",
        explanation=explanation,
    )


def _memory_headroom_check(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters,
) -> ConstraintCheck:
    threshold = parameters.memory_headroom_threshold
    predicted = prediction.memory_utilization
    passed = predicted <= threshold
    explanation = (
        f"Predicted memory utilization is {predicted:.1%} of the "
        f"{features.total_memory_capacity:g} GiB total allocation."
        if passed
        else (
            f"Predicted memory utilization is {predicted:.1%}, above the "
            f"{threshold:.0%} headroom threshold; the workload may risk "
            f"memory pressure or evictions."
        )
    )
    return _check(
        "memory_headroom",
        passed,
        required=f"predicted utilization <= {threshold:.0%}",
        actual=f"{predicted:.1%}",
        explanation=explanation,
    )


def _latency_check(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters,
) -> ConstraintCheck:
    cpu_utilization = prediction.cpu_utilization
    max_latency_ms = features.max_latency_ms
    base_ms = parameters.latency_base_ms

    if cpu_utilization >= 0.99:
        return _check(
            "latency_feasibility",
            False,
            required=f"estimated latency <= {max_latency_ms:g} ms",
            actual="saturated",
            explanation=(
                f"Predicted CPU utilization is {cpu_utilization:.1%}; near "
                f"saturation makes any latency estimate meaningless and the "
                f"service is expected to time out under load."
            ),
        )

    estimated_latency_ms = base_ms / (1.0 - cpu_utilization)
    passed = estimated_latency_ms <= max_latency_ms
    explanation = (
        (
            f"Heuristic latency estimate is {estimated_latency_ms:.0f} ms "
            f"({base_ms:g} ms base load divided by spare CPU capacity "
            f"{1.0 - cpu_utilization:.0%}), within the {max_latency_ms:g} ms "
            f"target."
        )
        if passed
        else (
            f"Heuristic latency estimate is {estimated_latency_ms:.0f} ms "
            f"({base_ms:g} ms base load divided by spare CPU capacity "
            f"{1.0 - cpu_utilization:.0%}), exceeding the {max_latency_ms:g} ms "
            f"target."
        )
    )
    return _check(
        "latency_feasibility",
        passed,
        required=f"estimated latency <= {max_latency_ms:g} ms",
        actual=f"{estimated_latency_ms:.0f} ms",
        explanation=explanation,
    )


def _availability_check(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters,
) -> ConstraintCheck:
    del prediction, parameters  # Tier rule depends only on workload + replicas.

    target = features.availability_target
    replicas = max(features.replicas, 0)
    required_replicas = _AVAILABILITY_FALLBACK_REPLICAS
    covered = False
    for tier_target, tier_replicas in _AVAILABILITY_TIERS:
        if target <= tier_target:
            required_replicas = tier_replicas
            covered = True
            break

    tier_label = (
        f"<= {tier_target:g}% tier"
        if covered
        else f"above the {_AVAILABILITY_TIERS[-1][0]:g}% tier"
    )
    if features.autoscaling_enabled:
        passed = True
        explanation = (
            f"Availability target {target:g}% normally requires at least "
            f"{required_replicas} replica(s) ({tier_label}); autoscaling is "
            f"enabled, so replicas can grow under load."
        )
        actual = f"{replicas} replica(s), autoscaling enabled"
    else:
        passed = replicas >= required_replicas
        explanation = (
            f"Availability target {target:g}% requires at least "
            f"{required_replicas} replica(s) ({tier_label}); the deployment "
            f"declares {replicas}."
        )
        actual = f"{replicas} replica(s), autoscaling disabled"
    return _check(
        "availability_replicas",
        passed,
        required=f">= {required_replicas} replica(s) or autoscaling",
        actual=actual,
        explanation=explanation,
    )


def _user_capacity_check(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters,
) -> ConstraintCheck:
    del prediction

    multiplier = parameters.traffic_multipliers.get(features.traffic_level, 1.0)
    capacity = features.replicas * parameters.max_users_per_replica * multiplier
    expected_users = features.expected_users
    passed = expected_users <= capacity
    explanation = (
        (
            f"Expected {expected_users} users fit within the estimated "
            f"capacity of {capacity:g} users ({features.replicas} replica(s) "
            f"x {parameters.max_users_per_replica:g} users/replica x "
            f"{features.traffic_level} traffic x{multiplier:g})."
        )
        if passed
        else (
            f"Expected {expected_users} users exceed the estimated capacity "
            f"of {capacity:g} users ({features.replicas} replica(s) x "
            f"{parameters.max_users_per_replica:g} users/replica x "
            f"{features.traffic_level} traffic x{multiplier:g}); add replicas "
            f"or enable autoscaling."
        )
    )
    return _check(
        "user_capacity",
        passed,
        required=f"expected users <= {capacity:g}",
        actual=f"{expected_users} users",
        explanation=explanation,
    )


_CHECKS = (
    _cpu_headroom_check,
    _memory_headroom_check,
    _latency_check,
    _availability_check,
    _user_capacity_check,
)


def evaluate_constraints(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: ConstraintParameters | None = None,
) -> ConstraintEvaluation:
    """Evaluate all configured checks against one feature vector and prediction."""
    values = parameters or parameters_from_settings()
    checks = [check(features, prediction, values) for check in _CHECKS]
    return ConstraintEvaluation(
        satisfied=all(check.status is ConstraintStatus.pass_ for check in checks),
        checks=checks,
        disclaimer=DISCLAIMER,
    )
