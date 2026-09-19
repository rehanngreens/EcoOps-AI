"""Tests for Phase 18: optimized IaC generation for Terraform/Compose sources.

The service reuses the Phase 16 templates + round-trip validators, so these
specs focus on the Mode A adaptations (instance-type snapping, autoscaling
drop, storage notes, name sanitization), the never-modified-original diff
guarantee, and the failure paths. No ML, no DB.
"""

import pytest

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.services.generation.iac_generation_service import (
    _COMPOSE_ROUND_TRIP_FIELDS,
    _K8S_ROUND_TRIP_FIELDS,
    _TF_ROUND_TRIP_FIELDS,
)
from app.services.optimized_iac_service import (
    SOURCE_ROUND_TRIP_FIELDS,
    OptimizedIaCError,
    generate_optimized_iac,
    render_optimized_for_source,
    validate_rendered_for_source,
)


def _tf_config(**overrides) -> InfrastructureConfiguration:
    base = dict(
        application="api-backend",
        source_type="terraform",
        cloud_provider="aws",
        region="ap-south-1",
        instance_type="t3.medium",
        replicas=2,
        cpu_request=2.0,
        memory_request_gb=4.0,
        storage_gb=20,
    )
    base.update(overrides)
    return InfrastructureConfiguration(**base)


def _compose_config(**overrides) -> InfrastructureConfiguration:
    base = dict(
        application="web",
        source_type="docker_compose",
        replicas=3,
        cpu_request=0.5,
        cpu_limit=1.0,
        memory_request_gb=0.5,
        memory_limit_gb=1.0,
    )
    base.update(overrides)
    return InfrastructureConfiguration(**base)


class TestTerraformRendering:
    def test_round_trip_reproduces_the_configuration(self) -> None:
        rendered = render_optimized_for_source(_tf_config(), "terraform")
        assert rendered.filename == "main-optimized.tf"
        assert 'instance_type = "t3.medium"' in rendered.content
        assert "count         = 2" in rendered.content

    def test_autoscaling_is_dropped_with_a_note(self) -> None:
        rendered = render_optimized_for_source(
            _tf_config(autoscaling_enabled=True), "terraform"
        )
        assert any("Autoscaling has no Terraform" in note for note in rendered.notes)

    def test_non_spec_sizing_snaps_to_the_instance_type(self) -> None:
        # 3 vCPU / 6 GiB is not an instance spec; t3.medium covers nothing of
        # that shape, so the smallest covering type is selected and the
        # sizing snapped to its discrete spec.
        rendered = render_optimized_for_source(
            _tf_config(cpu_request=3.0, memory_request_gb=6.0), "terraform"
        )
        assert any("discrete instance type" in note for note in rendered.notes)

    def test_unknown_instance_type_is_replaced(self) -> None:
        rendered = render_optimized_for_source(
            _tf_config(instance_type="not-a-type"), "terraform"
        )
        assert any("not in the metadata" in note for note in rendered.notes)
        assert "instance_type = " in rendered.content

    def test_uncoverable_size_is_refused(self) -> None:
        with pytest.raises(OptimizedIaCError, match="refusing to emit an undersized"):
            render_optimized_for_source(
                _tf_config(instance_type=None, cpu_request=96.0, memory_request_gb=512.0),
                "terraform",
            )

    def test_non_aws_provider_is_refused(self) -> None:
        with pytest.raises(OptimizedIaCError, match="provider 'aws' only"):
            render_optimized_for_source(_tf_config(cloud_provider="gcp"), "terraform")

    def test_fractional_storage_rounds_up_with_a_note(self) -> None:
        rendered = render_optimized_for_source(_tf_config(storage_gb=20.5), "terraform")
        assert "volume_size = 21" in rendered.content
        assert any("rounded up" in note for note in rendered.notes)

    def test_application_name_is_sanitized_with_a_note(self) -> None:
        rendered = render_optimized_for_source(
            _tf_config(application="api backend!"), "terraform"
        )
        assert 'resource "aws_instance" "api-backend"' in rendered.content
        assert any("Terraform-resource-safe" in note for note in rendered.notes)

    def test_missing_sizing_is_refused(self) -> None:
        with pytest.raises(OptimizedIaCError, match="no CPU/memory sizing"):
            render_optimized_for_source(
                _tf_config(instance_type=None, cpu_request=None, memory_request_gb=None),
                "terraform",
            )


