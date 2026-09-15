import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services.prediction_service import ModelArtifactsUnavailableError
from tests.conftest import load_manifest

client = TestClient(app)

HEAVY_WORKLOAD = {
    "application_type": "e-commerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,
}


@pytest.fixture(autouse=True)
def mock_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep route tests independent of ignored local model artifacts."""
    monkeypatch.setattr(
        "app.api.routes.analysis.prediction_service.predict_utilization",
        lambda _: UtilizationPrediction(
            cpu_utilization=0.25,
            memory_utilization=0.5,
            model_type="RandomForestRegressor",
            model_created_at="2026-09-13T00:00:00+00:00",
        ),
    )

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
    assert analyze_data["prediction"]["cpu_utilization"] == 0.25
    assert analyze_data["prediction"]["memory_utilization"] == 0.5
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

    # Phase 14 added optional v2 workload fields to the echoed profile, so
    # compare the submitted v1 fields as a subset instead of exact equality.
    assert HEAVY_WORKLOAD.items() <= analyze_data["workload"].items()
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
    # v2 fields are additive in the echoed profile; compare v1 fields as a subset.
    assert HEAVY_WORKLOAD.items() <= features_data["workload"].items()
    assert analyze_data["prediction"]["model_type"] == "RandomForestRegressor"
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

def test_analyze_reports_missing_model_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(_: object) -> UtilizationPrediction:
        raise ModelArtifactsUnavailableError("Model artifacts are unavailable. Run: python ml/train_model.py")

    monkeypatch.setattr(
        "app.api.routes.analysis.prediction_service.predict_utilization", unavailable
    )
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": ("deployment.yaml", load_manifest("deployment-well-provisioned.yaml"), "application/x-yaml")
        },
    )
    assert response.status_code == 503
    assert "python ml/train_model.py" in response.json()["detail"]


def test_get_configuration_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/configuration")

    assert response.status_code == 404


def test_analyze_returns_transparent_estimation() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
    )
    assert response.status_code == 201
    estimation = response.json()["estimation"]
    assert estimation["estimated_cost_usd"] > 0
    assert estimation["estimated_energy_kwh"] >= 0
    assert estimation["estimated_carbon_kg_co2e"] >= 0
    assert "not measured usage" in estimation["disclaimer"]


def test_get_features_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/features")
    assert response.status_code == 404


def test_analyze_includes_constraint_evaluation() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            ),
            "workload": (None, json.dumps(HEAVY_WORKLOAD), "application/json"),
        },
    )

    assert response.status_code == 201
    constraints = response.json()["constraints"]
    assert isinstance(constraints["satisfied"], bool)
    check_names = {check["name"] for check in constraints["checks"]}
    assert check_names == {
        "cpu_headroom",
        "memory_headroom",
        "latency_feasibility",
        "availability_replicas",
        "user_capacity",
    }
    for check in constraints["checks"]:
        assert check["status"] in {"pass", "fail"}
        assert check["required"]
        assert check["actual"]
        assert check["explanation"]
    assert "not measured performance" in constraints["disclaimer"]


def test_constraints_endpoint_recomputes_from_stored_analysis() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
    )
    analysis_id = analyze_response.json()["analysis_id"]

    response = client.get(f"/api/v1/analysis/{analysis_id}/constraints")

    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == analysis_id
    assert data["constraints"]["satisfied"] is True
    assert len(data["constraints"]["checks"]) == 5


def test_constraints_endpoint_not_found() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/constraints")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_optimize_on_missing_analysis_returns_404() -> None:
    response = client.post("/api/v1/analysis/nonexistent-id/optimize")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_optimize_and_get_recommendations_end_to_end() -> None:
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
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")

    assert optimize_response.status_code == 201
    optimize_data = optimize_response.json()
    recommendation_set = optimize_data["recommendation_set"]

    assert recommendation_set["status"] in {"recommended", "no_recommendation"}
    assert "advisory prototype estimates" in recommendation_set["disclaimer"]
    assert recommendation_set["baseline_configuration"]["replicas"] == 8

    scores = optimize_data["scores"]
    assert 0.0 <= scores["baseline"]["score"] <= 1.0
    assert len(scores["baseline"]["components"]) == 5

    if recommendation_set["status"] == "recommended":
        assert recommendation_set["optimized_configuration"] is not None
        assert recommendation_set["optimized_configuration"] != recommendation_set["baseline_configuration"]
        assert scores["optimized"] is not None
        assert scores["improvement"] is not None
        assert scores["improvement"] == pytest.approx(
            scores["optimized"]["score"] - scores["baseline"]["score"], abs=1e-4
        )
        totals = recommendation_set["totals"]
        assert totals["cost_reduction_usd"] >= 0
        assert totals["optimized"]["estimated_cost_usd"] <= totals["baseline"]["estimated_cost_usd"]
        assert len(recommendation_set["items"]) >= 1
        for item in recommendation_set["items"]:
            assert item["parameter"] in {
                "cpu_request",
                "memory_request_gb",
                "replicas",
                "autoscaling_enabled",
            }
            assert item["current_value"] != item["suggested_value"]
            assert item["reason"]
    else:
        assert recommendation_set["optimized_configuration"] is None
        assert len(recommendation_set["rejected_candidates"]) >= 1
        assert scores["optimized"] is None
        assert scores["improvement"] is None

    stored_response = client.get(f"/api/v1/analysis/{analysis_id}/recommendations")
    assert stored_response.status_code == 200
    stored_data = stored_response.json()
    assert stored_data["analysis_id"] == analysis_id
    assert stored_data["recommendation_set"]["status"] == recommendation_set["status"]
    assert stored_data["recommendation_set"]["items"] == recommendation_set["items"]
    stored_scores = stored_data["scores"]
    assert stored_scores["baseline"]["score"] == scores["baseline"]["score"]
    if recommendation_set["status"] == "recommended":
        assert stored_scores["optimized"]["score"] == scores["optimized"]["score"]
        assert stored_scores["improvement"] == scores["improvement"]


def test_recommendations_before_optimize_returns_404() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
    )
    analysis_id = analyze_response.json()["analysis_id"]

    response = client.get(f"/api/v1/analysis/{analysis_id}/recommendations")

    assert response.status_code == 404
    assert "run optimize first" in response.json()["detail"]


def test_recommendations_for_missing_analysis_returns_404() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/recommendations")

    assert response.status_code == 404


def test_optimized_config_end_to_end_with_real_round_trip() -> None:
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
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
    assert optimize_response.status_code == 201

    response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")

    if optimize_response.json()["recommendation_set"]["status"] != "recommended":
        assert response.status_code == 404
        return

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "stored_original"
    assert data["original_yaml"] == load_manifest("deployment-heavy-overprovisioned.yaml")
    assert "kind: Deployment" in data["optimized_yaml"]
    assert data["diff"], "diff should not be empty when a recommendation exists"
    assert any(change["parameter"] for change in data["changes"])
    assert "deploy manually" in data["disclaimer"]

    # Generated YAML must round-trip to the stored optimized configuration.
    import yaml as pyyaml

    from app.parsers.kubernetes_parser import parse_kubernetes_yaml

    parsed = parse_kubernetes_yaml(data["optimized_yaml"])
    stored_optimized = optimize_response.json()["recommendation_set"]["optimized_configuration"]
    # K8s-parser output excludes the Terraform-only optional fields; compare
    # on the parser's key set so the round-trip stays exact where it applies.
    assert parsed == {k: v for k, v in stored_optimized.items() if k in parsed}


def test_optimized_config_before_optimize_returns_404() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
    )
    analysis_id = analyze_response.json()["analysis_id"]

    response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")

    assert response.status_code == 404
    assert "run optimize first" in response.json()["detail"]


def test_optimized_config_when_no_recommendation_accepted_returns_404() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            ),
            "workload": (None, json.dumps(HEAVY_WORKLOAD), "application/json"),
        },
    )
    analysis_id = analyze_response.json()["analysis_id"]

    optimize_response = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
    assert optimize_response.status_code == 201

    if optimize_response.json()["recommendation_set"]["status"] == "recommended":
        pytest.skip("model recommended for this scenario; 404 path not applicable")

    response = client.get(f"/api/v1/analysis/{analysis_id}/optimized-config")

    assert response.status_code == 404
    assert "no accepted recommendation" in response.json()["detail"]


def test_optimized_config_missing_analysis_returns_404() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/optimized-config")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_score_endpoint_returns_weighted_components() -> None:
    analyze_response = client.post(
        "/api/v1/analyze",
        files={
            "file": (
                "deployment.yaml",
                load_manifest("deployment-well-provisioned.yaml"),
                "application/x-yaml",
            )
        },
    )
    assert analyze_response.status_code == 201
    analysis_id = analyze_response.json()["analysis_id"]

    response = client.get(f"/api/v1/analysis/{analysis_id}/score")

    assert response.status_code == 200
    data = response.json()["score"]
    assert 0.0 <= data["score"] <= 1.0
    assert data["grade"] in {"A", "B", "C", "D", "F"}
    assert len(data["components"]) == 5
    assert sum(c["weight"] for c in data["components"]) == pytest.approx(1.0)
    assert "weighted" in data["methodology"].lower()
    assert data["disclaimer"]


def test_score_endpoint_missing_analysis_returns_404() -> None:
    response = client.get("/api/v1/analysis/nonexistent-id/score")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

    assert response.status_code == 404
