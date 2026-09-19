"""Route tests for Terraform uploads (Phase 12)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services.prediction_service import ModelArtifactsUnavailableError
from tests.conftest import load_manifest, load_terraform

client = TestClient(app)

TERRAFORM_WORKLOAD = {
    "application_type": "e-commerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,
}


@pytest.fixture(autouse=True)
def mock_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.analysis.prediction_service.predict_utilization",
        lambda _: UtilizationPrediction(
            cpu_utilization=0.25,
            memory_utilization=0.5,
            model_type="RandomForestRegressor",
            model_created_at="2026-09-13T00:00:00+00:00",
        ),
    )


def _tf_file(name: str = "main-heavy-overprovisioned.tf") -> dict:
    return {"file": (name, load_terraform(name), "text/x-terraform")}


def test_validate_valid_terraform() -> None:
    response = client.post("/api/v1/validate", files=_tf_file("main-well-provisioned.tf"))
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_invalid_terraform_lists_error() -> None:
    response = client.post(
        "/api/v1/validate",
        files={"file": ("broken.tf", "resource \"aws_instance\" \"api\" {\n", "text/x-terraform")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) == 1


def test_analyze_terraform_end_to_end() -> None:
    response = client.post(
        "/api/v1/analyze",
        files=_tf_file(),
        data={"workload": json.dumps(TERRAFORM_WORKLOAD)},
    )
    assert response.status_code == 201
    data = response.json()

    configuration = data["configuration"]
    assert configuration["source_type"] == "terraform"
    assert configuration["application"] == "web-frontend"
    assert configuration["replicas"] == 8
    assert configuration["cpu_request"] == 8.0
    assert configuration["memory_request_gb"] == 32.0
    assert configuration["cloud_provider"] == "aws"
    assert configuration["region"] == "ap-south-1"
    assert configuration["instance_type"] == "m5.2xlarge"

    assert data["workload"]["application_type"] == "e-commerce"
    assert data["prediction"]["cpu_utilization"] == 0.25
    assert data["estimation"]["estimated_cost_usd"] > 0
    assert data["estimation"]["estimated_energy_kwh"] > 0
    assert data["estimation"]["estimated_carbon_kg_co2e"] > 0
    assert data["constraints"]["satisfied"] is not None


def test_analyze_terraform_without_workload_uses_defaults() -> None:
    response = client.post(
        "/api/v1/analyze",
        files=_tf_file("main-well-provisioned.tf"),
    )
    assert response.status_code == 201
    assert response.json()["workload"]["application_type"] == "rest-api"


def test_terraform_content_detected_even_with_wrong_extension() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("config.txt", load_terraform("main-well-provisioned.tf"), "text/plain")},
    )
    # .txt is not in the allow-list, so it must be rejected by extension...
    assert response.status_code == 400


def test_yaml_still_parses_after_terraform_detection() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("deployment.yaml", load_manifest("deployment-well-provisioned.yaml"), "application/x-yaml")},
        data={"workload": json.dumps(TERRAFORM_WORKLOAD)},
    )
    assert response.status_code == 201
    assert response.json()["configuration"]["source_type"] == "kubernetes"


def test_optimize_works_for_terraform_analysis() -> None:
    """Optimize (recommendation ranking) is source-agnostic; only YAML
    generation is Kubernetes-only. A heavily overprovisioned Terraform
    analysis should still produce recommendations."""
    analyze_response = client.post(
        "/api/v1/analyze",
        files=_tf_file(),
        data={"workload": json.dumps(TERRAFORM_WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
    assert optimize_response.status_code == 201
    assert optimize_response.json()["recommendation_set"]["status"] == "recommended"


def test_optimized_config_supported_for_terraform_phase18() -> None:
    """Phase 18: the Kubernetes-only 400 gate is gone; a Terraform analysis
    renders its optimized configuration through the Phase 16 template and
    round-trip validates it through the Phase 12 parser."""
    analyze_response = client.post(
        "/api/v1/analyze",
        files=_tf_file(),
        data={"workload": json.dumps(TERRAFORM_WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]

    client.post(f"/api/v1/analysis/{analysis_id}/optimize")

    config_response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")
    assert config_response.status_code == 200
    data = config_response.json()
    assert data["optimized_yaml"].startswith("# Generated by EcoOps AI")
    assert 'resource "aws_instance"' in data["optimized_yaml"]
    assert data["diff"], "diff against the stored original must be present"
    # Instance-type metadata preserved by the render config.
    assert "instance_type" in data["optimized_yaml"]


def test_optimized_config_still_works_for_kubernetes() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={"file": ("deployment.yaml", load_manifest("deployment-heavy-overprovisioned.yaml"), "application/x-yaml")},
        data={"workload": json.dumps(TERRAFORM_WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
    assert optimize_response.status_code == 201

    config_response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")
    assert config_response.status_code == 200
