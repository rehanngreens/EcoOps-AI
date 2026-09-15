"""Tests for Phase 16 IaC generation (design doc section 44.6).

The core guarantee: every rendered artifact re-parses through the SAME
parser that handles user uploads and reproduces the candidate's resource
fields exactly. Template tests are golden-smoke (structure, literals,
comments), not exhaustive snapshots.
"""

import pytest

from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile
from app.services.generation.candidate_generator import plans_for_workload
from app.services.generation.iac_generation_service import (
    IaCGenerationError,
    build_generation_result,
    generate_artifacts,
)
from app.services.generation.iac_templates import (
    render_docker_compose,
    render_kubernetes,
    render_terraform,
)
from app.services.generation.requirement_engine import estimate_requirements
from app.services.generation.target_selector import select_target


def _workload(**overrides: object) -> WorkloadProfile:
    values: dict = {
        "application_type": "rest-api",
        "expected_users": 2000,
        "traffic_level": "medium",
        "max_latency_ms": 250,
        "availability_target": 99.9,
        "average_rps": 200.0,
        "peak_rps": 500.0,
        "storage_gb": 50.0,
    }
    values.update(overrides)
    return WorkloadProfile(**values)  # type: ignore[arg-type]


def _selected_configuration(workload: WorkloadProfile) -> InfrastructureConfiguration:
    result_plans = plans_for_workload(workload)[1]
    return next(p for p in result_plans if p.variant == "balanced").configuration


def _vm_configuration(workload: WorkloadProfile) -> InfrastructureConfiguration:
    """The Terraform-shaped candidate: the one that carries storage_gb."""
    result_plans = plans_for_workload(workload)[1]
    return next(p for p in result_plans if p.variant == "vm-baseline").configuration


class TestRoundTripAllTargets:
    TARGETS = ["kubernetes", "terraform", "docker_compose", "terraform+kubernetes"]

    @pytest.mark.parametrize("target", TARGETS)
    def test_artifacts_round_trip_valid(self, target: str) -> None:
        config = _selected_configuration(_workload())
        artifacts = generate_artifacts(config, select_target(target, _workload()))
        assert artifacts
        assert all(a.round_trip_valid for a in artifacts)
        if target == "terraform+kubernetes":
            assert {a.filename for a in artifacts} == {"main.tf", "deployment.yaml"}

    def test_kubernetes_round_trip_reproduces_resources(self) -> None:
        config = _selected_configuration(_workload())
        artifacts = generate_artifacts(config, select_target("kubernetes", _workload()))
        content = artifacts[0].content
        assert f'replicas: {config.replicas}' in content
        assert f'memory: {_fmt(config.memory_request_gb)}Gi' in content
        assert f'cpu: "{_fmt(config.cpu_request)}"' in content

    def test_terraform_round_trip_reproduces_resources(self) -> None:
        # The VM-baseline candidate is the Terraform-shaped one: instance
        # type metadata and the requested storage come through.
        workload = _workload()
        config = _vm_configuration(workload)
        artifacts = generate_artifacts(config, select_target("terraform", workload))
        content = artifacts[0].content
        assert f'count         = {config.replicas}' in content
        assert f'volume_size = {int(config.storage_gb)}' in content  # storage kept
        assert config.instance_type in content

    def test_compose_round_trip_reproduces_resources(self) -> None:
        config = _selected_configuration(_workload())
        artifacts = generate_artifacts(config, select_target("docker_compose", _workload()))
        content = artifacts[0].content
        assert f'replicas: {config.replicas}' in content
        assert f'memory: {_fmt(config.memory_request_gb)}g' in content

    def test_generated_kubernetes_parses_like_an_upload(self) -> None:
        """The strongest check: the artifact IS a valid upload for its parser."""
        from app.parsers.kubernetes_parser import parse_kubernetes_yaml

        config = _selected_configuration(_workload())
        content = render_kubernetes(config)
        parsed = parse_kubernetes_yaml(content)
        assert parsed["source_type"] == "kubernetes"
        assert parsed["application"] == config.application
        assert parsed["cpu_request"] == config.cpu_request
        assert parsed["memory_request_gb"] == config.memory_request_gb
        assert parsed["replicas"] == config.replicas

    def test_elastic_to_compose_drops_autoscaling_with_note(self) -> None:
        workload = _workload(autoscaling_required=True)
        elastic = next(
            p for p in plans_for_workload(workload)[1] if p.variant == "elastic"
        )
        artifacts = generate_artifacts(
            elastic.configuration, select_target("docker_compose", workload)
        )
        assert artifacts[0].round_trip_valid
        assert artifacts[0].notes
        assert "autoscaling" in artifacts[0].notes[0]

    def test_storage_note_on_container_targets(self) -> None:
        # Only VM-shaped candidates carry storage; when such a candidate is
        # rendered for a container target, the storage limitation is noted.
        workload = _workload()
        config = _vm_configuration(workload)
        for target in ("kubernetes", "docker_compose"):
            artifacts = generate_artifacts(config, select_target(target, workload))
            assert any("storage" in note for note in artifacts[0].notes), target

    def test_terraform_rejects_non_aws_provider(self) -> None:
        config = _selected_configuration(_workload()).model_copy(
            update={"cloud_provider": "gcp"}
        )
        with pytest.raises(ValueError, match="provider 'aws' only"):
            render_terraform(config)

    def test_terraform_refuses_uncoverable_sizes(self) -> None:
        # 96 cores / 512 GiB per replica exceeds every table entry.
        config = InfrastructureConfiguration(
            source_type="kubernetes",
            application="huge-app",
            replicas=1,
            cpu_request=96.0,
            memory_request_gb=512.0,
        )
        with pytest.raises(ValueError, match="refusing to emit an undersized"):
            render_terraform(config)

    def test_mismatch_raises_generation_error(self, monkeypatch) -> None:
        """A corrupted render must raise, never return unvalidated output."""
        config = _selected_configuration(_workload())
        target_selection = select_target("kubernetes", _workload())

        def _broken_render(_config):
            return "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: wrong\n"

        monkeypatch.setattr(
            "app.services.generation.iac_generation_service.render_kubernetes",
            _broken_render,
        )
        with pytest.raises(IaCGenerationError, match="Round-trip validation failed"):
            generate_artifacts(config, target_selection)


