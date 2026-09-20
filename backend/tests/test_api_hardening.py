"""Phase 19 API hardening tests.

Adversarial inputs at the API boundary: empty/binary/comment-only uploads,
the upload-size ceiling, optimize idempotence, and target-name validation.
Everything runs through the public TestClient with the predictor mocked for
CI parity (no model artifacts).
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services import prediction_service
from tests.conftest import load_manifest

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
    monkeypatch.setattr(
        prediction_service,
        "predict_utilization",
        lambda _: UtilizationPrediction(
            cpu_utilization=0.25,
            memory_utilization=0.5,
            model_type="mock",
            model_created_at=None,
        ),
    )


def _upload(content: bytes | str, filename: str = "deployment.yaml"):
    return client.post(
        "/api/v1/analyze",
        files={
            "file": (filename, content, "application/x-yaml"),
            "workload": (None, json.dumps(WORKLOAD), "application/json"),
        },
    )


class TestDegenerateUploads:
    def test_empty_file_is_rejected_not_crash(self) -> None:
        response = _upload(b"")
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_binary_file_is_rejected_cleanly(self) -> None:
        # PNG magic bytes followed by junk — not valid UTF-8.
        payload = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
        response = _upload(payload)
        assert response.status_code in (400, 422)
        assert isinstance(response.json().get("detail"), (str, list))

    def test_comment_only_yaml_is_rejected_not_crash(self) -> None:
        response = _upload("# just a comment\n# another comment\n")
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_whitespace_only_file_is_rejected(self) -> None:
        response = _upload("   \n\n\t\n")
        assert response.status_code == 422

    def test_oversized_upload_returns_413(self) -> None:
        # The ceiling is 1 MiB (Settings.max_upload_size_bytes); exceed it
        # with a real payload so the route's own guard fires.
        big = "x" * (1_048_577)  # 1 MiB ceiling + 1 byte of valid padding text
        response = _upload(big)
        assert response.status_code == 413
        assert "maximum upload size" in response.json()["detail"]


class TestDoubleOptimizeIdempotence:
    def test_optimize_twice_yields_identical_recommendations(self) -> None:
        analyze = _upload(load_manifest("deployment-heavy-overprovisioned.yaml"))
        assert analyze.status_code == 201
        analysis_id = analyze.json()["analysis_id"]

        first = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
        assert first.status_code == 201
        second = client.post(f"/api/v1/analysis/{analysis_id}/optimize")
        assert second.status_code in (200, 201)

        first_set = first.json()["recommendation_set"]
        second_set = second.json()["recommendation_set"]
        assert first_set["status"] == second_set["status"]
        assert first_set["items"] == second_set["items"]
        # The stored set is ONE set, not a duplicate.
        stored = client.get(f"/api/v1/analysis/{analysis_id}/recommendations")
        assert stored.status_code == 200
        assert stored.json()["recommendation_set"]["items"] == first_set["items"]


class TestTargetNameValidation:
    @pytest.mark.parametrize("target", ["kubernetes", "terraform", "docker_compose", "terraform+kubernetes", "auto", None])
    def test_all_documented_targets_accepted(self, target: str | None) -> None:
        response = client.post(
            "/api/v1/generate", json={"workload": {**WORKLOAD, "average_rps": 200.0, "peak_rps": 500.0}, "target": target}
        )
        assert response.status_code == 201, response.text

    def test_unknown_target_400_names_valid_set(self) -> None:
        response = client.post(
            "/api/v1/generate",
            json={"workload": {**WORKLOAD, "average_rps": 200.0, "peak_rps": 500.0}, "target": "heroku"},
        )
        assert response.status_code == 400
        detail = str(response.json()["detail"])
        for expected in ("kubernetes", "terraform", "docker_compose", "auto"):
            assert expected in detail, f"valid target '{expected}' missing from error: {detail}"
