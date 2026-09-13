"""Synthetic Kubernetes-scale demand augmentation (design doc section 14).

The Google Cluster trace measures CPU/memory in machine fractions and carries
no Kubernetes-style allocations, user counts, or traffic levels. When the
event/usage shards cannot be joined, the trace's allocation proxy degenerates
(see preprocess.py metadata: allocation_source fallback), so a model trained
only on raw trace rows predicts near-constant utilization for real backend
inputs. Design doc section 14 permits "a clearly documented synthetic
component"; this module is that component.

Method (transparent, deterministic):
- Allocation ranges mirror common Kubernetes requests (cpu 0.25-8 cores,
  memory 0.25-16 GiB).
- Per-application demand curves define expected utilization at a reference
  allocation; utilization decreases hyperbolically as allocation grows
  (fixed demand spread over more resources), modulated by traffic level and
  user count.
- Random noise is calibrated to the real trace's utilization spread
  (cpu std ~0.14, memory std ~0.22) so the model still learns realistic
  variability.

The synthetic rows are ALWAYS combined with the real trace rows; the model
never trains on synthetic data alone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS

# Reference allocation where demand curves produce their nominal utilization.
REFERENCE_CPU_CORES = 1.0
REFERENCE_MEMORY_GB = 1.0

# Per-application demand at the reference allocation, on the FeatureVector's
# 1-9 application_type_code scale (mirrors backend feature_service mapping).
# Values are documented prototype assumptions, not measurements.
APPLICATION_DEMAND: dict[int, dict[str, float]] = {
    1: {"cpu": 0.55, "memory": 0.45},  # web-application
    2: {"cpu": 0.65, "memory": 0.55},  # e-commerce
    3: {"cpu": 0.45, "memory": 0.40},  # rest-api
    4: {"cpu": 0.35, "memory": 0.80},  # database
    5: {"cpu": 0.80, "memory": 0.65},  # machine-learning
    6: {"cpu": 0.75, "memory": 0.60},  # ai-inference
    7: {"cpu": 0.60, "memory": 0.70},  # streaming
    8: {"cpu": 0.85, "memory": 0.35},  # batch
    9: {"cpu": 0.50, "memory": 0.50},  # microservices
}

# Traffic multipliers on demand (traffic_score 1-4).
TRAFFIC_DEMAND_MULTIPLIER: dict[int, float] = {1: 0.7, 2: 1.0, 3: 1.35, 4: 1.1}

# User-count scaling: demand grows sublinearly with users (caching, batching).
USER_DEMAND_EXPONENT = 0.4
REFERENCE_USERS = 1000.0

# Noise standard deviations calibrated to the Google trace utilization spread.
CPU_NOISE_STD = 0.14
MEMORY_NOISE_STD = 0.22

SYNTHETIC_ALLOCATION_SOURCE = "trace_plus_synthetic_k8s_demand"


def _demand(
    application_type_code: int,
    traffic_score: int,
    expected_users: float,
) -> tuple[float, float]:
    profile = APPLICATION_DEMAND[int(application_type_code)]
    traffic = TRAFFIC_DEMAND_MULTIPLIER[int(traffic_score)]
    user_scale = (max(expected_users, 1.0) / REFERENCE_USERS) ** USER_DEMAND_EXPONENT
    return profile["cpu"] * traffic * user_scale, profile["memory"] * traffic * user_scale


def _utilization_for_row(row: pd.Series, rng: np.random.Generator) -> tuple[float, float]:
    # Each replica serves its share of users: demand is driven by
    # users_per_replica, then spread over that replica's allocation.
    demand_cpu, demand_memory = _demand(
        row["application_type_code"], row["traffic_score"], row["users_per_replica"]
    )
    cpu_scale = max(float(row["cpu"]), 1e-6) / REFERENCE_CPU_CORES
    memory_scale = max(float(row["memory_gb"]), 1e-6) / REFERENCE_MEMORY_GB
    # Fixed demand over a larger allocation -> lower utilization (hyperbolic).
    cpu_utilization = demand_cpu / cpu_scale
    memory_utilization = demand_memory / memory_scale

    cpu_utilization += rng.normal(0.0, CPU_NOISE_STD)
    memory_utilization += rng.normal(0.0, MEMORY_NOISE_STD)
    return float(np.clip(cpu_utilization, 0.0, 1.0)), float(np.clip(memory_utilization, 0.0, 1.0))


def generate_synthetic_rows(
    row_count: int,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate documented synthetic training rows in Kubernetes-scale units."""
    if row_count < 0:
        raise ValueError("row_count must be non-negative")
    if row_count == 0:
        return pd.DataFrame(columns=FEATURE_COLUMNS + TARGET_COLUMNS)
    rng = np.random.default_rng(seed)

    application_codes = np.array(sorted(APPLICATION_DEMAND))
    traffic_scores = np.array(sorted(TRAFFIC_DEMAND_MULTIPLIER))
    # Log-uniform allocations cover small and large Kubernetes requests evenly.
    cpu = np.exp(rng.uniform(np.log(0.25), np.log(8.0), row_count))
    memory_gb = np.exp(rng.uniform(np.log(0.25), np.log(16.0), row_count))
    replicas = rng.integers(1, 9, row_count)
    expected_users = np.exp(rng.uniform(np.log(100), np.log(100_000), row_count)).round(-1)
    traffic_score = rng.choice(traffic_scores, row_count)
    application_type_code = rng.choice(application_codes, row_count)

    frame = pd.DataFrame(
        {
            "application_type_code": application_type_code,
            "expected_users": expected_users,
            "traffic_score": traffic_score,
            "max_latency_ms": rng.choice([100, 150, 200, 300, 500], row_count),
            "availability_target": rng.choice([99.0, 99.5, 99.9, 99.95, 99.99], row_count),
            "cpu": cpu,
            "memory_gb": memory_gb,
            "replicas": replicas,
            "autoscaling_enabled_int": rng.integers(0, 2, row_count),
            "total_cpu_capacity": cpu * replicas,
            "total_memory_capacity": memory_gb * replicas,
            "users_per_replica": expected_users / np.maximum(replicas, 1),
        }
    )

    utilizations = frame.apply(lambda row: _utilization_for_row(row, rng), axis=1)
    frame["cpu_utilization"] = [value[0] for value in utilizations]
    frame["memory_utilization"] = [value[1] for value in utilizations]
    return frame
