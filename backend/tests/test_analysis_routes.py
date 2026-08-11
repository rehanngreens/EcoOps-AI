from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import load_manifest

client = TestClient(app)


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


def test_analyze_and_get_configuration() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={"file": ("deployment.yaml", load_manifest("deployment-well-provisioned.yaml"), "application/x-yaml")},
    )
    assert analyze_response.status_code == 201
    analyze_data = analyze_response.json()
    analysis_id = analyze_data["analysis_id"]
    assert analyze_data["configuration"]["application"] == "api-backend"
    assert analyze_data["configuration"]["cpu_request"] == 0.5

    get_response = client.get(f"/api/v1/analysis/{analysis_id}/configuration")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["analysis_id"] == analysis_id
    assert get_data["configuration"] == analyze_data["configuration"]


def test_get_configuration_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/configuration")
    assert response.status_code == 404
