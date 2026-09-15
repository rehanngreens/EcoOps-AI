"""Tests for Phase 14: WorkloadProfile v2 and the requirement engine."""

import math

import pytest
from pydantic import ValidationError

from app.schemas.workload_schema import WorkloadProfile
from app.services.feature_service import extract_features
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.services.generation.requirement_engine import (
    CPU_LADDER,
    MEMORY_LADDER,
    estimate_requirements,
    validate_workload_requirements,
)


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "rest-api",
        "expected_users": 1000,
        "traffic_level": "medium",
        "max_latency_ms": 200,
        "availability_target": 99.0,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


class TestWorkloadProfileV2Schema:
    def test_v1_only_payload_validates_unchanged(self) -> None:
        workload = WorkloadProfile(
            application_type="e-commerce",
            expected_users=10000,
            traffic_level="medium",
            max_latency_ms=150,
            availability_target=99.9,
        )
        assert workload.average_rps is None
        assert workload.peak_rps is None
        assert workload.traffic_pattern is None
        assert workload.storage_gb is None
        assert workload.autoscaling_required is None
        assert workload.performance_priority == "medium"
        assert workload.cost_priority == "medium"
        assert workload.sustainability_priority == "medium"

    def test_v2_fields_accepted(self) -> None:
        workload = _workload(
            average_rps=500.0,
            peak_rps=1500.0,
            traffic_pattern="bursty",
            storage_gb=100.0,
            autoscaling_required=True,
            performance_priority="high",
            cost_priority="low",
            sustainability_priority="high",
        )
        assert workload.average_rps == 500.0
        assert workload.peak_rps == 1500.0
        assert workload.traffic_pattern == "bursty"
        assert workload.autoscaling_required is True

    def test_traffic_level_still_rejects_bursty(self) -> None:
        with pytest.raises(ValidationError):
            _workload(traffic_level="bursty")

    def test_peak_below_average_rejected(self) -> None:
        with pytest.raises(ValidationError, match="peak_rps"):
            _workload(average_rps=1000.0, peak_rps=500.0)

    def test_peak_equal_average_allowed(self) -> None:
        workload = _workload(average_rps=500.0, peak_rps=500.0)
        assert workload.peak_rps == 500.0

    def test_negative_v2_values_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _workload(average_rps=-1)
        with pytest.raises(ValidationError):
            _workload(storage_gb=-5)

    def test_invalid_priority_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _workload(cost_priority="maximum")

    def test_v1_feature_extraction_unaffected_by_v2_fields(self) -> None:
        """v2 fields must never reach the ML feature pipeline."""
        configuration = InfrastructureConfiguration(
            source_type="kubernetes", application="app", replicas=2
        )
        workload = _workload(
            average_rps=999.0,
            peak_rps=4999.0,
            traffic_pattern="bursty",
            performance_priority="high",
        )
        features = extract_features(configuration, workload)
        assert features.traffic_level == "medium"
        assert features.traffic_score == 2  # v1 medium mapping, unchanged


