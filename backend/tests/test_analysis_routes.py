import json

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import load_manifest

client = TestClient(app)

HEAVY_WORKLOAD = {
    "application_type": "e-commerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,
}


def test_validate_valid_manifest() -> None:
    response = client.post(
        "/api/v1/validate",
        files={"file": ("deployment.yaml", load_manifest("deployment-well-provisioned.yaml"), "application/x-yaml")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_invalid_manifest() -> None:
    response = client.post(
        "/api/v1/validate",
        files={"file": ("service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: web", "application/x-yaml")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) == 1


def test_validate_rejects_unsupported_extension() -> None:
    response = client.post(
        "/api/v1/validate",
        files={"file": ("deployment.txt", load_manifest("deployment-well-provisioned.yaml"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_analyze_without_workload_uses_defaults() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={"file": ("deployment.yaml", load_manifest("deployment-well-provisioned.yaml"), "application/x-yaml")},
    )
    assert analyze_response.status_code == 201
    analyze_data = analyze_response.json()
    analysis_id = analyze_data["analysis_id"]
    assert analyze_data["configuration"]["application"] == "api-backend"
    assert analyze_data["configuration"]["cpu_request"] == 0.5
    assert analyze_data["workload"]["application_type"] == "rest-api"
    assert analyze_data["workload"]["expected_users"] == 1000
    assert "features" in analyze_data
    assert analyze_data["features"]["total_cpu_capacity"] == 1.0

    get_response = client.get(f"/api/v1/analysis/{analysis_id}/configuration")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["analysis_id"] == analysis_id
    assert get_data["configuration"] == analyze_data["configuration"]


def test_analyze_with_workload_returns_features() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-heavy-overprovisioned.yaml"),
                "application/x-yaml",
            ),
            "workload": (None, json.dumps(HEAVY_WORKLOAD), "application/json"),
        },
    )
    assert analyze_response.status_code == 201
    analyze_data = analyze_response.json()

    assert analyze_data["workload"] == HEAVY_WORKLOAD
    features = analyze_data["features"]
    assert features["application_type_code"] == 2
    assert features["traffic_score"] == 2
    assert features["cpu"] == 8.0
    assert features["memory_gb"] == 16.0
    assert features["replicas"] == 8
    assert features["total_cpu_capacity"] == 64.0
    assert features["total_memory_capacity"] == 128.0
    assert features["users_per_replica"] == 1250.0

    analysis_id = analyze_data["analysis_id"]
    features_response = client.get(f"/api/v1/analysis/{analysis_id}/features")
    assert features_response.status_code == 200
    features_data = features_response.json()
    assert features_data["analysis_id"] == analysis_id
    assert features_data["workload"] == HEAVY_WORKLOAD
    assert features_data["features"] == features


def test_analyze_rejects_invalid_workload_json() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            ),
            "workload": (None, "{not-json", "application/json"),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid workload JSON"


def test_analyze_rejects_invalid_workload_values() -> None:
    invalid_workload = {**HEAVY_WORKLOAD, "expected_users": -5}
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            ),
            "workload": (None, json.dumps(invalid_workload), "application/json"),
        },
    )
    assert response.status_code == 422


def test_get_configuration_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/configuration")
    assert response.status_code == 404


def test_get_features_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/features")
    assert response.status_code == 404
