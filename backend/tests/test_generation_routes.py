"""Tests for the Phase 17 Mode B generation API (design doc section 27/44.7).

The predictor is mocked (CI has no model artifacts); the assertions are
about the API contract: status codes, persistence, replay, the explicit
422 infeasible path, and the never-deploy safety property (artifacts are
text only).
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services import prediction_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_predictor(monkeypatch: pytest.MonkeyPatch):
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


def _workload(**overrides) -> dict:
    values: dict = {
        "application_type": "rest-api",
        "expected_users": 2000,
        "traffic_level": "medium",
        "max_latency_ms": 250,
        "availability_target": 99.9,
        "average_rps": 200.0,
        "peak_rps": 500.0,
    }
    values.update(overrides)
    return values


def _generate(workload: dict, target: str | None = None):
    return client.post(
        "/api/v1/generate",
        json={"workload": workload, "target": target},
    )


class TestGenerateEndpoint:
    def test_generate_returns_201_with_artifacts(self) -> None:
        response = _generate(_workload(), "kubernetes")
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "recommended"
        assert body["generation_id"]
        assert body["target_selection"]["target"] == "kubernetes"
        assert body["target_selection"]["source"] == "user"
        assert body["artifacts"][0]["filename"] == "deployment.yaml"
        assert body["artifacts"][0]["round_trip_valid"] is True
        assert body["requirements"]["cpu_cores"] > 0
        assert body["evaluation"]["selected_index"] == 0
        assert body["evaluation"]["disclaimer"]  # estimates labeled as such

    def test_auto_target_selects_by_rules(self) -> None:
        workload = _workload(application_type="batch", availability_target=99.0)
        response = _generate(workload, None)
        assert response.status_code == 201
        assert response.json()["target_selection"]["target"] == "docker_compose"
        assert "Rule 1" in response.json()["target_selection"]["explanation"]

    def test_combo_target_yields_two_artifacts(self) -> None:
        response = _generate(_workload(), "terraform+kubernetes")
        assert response.status_code == 201
        filenames = {a["filename"] for a in response.json()["artifacts"]}
        assert filenames == {"main.tf", "deployment.yaml"}

    def test_invalid_workload_rejected_422(self) -> None:
        response = _generate(_workload(average_rps=100.0, peak_rps=50.0))
        assert response.status_code == 422  # pydantic: peak < average

    def test_unknown_target_rejected(self) -> None:
        response = _generate(_workload(), "heroku")
        assert response.status_code in (400, 422)

    def test_infeasible_generation_is_explicit_422(self, monkeypatch) -> None:
        from app.schemas.constraint_schema import (
            ConstraintCheck,
            ConstraintEvaluation,
            ConstraintStatus,
        )
        from app.services.generation import evaluation_service

        def _always_fail(features, prediction):
            check = ConstraintCheck(
                name="cpu_headroom",
                status=ConstraintStatus.fail,
                required="predicted utilization <= 70%",
                actual="98.0%",
                explanation="Mocked failure for the infeasible API path.",
            )
            return ConstraintEvaluation(satisfied=False, checks=[check], disclaimer="mock")

        monkeypatch.setattr(
            evaluation_service.constraint_service,
            "evaluate_constraints",
            _always_fail,
        )
        response = _generate(_workload())
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "infeasible"
        assert "cpu_headroom" in detail["explanation"]
        assert detail["generation_id"]

    def test_artifacts_are_text_never_executed(self) -> None:
        response = _generate(_workload(), "kubernetes")
        artifact = response.json()["artifacts"][0]
        assert isinstance(artifact["content"], str)
        assert "never deploys" in artifact["content"]


class TestGenerationRetrieval:
    def test_round_trip_get_generation(self) -> None:
        created = _generate(_workload(), "kubernetes").json()
        fetched = client.get(f"/api/v1/generation/{created['generation_id']}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["generation_id"] == created["generation_id"]
        assert body["target_selection"] == created["target_selection"]
        assert body["artifacts"] == created["artifacts"]
        assert body["evaluation"]["requirements"] == created["evaluation"]["requirements"]

    def test_unknown_generation_404(self) -> None:
        response = client.get("/api/v1/generation/does-not-exist")
        assert response.status_code == 404

    def test_configuration_summary_endpoint(self) -> None:
        created = _generate(_workload(), "kubernetes").json()
        response = client.get(
            f"/api/v1/generation/{created['generation_id']}/configuration"
        )
        assert response.status_code == 200
        config = response.json()
        assert config["application"].endswith("-app")
        assert config["cpu_per_replica"] > 0
        assert config["memory_per_replica_gb"] > 0
        assert config["replicas"] >= 1
        assert config["source_type"] == "kubernetes"

    def test_optimize_reranks(self) -> None:
        created = _generate(_workload(), "kubernetes").json()
        response = client.post(f"/api/v1/generation/{created['generation_id']}/optimize")
        assert response.status_code == 200
        body = response.json()
        assert body["generation_id"] == created["generation_id"]
        assert body["candidates"]
        assert sum(body["weights_used"].values()) == pytest.approx(1.0)

    def test_optimize_unknown_generation_404(self) -> None:
        assert client.post("/api/v1/generation/nope/optimize").status_code == 404

    def test_generation_persisted_in_database(self) -> None:
        from app.core.database import SessionLocal
        from app.models.generation import GenerationRecord

        created = _generate(_workload(), "terraform").json()
        with SessionLocal() as session:
            record = session.get(GenerationRecord, created["generation_id"])
            assert record is not None
            assert record.status == "recommended"
            assert record.target == "terraform"
            assert record.workload["application_type"] == "rest-api"
            assert record.evaluation["candidates"]  # rejected candidates kept too
