"""Map Google Cluster rows onto Phase 3 FeatureVector numeric columns."""

from __future__ import annotations

import pandas as pd

from config import (
    DEFAULT_APPLICATION_TYPE_CODE,
    DEFAULT_AUTOSCALING_ENABLED_INT,
    DEFAULT_AVAILABILITY_TARGET,
    DEFAULT_EXPECTED_USERS,
    DEFAULT_MAX_LATENCY_MS,
    DEFAULT_REPLICAS,
    DEFAULT_TRAFFIC_SCORE,
)

# Google scheduling_class is 0-3. This is a documented proxy, not a true app type.
SCHEDULING_CLASS_TO_APPLICATION_TYPE_CODE = {
    "0": 3,  # rest-api
    "1": 1,  # web-application
    "2": 8,  # batch
    "3": 5,  # machine-learning
}

FEATURE_COLUMNS = [
    "application_type_code",
    "expected_users",
    "traffic_score",
    "max_latency_ms",
    "availability_target",
    "cpu",
    "memory_gb",
    "replicas",
    "autoscaling_enabled_int",
    "total_cpu_capacity",
    "total_memory_capacity",
    "users_per_replica",
]

TARGET_COLUMNS = [
    "cpu_utilization",
    "memory_utilization",
]

OUTPUT_COLUMNS = FEATURE_COLUMNS + TARGET_COLUMNS


def latest_allocations(events: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest resource request per instance."""
    required = {"collection_id", "instance_index", "time", "cpu_request", "memory_request"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Events frame missing columns: {sorted(missing)}")

    allocated = events.dropna(subset=["collection_id", "instance_index", "cpu_request", "memory_request"])
    allocated = allocated[(allocated["cpu_request"] > 0) & (allocated["memory_request"] > 0)]
    if allocated.empty:
        return allocated

    allocated = allocated.sort_values("time")
    keep = [
        "collection_id",
        "instance_index",
        "cpu_request",
        "memory_request",
        "scheduling_class",
        "priority",
    ]
    keep = [column for column in keep if column in allocated.columns]
    return allocated.groupby(["collection_id", "instance_index"], as_index=False).tail(1)[keep]


def join_usage_with_allocations(usage: pd.DataFrame, allocations: pd.DataFrame) -> pd.DataFrame:
    joined = usage.merge(
        allocations,
        on=["collection_id", "instance_index"],
        how="inner",
    )
    return joined.dropna(subset=["cpu_usage", "memory_usage", "cpu_request", "memory_request"])


def allocations_from_usage_peaks(usage: pd.DataFrame) -> pd.DataFrame:
    """Fallback allocation proxy when events do not join this usage shard.

    Uses maximum_usage as the allocated amount for the measurement window.
    assigned_memory is preferred for memory when it is present and positive.
    """
    result = usage.copy()
    result["cpu_request"] = result["cpu_max"]
    memory_from_assigned = result["assigned_memory"].fillna(0) > 0
    result["memory_request"] = result["memory_max"]
    result.loc[memory_from_assigned, "memory_request"] = result.loc[
        memory_from_assigned, "assigned_memory"
    ]
    if "scheduling_class" not in result.columns:
        result["scheduling_class"] = None
    return result.dropna(subset=["cpu_request", "memory_request"])


def add_utilization_targets(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result = result[(result["cpu_request"] > 0) & (result["memory_request"] > 0)]
    result["cpu_utilization"] = (result["cpu_usage"] / result["cpu_request"]).clip(0, 1)
    result["memory_utilization"] = (result["memory_usage"] / result["memory_request"]).clip(0, 1)
    return result.dropna(subset=TARGET_COLUMNS)


def map_to_training_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Produce the FeatureVector-aligned training table."""
    result = frame.copy()
    replicas = DEFAULT_REPLICAS

    scheduling_class = result["scheduling_class"] if "scheduling_class" in result.columns else None
    if scheduling_class is not None:
        result["application_type_code"] = scheduling_class.map(
            SCHEDULING_CLASS_TO_APPLICATION_TYPE_CODE
        ).fillna(DEFAULT_APPLICATION_TYPE_CODE)
    else:
        result["application_type_code"] = DEFAULT_APPLICATION_TYPE_CODE

    result["expected_users"] = DEFAULT_EXPECTED_USERS
    result["traffic_score"] = DEFAULT_TRAFFIC_SCORE
    result["max_latency_ms"] = DEFAULT_MAX_LATENCY_MS
    result["availability_target"] = DEFAULT_AVAILABILITY_TARGET
    result["cpu"] = result["cpu_request"]
    result["memory_gb"] = result["memory_request"]
    result["replicas"] = replicas
    result["autoscaling_enabled_int"] = DEFAULT_AUTOSCALING_ENABLED_INT
    result["total_cpu_capacity"] = result["cpu"] * replicas
    result["total_memory_capacity"] = result["memory_gb"] * replicas
    result["users_per_replica"] = DEFAULT_EXPECTED_USERS / replicas

    result["application_type_code"] = result["application_type_code"].astype(int)
    return result[OUTPUT_COLUMNS]


def build_training_table(
    events: pd.DataFrame,
    usage: pd.DataFrame,
    min_joined_rows: int = 1,
) -> tuple[pd.DataFrame, str]:
    allocations = latest_allocations(events) if not events.empty else events
    joined = join_usage_with_allocations(usage, allocations) if not allocations.empty else usage.iloc[0:0]
    allocation_source = "instance_events.resource_request"

    if len(joined) < min_joined_rows:
        joined = allocations_from_usage_peaks(usage)
        allocation_source = "instance_usage.maximum_usage_fallback"

    with_targets = add_utilization_targets(joined)
    return map_to_training_features(with_targets), allocation_source