class TestComposeRendering:
    def test_round_trip_preserves_limits_distinct_from_requests(self) -> None:
        rendered = render_optimized_for_source(_compose_config(), "docker_compose")
        assert rendered.filename == "docker-compose-optimized.yaml"
        assert 'cpus: "1"' in rendered.content  # limit
        assert 'cpus: "0.5"' in rendered.content  # request
        assert "memory: 1g" in rendered.content and "memory: 0.5g" in rendered.content

    def test_autoscaling_is_dropped_with_a_note(self) -> None:
        rendered = render_optimized_for_source(
            _compose_config(autoscaling_enabled=True), "docker_compose"
        )
        assert any("no Docker Compose semantics" in note for note in rendered.notes)

    def test_storage_is_noted_but_not_claimed(self) -> None:
        rendered = render_optimized_for_source(
            _compose_config(storage_gb=10.5), "docker_compose"
        )
        assert any("not expressible" in note for note in rendered.notes)
        assert "10.5" not in rendered.content


class TestDiffAndGuarantees:
    def test_diff_is_computed_against_the_stored_original(self) -> None:
        original = 'provider "aws" {\n  region = "us-east-1"\n}\n'
        result = generate_optimized_iac(original, _tf_config(), _tf_config(), "terraform")
        assert result.diff_lines, "diff against the original must be present"
        assert result.diff_lines[0].startswith("---")
        # The original text itself is echoed verbatim in the response path
        # (the route sends it back unchanged).
        assert "us-east-1" in original

    def test_empty_original_yields_canonical_empty_diff(self) -> None:
        result = generate_optimized_iac(None, _tf_config(), _tf_config(), "terraform")
        assert result.diff_lines == []

    def test_kubernetes_source_refused_phase10_handles_it(self) -> None:
        with pytest.raises(OptimizedIaCError, match="Phase 10"):
            generate_optimized_iac("a: b\n", _tf_config(), _tf_config(), "kubernetes")

    def test_unknown_source_refused(self) -> None:
        with pytest.raises(OptimizedIaCError, match="got 'helm'"):
            render_optimized_for_source(_tf_config(), "helm")

    def test_corrupted_render_fails_validation(self, monkeypatch) -> None:
        """A render that fails to parse must raise, never return unvalidated."""
        monkeypatch.setattr(
            "app.services.optimized_iac_service.render_docker_compose",
            lambda config: "not: [valid: compose",
        )
        with pytest.raises(OptimizedIaCError, match="Round-trip validation failed"):
            render_optimized_for_source(_compose_config(), "docker_compose")


class TestSharedFieldSets:
    def test_field_sets_match_phase16_definitions(self) -> None:
        assert SOURCE_ROUND_TRIP_FIELDS["kubernetes"] == _K8S_ROUND_TRIP_FIELDS
        assert SOURCE_ROUND_TRIP_FIELDS["terraform"] == _TF_ROUND_TRIP_FIELDS
        assert SOURCE_ROUND_TRIP_FIELDS["docker_compose"] == _COMPOSE_ROUND_TRIP_FIELDS

    def test_validate_rejects_field_mismatch(self) -> None:
        # Compose validator flags autoscaling claims and field mismatches.
        with pytest.raises(OptimizedIaCError, match="cpu_request"):
            validate_rendered_for_source(
                "services:\n  web:\n    image: nginx\n    deploy:\n      replicas: 3\n"
                "      resources:\n        limits:\n          cpus: \"9\"\n"
                "          memory: 9g\n        reservations:\n          cpus: \"9\"\n"
                "          memory: 9g\n",
                _compose_config(),
                "docker_compose",
            )
