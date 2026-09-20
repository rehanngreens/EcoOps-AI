"""Tests for Phase 16 target selection (design doc section 44.4).

Table-driven over the ordered rule list: each rule fires for its case,
precedence holds (first match wins), and explicit user choice bypasses
the rules entirely. No ML, no LLM — pure deterministic rules.
"""

import pytest

from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.target_selector import select_target, select_target_auto


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "rest-api",
        "expected_users": 500,
        "traffic_level": "medium",
        "max_latency_ms": 200,
        "availability_target": 99.0,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


# (name, workload, expected target, expected explanation fragment)
RULE_TABLE = [
    (
        "rule1_batch_to_compose",
        _workload(application_type="batch"),
        "docker_compose",
        "Rule 1",
    ),
    (
        "rule2_database_with_storage",
        _workload(application_type="database", storage_gb=200.0),
        "terraform+kubernetes",
        "Rule 2",
    ),
    (
        "rule2_database_without_storage",
        _workload(application_type="database"),
        "terraform",
        "Rule 2",
    ),
    (
        "rule3_bursty_autoscaling",
        _workload(autoscaling_required=True, traffic_pattern="bursty"),
        "kubernetes",
        "Rule 3",
    ),
    (
        "rule3_ecommerce_autoscaling",
        _workload(application_type="e-commerce", autoscaling_required=True),
        "kubernetes",
        "Rule 3",
    ),
    (
        "rule3_streaming_autoscaling",
        _workload(application_type="streaming", autoscaling_required=True),
        "kubernetes",
        "Rule 3",
    ),
    (
        "rule4_machine_learning",
        _workload(application_type="machine-learning"),
        "kubernetes",
        "Rule 4",
    ),
    (
        "rule4_ai_inference",
        _workload(application_type="ai-inference"),
        "kubernetes",
        "Rule 4",
    ),
    (
        "rule5_plain_autoscaling",
        _workload(autoscaling_required=True),
        "kubernetes",
        "Rule 5",
    ),
    (
        "rule6_huge_users",
        _workload(expected_users=150_000),
        "terraform+kubernetes",
        "Rule 6",
    ),
    (
        "rule6_high_availability",
        _workload(availability_target=99.95),
        "terraform+kubernetes",
        "Rule 6",
    ),
    (
        "rule7_small_service",
        _workload(),
        "docker_compose",
        "Rule 7",
    ),
]


class TestAutoRules:
    @pytest.mark.parametrize("name,workload,expected,fragment", RULE_TABLE, ids=[r[0] for r in RULE_TABLE])
    def test_rule_table(self, name, workload, expected, fragment) -> None:
        selection = select_target_auto(workload)
        assert selection.target == expected, name
        assert fragment in selection.explanation, name
        assert selection.source == "auto"

    def test_first_match_wins_batch_beats_everything(self) -> None:
        # Batch + autoscaling + bursty + huge users: rule 1 still fires.
        selection = select_target_auto(
            _workload(
                application_type="batch",
                autoscaling_required=True,
                traffic_pattern="bursty",
                expected_users=500_000,
                availability_target=99.99,
            )
        )
        assert selection.target == "docker_compose"
        assert "Rule 1" in selection.explanation

    def test_database_beats_autoscaling_rule(self) -> None:
        selection = select_target_auto(
            _workload(application_type="database", autoscaling_required=True)
        )
        assert "Rule 2" in selection.explanation

    def test_gpu_beats_plain_autoscaling(self) -> None:
        selection = select_target_auto(
            _workload(application_type="machine-learning", autoscaling_required=True)
        )
        assert "Rule 4" in selection.explanation

    def test_deterministic(self) -> None:
        workload = _workload(autoscaling_required=True)
        first = select_target_auto(workload)
        second = select_target_auto(workload)
        assert first == second


class TestExplicitSelection:
    def test_user_choice_bypasses_rules(self) -> None:
        # Would be Rule 7 (docker_compose) if auto; the user wins.
        selection = select_target("kubernetes", _workload())
        assert selection.target == "kubernetes"
        assert selection.source == "user"

    def test_combo_alias_accepted(self) -> None:
        for spelling in ("terraform+kubernetes", "Terraform + Kubernetes", "terraform_kubernetes"):
            assert select_target(spelling, _workload()).target == "terraform+kubernetes"

    def test_invalid_target_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown generation target"):
            select_target("heroku", _workload())

    def test_none_means_auto(self) -> None:
        assert select_target(None, _workload()).source == "auto"
        assert select_target("auto", _workload()).source == "auto"
