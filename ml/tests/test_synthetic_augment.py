import numpy as np
import pandas as pd
import pytest

from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS
from synthetic_augment import (
    APPLICATION_DEMAND,
    SYNTHETIC_ALLOCATION_SOURCE,
    generate_synthetic_rows,
)

def test_generated_rows_have_full_contract() -> None:
    frame = generate_synthetic_rows(50, seed=42)
    assert list(frame.columns) == FEATURE_COLUMNS + TARGET_COLUMNS
    assert len(frame) == 50


def test_generation_is_deterministic_for_same_seed() -> None:
    first = generate_synthetic_rows(20, seed=7)
    second = generate_synthetic_rows(20, seed=7)
    pd.testing.assert_frame_equal(first, second)


def test_utilization_decreases_as_allocation_grows() -> None:
    frame = generate_synthetic_rows(4000, seed=42)
    # Average utilization in the smallest CPU quartile should exceed the largest.
    cpu_quartiles = pd.qcut(frame["cpu"], 4, labels=False)
    small = frame[cpu_quartiles == 0]["cpu_utilization"].mean()
    large = frame[cpu_quartiles == 3]["cpu_utilization"].mean()
    assert small > large > 0


def test_memory_utilization_decreases_as_memory_grows() -> None:
    frame = generate_synthetic_rows(4000, seed=42)
    memory_quartiles = pd.qcut(frame["memory_gb"], 4, labels=False)
    small = frame[memory_quartiles == 0]["memory_utilization"].mean()
    large = frame[memory_quartiles == 3]["memory_utilization"].mean()
    assert small > large > 0


def test_targets_within_unit_range() -> None:
    frame = generate_synthetic_rows(500, seed=42)
    assert frame[TARGET_COLUMNS].min().min() >= 0.0
    assert frame[TARGET_COLUMNS].max().max() <= 1.0


def test_allocations_cover_kubernetes_scale() -> None:
    frame = generate_synthetic_rows(2000, seed=42)
    assert frame["cpu"].min() >= 0.25
    assert frame["cpu"].max() <= 8.0
    assert frame["memory_gb"].min() >= 0.25
    assert frame["memory_gb"].max() <= 16.0
    assert set(frame["replicas"]).issubset(set(range(1, 9)))


def test_application_codes_match_demand_table() -> None:
    frame = generate_synthetic_rows(2000, seed=42)
    assert set(frame["application_type_code"]).issubset(set(APPLICATION_DEMAND))


def test_higher_traffic_increases_utilization() -> None:
    frame = generate_synthetic_rows(8000, seed=42)
    low = frame[frame["traffic_score"] == 1]["cpu_utilization"].mean()
    high = frame[frame["traffic_score"] == 3]["cpu_utilization"].mean()
    assert high > low


def test_negative_row_count_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        generate_synthetic_rows(-1)


def test_zero_rows_allowed() -> None:
    frame = generate_synthetic_rows(0, seed=42)
    assert len(frame) == 0
    assert SYNTHETIC_ALLOCATION_SOURCE  # source label present