class TestBuildGenerationResult:
    def test_full_result_for_recommended_evaluation(self, monkeypatch) -> None:
        # CI runners have no model artifacts; this test is about result
        # assembly, not predictions.
        from app.schemas.unified_schema import UtilizationPrediction
        from app.services import prediction_service

        monkeypatch.setattr(
            prediction_service,
            "predict_utilization",
            lambda features: UtilizationPrediction(
                cpu_utilization=0.4,
                memory_utilization=0.45,
                model_type="mock",
                model_created_at=None,
            ),
        )

        workload = _workload()
        from app.services.generation.evaluation_service import evaluate_generation

        evaluation = evaluate_generation(workload)
        target_selection = select_target("auto", workload)
        result = build_generation_result(evaluation, target_selection)

        assert result.generation_id
        # The default workload has availability 99.9%, so auto rule 6 fires.
        assert result.target_selection.target == "terraform+kubernetes"
        assert result.target_selection.source == "auto"
        assert result.artifacts
        assert all(a.round_trip_valid for a in result.artifacts)
        assert result.selected_configuration.cpu_request == (
            evaluation.candidates[evaluation.selected_index].plan.configuration.cpu_request
        )
        assert "never deploys" in result.disclaimer

    def test_infeasible_evaluation_cannot_generate(self) -> None:
        from app.schemas.generation_schema import GenerationEvaluation, ResourceRequirementsModel
        from app.services.generation.target_selector import select_target_auto

        evaluation = GenerationEvaluation(
            status="infeasible",
            requirements=ResourceRequirementsModel(
                cpu_cores=1, memory_gb=1, replica_estimate=1, replica_minimum=1,
                autoscaling_required=False, peak_factor=1.0,
            ),
            candidates=[],
            selected_index=None,
            weights_used={},
            ranking_explanation="none",
            infeasibility_explanation="everything failed",
            disclaimer="d",
        )
        with pytest.raises(IaCGenerationError, match="infeasible"):
            build_generation_result(evaluation, select_target_auto(_workload()))


class TestTemplateShape:
    def test_kubernetes_autoscaling_annotation_detected_by_parser(self) -> None:
        from app.parsers.kubernetes_parser import parse_kubernetes_yaml

        config = _selected_configuration(_workload()).model_copy(
            update={"autoscaling_enabled": True}
        )
        parsed = parse_kubernetes_yaml(render_kubernetes(config))
        assert parsed["autoscaling_enabled"] is True

    def test_rendered_artifacts_are_commented_and_literal(self) -> None:
        config = _selected_configuration(_workload())
        for content in (
            render_kubernetes(config),
            render_terraform(config),
            render_docker_compose(config),
        ):
            assert "Generated by EcoOps AI" in content
            assert "review before use" in content
            assert "${" not in content  # no interpolation, literal values only
            assert "var." not in content


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    if float(value) == int(value):
        return str(int(value))
    return f"{value:g}"
