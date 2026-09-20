"""Route tests for Docker Compose uploads (Phase 13)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
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


def _compose_file(name: str = "compose-heavy-overprovisioned.yaml") -> dict:
    return {"file": (name, load_compose(name), "application/x-yaml")}


def test_validate_valid_compose() -> None:
    response = client.post("/api/v1/validate", files=_compose_file("compose-well-provisioned.yaml"))
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_invalid_compose_lists_error() -> None:
    response = client.post(
        "/api/v1/validate",
        files={"file": ("compose.yaml", "services: {}\n", "application/x-yaml")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) == 1


def test_analyze_compose_end_to_end() -> None:
    response = client.post(
        "/api/v1/analyze",
        files=_compose_file(),
        data={"workload": json.dumps(WORKLOAD)},
    )
    assert response.status_code == 201
    data = response.json()

    configuration = data["configuration"]
    assert configuration["source_type"] == "docker_compose"
    assert configuration["application"] == "api-backend"
    assert configuration["replicas"] == 8
    assert configuration["cpu_request"] == 8.0
    assert configuration["memory_request_gb"] == 16.0
    assert configuration["autoscaling_enabled"] is False
    assert configuration["container_image"] == "ecommerce/api-backend:1.0.0"

    assert data["prediction"]["cpu_utilization"] == 0.25
    assert data["estimation"]["estimated_cost_usd"] > 0
    assert data["constraints"]["satisfied"] is not None


def test_compose_detected_despite_yaml_extension() -> None:
    """Compose and Kubernetes share the extension; content must decide."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("stack.yaml", load_compose("compose-heavy-overprovisioned.yaml"), "application/x-yaml")},
        data={"workload": json.dumps(WORKLOAD)},
    )
    assert response.status_code == 201
    assert response.json()["configuration"]["source_type"] == "docker_compose"


def test_kubernetes_yaml_not_mistaken_for_compose() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
        data={"workload": json.dumps(WORKLOAD)},
    )
    assert response.status_code == 201
    assert response.json()["configuration"]["source_type"] == "kubernetes"


def test_terraform_not_mistaken_for_compose() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("main.tf", load_terraform("main-well-provisioned.tf"), "text/x-terraform")},
        data={"workload": json.dumps(WORKLOAD)},
    )
    assert response.status_code == 201
    assert response.json()["configuration"]["source_type"] == "terraform"


def test_optimize_works_for_compose_analysis() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files=_compose_file(),
        data={"workload": json.dumps(WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
    assert optimize_response.status_code == 201
    assert optimize_response.json()["recommendation_set"]["status"] == "recommended"


def test_optimized_config_supported_for_compose_phase18() -> None:
    """Phase 18: the Kubernetes-only 400 gate is gone; a Compose analysis
    renders its optimized configuration through the Phase 16 template and
    round-trip validates it through the Phase 13 parser."""
    analyze_response = client.post(
        "/api/v1/analyze",
        files=_compose_file(),
        data={"workload": json.dumps(WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]
    client.post(f"/api/v1/analysis/{analysis_id}/optimize")

    config_response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")
    assert config_response.status_code == 200
    data = config_response.json()
    assert data["optimized_yaml"].startswith("# Generated by EcoOps AI")
    assert "services:" in data["optimized_yaml"]
    assert data["diff"], "diff against the stored original must be present"


def test_kubernetes_optimized_config_still_works() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-heavy-overprovisioned.yaml"),
                "application/x-yaml",
            )
        },
        data={"workload": json.dumps(WORKLOAD)},
    )
    analysis_id = analyze_response.json()["analysis_id"]
    client.post(f"/api/v1/analysis/{analysis_id}/optimize")

    config_response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")
    assert config_response.status_code == 200
