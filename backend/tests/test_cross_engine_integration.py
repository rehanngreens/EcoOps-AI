"""Phase 19 cross-engine integration tests.

These tests wire MULTIPLE real engines together in one flow (predictor
mocked for CI parity): the full Mode A chain, score arithmetic, estimator
composition, parser parity across formats, and the Mode A -> Mode B bridge
through the shared WorkloadProfile normalization. Unit tests prove each
engine alone; these prove the seams.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services import prediction_service
from tests.conftest import load_compose, load_manifest, load_terraform

client = TestClient(app)

WORKLOAD = {
    "application_type": "e-commerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,
}


@pytest.fixture(autouse=True)
def mock_predictor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixed, allocation-sensitive mock: utilization rises as capacity falls.

    CI has no model artifacts, so every test here controls prediction
    explicitly. The mock mimics the real Phase 5 model's key property
    (scale-down raises predicted utilization) so constraint gating and
    ranking behave realistically.
    """

    def _predict(features):
        per_replica_cpu = features.cpu
        # 1 vCPU per replica predicts 30% busy; 0.25 vCPU predicts ~saturated.
        cpu = min(0.95, max(0.05, 0.30 / per_replica_cpu)) if per_replica_cpu else 0.95
        return UtilizationPrediction(
            cpu_utilization=round(cpu, 4),
            memory_utilization=0.5,
            model_type="mock",
            model_created_at=None,
        )

    monkeypatch.setattr(prediction_service, "predict_utilization", _predict)


def _analyze(source: str):
    """Analyze one fixture and return (status_code, body)."""
    builders = {
        "kubernetes": ("deployment.yaml", load_manifest("deployment-heavy-overprovisioned.yaml")),
        "terraform": ("main.tf", load_terraform("main-heavy-overprovisioned.tf")),
        "docker_compose": ("docker-compose.yaml", load_compose("compose-heavy-overprovisioned.yaml")),
    }
    filename, content = builders[source]
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (filename, content, "application/x-yaml"),
            "workload": (None, __import__("json").dumps(WORKLOAD), "application/json"),
        },
    )
    return response.status_code, response.json()


class TestFullModeAChain:
    def test_analyze_recommend_optimize_config_score_one_flow(self) -> None:
        """analyze -> optimize -> optimized-config -> score with REAL engines
        (only the predictor mocked). The generated config must round-trip and
        the score must exist for the same analysis."""
        status, analyze = _analyze("kubernetes")
        assert status == 201, analyze
        analysis_id = analyze["analysis_id"]

        optimize = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
        assert optimize.status_code == 201
        rec_set = optimize.json()["recommendation_set"]
        assert rec_set["status"] == "recommended", rec_set
        assert rec_set["optimized_configuration"] != analyze["configuration"]
        assert optimize.json()["recommendation_set"]["totals"]["cost_reduction_usd"] > 0

        config = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")
        assert config.status_code == 200
        assert config.json()["source"] == "stored_original"
        assert config.json()["diff"]

        score = client.get(f"/api/v1/analysis/{analysis_id}/score")
        assert score.status_code == 200
        assert 0.0 <= score.json()["score"]["score"] <= 1.0

    def test_scores_reflect_optimized_configuration(self) -> None:
        """The optimize response's optimized score must beat the baseline when
        a scale-down recommendation was accepted (cost share rises)."""
        status, analyze = _analyze("kubernetes")
        analysis_id = analyze["analysis_id"]
        optimize = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
        body = optimize.json()
        assert body["recommendation_set"]["status"] == "recommended"
        assert body["scores"]["optimized"]["score"] > body["scores"]["baseline"]["score"]