class TestEstimateRequirements:
    def test_deterministic_same_input_same_output(self) -> None:
        workload = _workload(average_rps=600.0, peak_rps=1800.0)
        first = estimate_requirements(workload)
        second = estimate_requirements(workload)
        assert first == second

    def test_rps_path_sizes_cpu_for_peak(self) -> None:
        # rest-api: 150 rps/core; 600 avg x 3 peak = 1800 rps -> 12 -> 16 cores.
        result = estimate_requirements(_workload(average_rps=600.0, peak_rps=1800.0))
        assert result.cpu_cores == 16.0
        # Memory: 16 x 1.5 = 24 -> 32 on the ladder.
        assert result.memory_gb == 32.0
        assert result.peak_factor == pytest.approx(3.0)

    def test_users_path_estimates_rps_from_share(self) -> None:
        # e-commerce users_rps_share=0.3: 10000 users -> 3000 avg rps.
        result = estimate_requirements(_workload(application_type="e-commerce", expected_users=10000))
        # No pattern given -> e-commerce default peak factor 2.0 -> 6000 rps
        # / 80 rps-per-core = 75 -> clamped to the 32-core ladder ceiling.
        assert result.cpu_cores == 32.0
        assert result.memory_gb == 64.0
        assert any("users_rps_share" in note for note in result.notes)

    def test_traffic_pattern_drives_peak_factor(self) -> None:
        bursty = estimate_requirements(_workload(traffic_pattern="bursty"))
        low = estimate_requirements(_workload(traffic_pattern="low"))
        assert bursty.peak_factor == pytest.approx(3.0)
        assert low.peak_factor == pytest.approx(1.2)
        assert bursty.cpu_cores >= low.cpu_cores

    def test_replica_minimums_match_constraint_tiers(self) -> None:
        assert (
            estimate_requirements(_workload(availability_target=99.0)).replica_minimum == 1
        )
        assert (
            estimate_requirements(_workload(availability_target=99.9)).replica_minimum == 2
        )
        assert (
            estimate_requirements(_workload(availability_target=99.99)).replica_minimum == 3
        )
        assert (
            estimate_requirements(_workload(availability_target=99.999)).replica_minimum == 4
        )

    def test_autoscaling_requires_two_replicas_minimum(self) -> None:
        result = estimate_requirements(
            _workload(availability_target=99.0, autoscaling_required=True)
        )
        assert result.replica_minimum == 2
        assert result.autoscaling_required is True

    def test_fixed_replicas_size_for_peak(self) -> None:
        # 300 avg x 2 peak = 600 rps sizing -> 600/150 = 4 raw -> 4.0 cores;
        # per-replica capacity 150 x 4 = 600 rps -> ceil(600/600) = 1 replica.
        result = estimate_requirements(
            _workload(average_rps=300.0, peak_rps=600.0, expected_users=1000)
        )
        assert result.cpu_cores == 4.0
        assert result.replica_estimate == 1

    def test_replica_estimate_never_below_availability_minimum(self) -> None:
        # Tiny load, huge availability target.
        result = estimate_requirements(
            _workload(average_rps=1.0, peak_rps=2.0, availability_target=99.99)
        )
        assert result.replica_estimate == 3
        assert any("availability minimum" in note for note in result.notes)

    def test_database_is_memory_dominant(self) -> None:
        result = estimate_requirements(_workload(application_type="database"))
        rules_ratio = 4.0
        assert result.memory_gb == pytest.approx(
            min(
                [step for step in MEMORY_LADDER if step >= result.cpu_cores * rules_ratio]
            )
        )

    def test_batch_is_compute_cheap_but_flagged(self) -> None:
        result = estimate_requirements(_workload(application_type="batch"))
        assert result.cpu_cores <= 1.0  # batch users_rps_share is 0.0
        assert result.peak_factor == pytest.approx(1.2)

    def test_storage_passthrough_no_invention(self) -> None:
        assert estimate_requirements(_workload()).storage_gb is None
        assert estimate_requirements(_workload(storage_gb=250.0)).storage_gb == 250.0

    def test_ladder_round_up_and_clamp(self) -> None:
        tiny = estimate_requirements(_workload(average_rps=1.0, peak_rps=1.0))
        assert tiny.cpu_cores == CPU_LADDER[0]
        # Memory: 0.25 cores x 1.5 GiB/core = 0.375 -> rounds UP to 0.5.
        assert tiny.memory_gb == MEMORY_LADDER[1]

        huge = estimate_requirements(_workload(average_rps=10**6, peak_rps=10**6))
        assert huge.cpu_cores == CPU_LADDER[-1]
        assert huge.memory_gb == MEMORY_LADDER[-1]

    def test_missing_average_with_peak_given(self) -> None:
        result = estimate_requirements(_workload(peak_rps=900.0))
        assert any("peak_rps/2" in note for note in result.notes)
        assert result.peak_factor >= 1.0

    def test_notes_explain_every_major_rule(self) -> None:
        result = estimate_requirements(
            _workload(average_rps=300.0, peak_rps=600.0, storage_gb=40.0, autoscaling_required=True)
        )
        joined = " | ".join(result.notes)
        assert "CPU:" in joined
        assert "Memory:" in joined
        assert "Replica minimum" in joined
        assert "Autoscaling replicas" in joined
        assert math.isclose(result.peak_factor, 2.0)


class TestValidateWorkloadRequirements:
    def test_valid_input_returns_empty(self) -> None:
        workload = _workload(average_rps=100.0, peak_rps=300.0)
        assert validate_workload_requirements(workload) == []

    def test_bursty_without_rps_numbers_flagged(self) -> None:
        workload = _workload(traffic_pattern="bursty")
        problems = validate_workload_requirements(workload)
        assert len(problems) == 1
        assert "bursty" in problems[0]

    def test_bursty_with_rps_numbers_is_fine(self) -> None:
        workload = _workload(traffic_pattern="bursty", average_rps=100.0, peak_rps=800.0)
        assert validate_workload_requirements(workload) == []

    def test_batch_with_sub_second_latency_flagged(self) -> None:
        workload = _workload(application_type="batch", max_latency_ms=100)
        problems = validate_workload_requirements(workload)
        assert len(problems) == 1
        assert "batch" in problems[0]
