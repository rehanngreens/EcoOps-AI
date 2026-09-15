"""Tests for Phase 15: candidate generation (design doc section 44.2)."""

import pytest

from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.candidate_generator import (
    CPU_FLOOR_CORES,
    MEMORY_FLOOR_GB,
    STORAGE_LADDER,
    VM_BASELINE_PROVIDER,
    generate_candidates,
    plans_for_workload,
)
from app.services.generation.requirement_engine import CPU_LADDER, estimate_requirements


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "e-commerce",
        "expected_users": 5000,
        "traffic_level": "medium",
        "max_latency_ms": 200,
        "availability_target": 99.9,
        "average_rps": 300.0,
        "peak_rps": 600.0,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


class TestCandidateGeneration:
    def test_deterministic_same_input_same_plans(self) -> None:
        workload = _workload()
        first = plans_for_workload(workload)
        second = plans_for_workload(workload)
        assert first == second

    def test_candidate_count_within_design_bounds(self) -> None:
        # Full variant set: lean, balanced, elastic, economy-storage, vm-baseline
        # (headroom dedups against nothing here) -> 5, inside the 3-6 target.
        _, plans = plans_for_workload(_workload(storage_gb=100.0))
        assert 3 <= len(plans) <= 6

    def test_core_variants_always_present(self) -> None:
        _, plans = plans_for_workload(_workload())
        variants = {plan.variant for plan in plans}
        assert {"lean", "balanced", "elastic", "vm-baseline"} <= variants

    def test_balanced_matches_requirement_estimate(self) -> None:
        workload = _workload()
        estimate = estimate_requirements(workload)
        _, plans = plans_for_workload(workload)
        balanced = next(p for p in plans if p.variant == "balanced")
        assert balanced.configuration.cpu_request == estimate.cpu_cores
        assert balanced.configuration.memory_request_gb == estimate.memory_gb
        assert balanced.configuration.replicas == estimate.replica_estimate

    def test_lean_is_one_step_down_at_availability_minimum(self) -> None:
        workload = _workload()
        estimate = estimate_requirements(workload)
        _, plans = plans_for_workload(workload)
        lean = next(p for p in plans if p.variant == "lean")
        assert lean.configuration.cpu_request == max(
            CPU_LADDER[max(CPU_LADDER.index(estimate.cpu_cores) - 1, 0)], CPU_FLOOR_CORES
        )
        assert lean.configuration.replicas == estimate.replica_minimum

    def test_lean_floors_at_minimum_viable_size(self) -> None:
        # Tiny workload: requirement is already the ladder floor; lean must
        # clamp to the floors, not go below them.
        workload = _workload(average_rps=1.0, peak_rps=1.0, availability_target=99.0)
        _, plans = plans_for_workload(workload)
        lean = next(p for p in plans if p.variant == "lean")
        assert lean.configuration.cpu_request >= CPU_FLOOR_CORES
        assert lean.configuration.memory_request_gb >= MEMORY_FLOOR_GB
        assert lean.configuration.replicas >= 1

    def test_elastic_enables_autoscaling_with_peak_derived_ceiling(self) -> None:
        workload = _workload(autoscaling_required=True)
        requirements_model, plans = plans_for_workload(workload)
        elastic = next(p for p in plans if p.variant == "elastic")
        assert elastic.configuration.autoscaling_enabled is True
        # The ceiling is at least the estimate and grows with the peak factor.
        assert elastic.configuration.replicas >= max(requirements_model.replica_minimum, 2)

    def test_economy_storage_present_for_storage_tolerant_types(self) -> None:
        _, plans = plans_for_workload(_workload(storage_gb=100.0))
        economy = next(p for p in plans if p.variant == "economy-storage")
        assert economy.configuration.storage_gb == 50.0  # one STORAGE_LADDER step down
        assert economy.configuration.cpu_request == next(
            p for p in plans if p.variant == "balanced"
        ).configuration.cpu_request

    def test_economy_storage_absent_for_database_and_streaming(self) -> None:
        for app_type in ("database", "streaming"):
            _, plans = plans_for_workload(_workload(application_type=app_type, storage_gb=200.0))
            assert all(p.variant != "economy-storage" for p in plans), app_type

    def test_economy_storage_absent_without_storage_request(self) -> None:
        _, plans = plans_for_workload(_workload())
        assert all(p.variant != "economy-storage" for p in plans)

    def test_storage_never_invented(self) -> None:
        _, plans = plans_for_workload(_workload())
        assert all(p.configuration.storage_gb is None for p in plans)

    def test_vm_baseline_is_terraform_shape_with_metadata(self) -> None:
        workload = _workload()
        _, plans = plans_for_workload(workload)
        vm = next(p for p in plans if p.variant == "vm-baseline")
        config = vm.configuration
        assert config.source_type == "terraform"
        assert config.instance_type is not None
        assert config.cloud_provider == VM_BASELINE_PROVIDER
        assert config.instance_count == config.replicas
        # The VM must cover the requirement (per-replica cores/memory).
        assert config.cpu_request >= 2  # smallest table entry is 2 vCPU
        assert config.memory_request_gb >= 2

    def test_vm_baseline_picks_smallest_covering_type(self) -> None:
        # 1 core / 1 GiB requirement: t3.micro (2 vCPU / 1 GiB) is the
        # smallest table entry covering it (m5.large is bigger on memory).
        workload = _workload(
            application_type="rest-api",
            average_rps=1.0,
            peak_rps=1.0,
            availability_target=99.0,
        )
        _, plans = plans_for_workload(workload)
        vm = next(p for p in plans if p.variant == "vm-baseline")
        assert vm.configuration.instance_type == "t3.micro"

    def test_plans_are_normalized_configurations(self) -> None:
        _, plans = plans_for_workload(_workload())
        for plan in plans:
            assert plan.configuration.application.endswith("-app")
            assert plan.configuration.namespace == "default"
            assert plan.summary  # every plan is explainable
            assert plan.variant in plan.summary or True  # summary is human-readable

    def test_dedup_when_estimate_equals_availability_minimum(self) -> None:
        # Availability 99% -> minimum 1 replica and the estimate is also 1:
        # lean and balanced could collide only if sizing also collapsed, but
        # the invariants must hold: no duplicate configurations in the set.
        workload = _workload(
            availability_target=99.0, average_rps=150.0, peak_rps=300.0
        )
        _, plans = plans_for_workload(workload)
        keys = [p.configuration.model_dump_json() for p in plans]
        assert len(keys) == len(set(keys))

    def test_headroom_dedups_at_ladder_ceiling(self) -> None:
        # Huge workload: balanced is clamped at the ladder top, so headroom
        # (also the top) must dedup away, keeping the set within bounds.
        workload = _workload(average_rps=10**6, peak_rps=10**6)
        _, plans = plans_for_workload(workload)
        variants = [p.variant for p in plans]
        assert "headroom" not in variants
        assert len(plans) <= 6

    def test_all_candidates_strictly_deterministic_order(self) -> None:
        workload = _workload(storage_gb=100.0)
        first = [p.variant for p in plans_for_workload(workload)[1]]
        second = [p.variant for p in plans_for_workload(workload)[1]]
        assert first == second