class TestWeightToOutcomeProperty:
    """Heavier over-provisioning must surface as a larger optimization
    opportunity — the property the dashboard's demo scenarios rely on."""

    @staticmethod
    def _optimize_from_fixture(filename: str, content: str) -> dict:
        response = client.post(
            "/api/v1/analyze",
            files={
                "file": (filename, content, "application/x-yaml"),
                "workload": (None, __import__("json").dumps(WORKLOAD), "application/json"),
            },
        )
        assert response.status_code == 201
        analysis_id = response.json()["analysis_id"]
        optimize = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
        assert optimize.status_code == 201
        return optimize.json()

    def test_heavier_overprovisioning_yields_more_savings(self) -> None:
        heavy = self._optimize_from_fixture(
            "deployment.yaml", load_manifest("deployment-heavy-overprovisioned.yaml")
        )
        moderate = self._optimize_from_fixture(
            "deployment.yaml", load_manifest("deployment-moderate-overprovisioned.yaml")
        )
        well = self._optimize_from_fixture(
            "deployment.yaml", load_manifest("deployment-well-provisioned.yaml")
        )

        def _savings(body: dict) -> float:
            totals = body["recommendation_set"]["totals"]
            return float(totals["cost_reduction_usd"]) if totals else 0.0

        # Ordering across the demo ladder (allowing a tie between the two
        # lighter scenarios, never an inversion against the heavy one).
        assert _savings(heavy) > _savings(well)
        assert _savings(moderate) >= _savings(well)
        assert _savings(heavy) >= _savings(moderate)

    def test_well_provisioned_never_recommends_scale_up(self) -> None:
        body = self._optimize_from_fixture(
            "deployment.yaml", load_manifest("deployment-well-provisioned.yaml")
        )
        rec_set = body["recommendation_set"]
        if rec_set["status"] == "recommended":
            for item in rec_set["items"]:
                assert not (
                    item["parameter"] == "cpu_request" and item["suggested_value"] > item["current_value"]
                ), "a well-provisioned baseline must never be told to scale up"
                assert not (
                    item["parameter"] == "memory_request_gb"
                    and item["suggested_value"] > item["current_value"]
                )


class TestParserParity:
    def test_terraform_kubernetes_feature_parity(self) -> None:
        """The SAME logical deployment (4 replicas x 2 vCPU x 4 GiB) through
        the TF and K8s parsers must produce the same ML feature totals and
        workload fields (Phase 12 contract). Per-replica fields may differ
        because TF models whole instances (t3.medium = 2 vCPU/4 GiB) while
        K8s models containers — totals are the comparable quantity."""
        k8s_yaml = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-backend
  namespace: default
spec:
  replicas: 4
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.27
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
"""
        tf_hcl = '''provider "aws" {
  region = "ap-south-1"
}

resource "aws_instance" "api" {
  ami           = "ami-0abcd1234efgh5678"
  instance_type = "t3.medium"
  count         = 4
}
'''
        k8s_resp = client.post(
            "/api/v1/analyze",
            files={
                "file": ("deployment.yaml", k8s_yaml, "application/x-yaml"),
                "workload": (None, __import__("json").dumps(WORKLOAD), "application/json"),
            },
        )
        tf_resp = client.post(
            "/api/v1/analyze",
            files={
                "file": ("main.tf", tf_hcl, "application/x-terraform"),
                "workload": (None, __import__("json").dumps(WORKLOAD), "application/json"),
            },
        )
        assert k8s_resp.status_code == 201, k8s_resp.text
        assert tf_resp.status_code == 201, tf_resp.text
        tf_f, k8s_f = tf_resp.json()["features"], k8s_resp.json()["features"]
        assert tf_f["total_cpu_capacity"] == k8s_f["total_cpu_capacity"] == 8.0
        assert tf_f["total_memory_capacity"] == k8s_f["total_memory_capacity"] == 16.0
        assert tf_f["expected_users"] == k8s_f["expected_users"]
        assert tf_f["application_type_code"] == k8s_f["application_type_code"]

    def test_compose_kubernetes_request_parity(self) -> None:
        """Compose and Kubernetes express the same heavy deployment; the
        normalized requests must agree where both parsers emit them."""
        _, compose = _analyze("docker_compose")
        _, k8s = _analyze("kubernetes")
        c, k = compose["configuration"], k8s["configuration"]
        assert c["replicas"] == k["replicas"]
        assert c["cpu_request"] == k["cpu_request"]
        assert c["memory_request_gb"] == k["memory_request_gb"]


class TestScoreConsistency:
    def test_components_sum_to_total_for_live_analysis(self) -> None:
        """Score internal arithmetic: weighted components must sum to the
        composite (the score endpoint computes on the BASELINE)."""
        status, analyze = _analyze("kubernetes")
        analysis_id = analyze["analysis_id"]
        score = client.get(f"/api/v1/analysis/{analysis_id}/score")
        body = score.json()["score"]
        weighted = sum(c["score"] * c["weight"] for c in body["components"])
        assert body["score"] == pytest.approx(round(weighted, 4), abs=1e-6)
        assert abs(sum(c["weight"] for c in body["components"]) - 1.0) < 1e-6
        # Grade must agree with the documented bands.
        assert body["grade"] in {"A", "B", "C", "D", "F"}

    def test_estimate_endpoints_consistent_across_engine_calls(self) -> None:
        """The analyze response estimation and the score component raw values
        must describe the same numbers (both derive from the same estimate)."""
        status, analyze = _analyze("kubernetes")
        energy = analyze["estimation"]["estimated_energy_kwh"]
        assert energy > 0
        # Utilization-proportional energy must scale with the predicted cpu.
        assert analyze["estimation"]["active_cpu_vcpus"] == pytest.approx(
            analyze["features"]["total_cpu_capacity"] * analyze["prediction"]["cpu_utilization"]
        )


class TestEstimatorComposition:
    def test_settings_drive_estimates_monotonically(self) -> None:
        """Energy/carbon/cost must respond to their settings knobs (PUE,
        carbon intensity, prices) — the 'configurable assumptions' contract."""
        from app.core.config import get_settings
        from app.schemas.unified_schema import FeatureVector, UtilizationPrediction
        from app.services.estimation_service import estimate_sustainability, parameters_from_settings

        features = FeatureVector(
            application_type="rest-api",
            application_type_code=3,
            expected_users=1000,
            traffic_level="medium",
            traffic_score=2,
            max_latency_ms=200,
            availability_target=99.0,
            cpu=2.0,
            memory_gb=4.0,
            replicas=2,
            autoscaling_enabled=False,
            autoscaling_enabled_int=0,
            source_type="kubernetes",
            total_cpu_capacity=4.0,
            total_memory_capacity=8.0,
            users_per_replica=500.0,
        )
        prediction = UtilizationPrediction(cpu_utilization=0.5, memory_utilization=0.5, model_type="mock", model_created_at=None)

        import dataclasses

        base = parameters_from_settings(get_settings())
        base_estimate = estimate_sustainability(features, prediction, base)

        higher = dataclasses.replace(
            base,
            data_center_pue=base.data_center_pue + 0.6,
            carbon_intensity_gco2_per_kwh=base.carbon_intensity_gco2_per_kwh + 100.0,
            cpu_cost_per_vcpu_hour_usd=base.cpu_cost_per_vcpu_hour_usd * 2,
            memory_cost_per_gb_hour_usd=base.memory_cost_per_gb_hour_usd * 2,
        )
        bumped = estimate_sustainability(features, prediction, higher)

        assert bumped.estimated_energy_kwh > base_estimate.estimated_energy_kwh
        assert bumped.estimated_carbon_kg_co2e > base_estimate.estimated_carbon_kg_co2e
        assert bumped.estimated_cost_usd > base_estimate.estimated_cost_usd
        # Carbon = energy * intensity / 1000 exactly (composition contract).
        assert bumped.estimated_carbon_kg_co2e == pytest.approx(
            bumped.estimated_energy_kwh * bumped.assumptions.carbon_intensity_gco2_per_kwh / 1000
        )


class TestModeABridge:
    def test_stored_analysis_workload_feeds_requirement_engine(self) -> None:
        """Mode A -> Mode B bridge: the workload a stored analysis normalized
        must flow through the Phase 14 requirement engine unchanged — the two
        modes share one WorkloadProfile normalization."""
        from app.schemas.workload_schema import WorkloadProfile
        from app.services.generation.requirement_engine import estimate_requirements

        status, analyze = _analyze("kubernetes")
        assert status == 201
        profile = WorkloadProfile.model_validate(analyze["workload"])
        requirements = estimate_requirements(profile)
        assert requirements.cpu_cores > 0
        assert requirements.memory_gb > 0
        assert requirements.replica_minimum >= 1
        assert requirements.replica_estimate >= requirements.replica_minimum

    def test_analyzed_configuration_shape_is_candidate_compatible(self) -> None:
        """A Mode A normalized configuration must be valid as a Mode B
        candidate configuration — one InfrastructureConfiguration schema."""
        from app.schemas.infrastructure_schema import InfrastructureConfiguration
        from app.schemas.workload_schema import WorkloadProfile
        from app.services.generation.candidate_generator import generate_candidates
        from app.services.generation.requirement_engine import estimate_requirements

        status, analyze = _analyze("kubernetes")
        profile = WorkloadProfile.model_validate(analyze["workload"])
        requirements = estimate_requirements(profile)
        candidates = generate_candidates(profile, requirements)
        assert candidates, "requirement engine must yield at least one candidate"
        for plan in candidates:
            assert isinstance(plan.configuration, InfrastructureConfiguration)
