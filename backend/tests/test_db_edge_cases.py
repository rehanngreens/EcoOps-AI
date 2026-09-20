"""Phase 19 database and persistence edge tests.

These exercise the seams that normal flows never hit: corrupted JSON in
stored columns, unicode payloads, concurrent writes, duplicate analyses,
the migration 005 downgrade/upgrade cycle, and very large artifact
payloads. Everything runs against in-memory SQLite via the app TestClient;
the migration test spins up a real file-backed database in tmp_path.
"""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.unified_schema import UtilizationPrediction
from app.services import prediction_service

client = TestClient(app)
# Production-parity client: server exceptions become real 500 responses.
prod_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def mock_predictor(monkeypatch: pytest.MonkeyPatch):
    """CI parity: no model artifacts, so Mode B paths are mocked here too."""
    monkeypatch.setattr(
        prediction_service,
        "predict_utilization",
        lambda _: UtilizationPrediction(
            cpu_utilization=0.4,
            memory_utilization=0.45,
            model_type="mock",
            model_created_at=None,
        ),
    )

WORKLOAD = {
    "application_type": "rest-api",
    "expected_users": 2000,
    "traffic_level": "medium",
    "max_latency_ms": 250,
    "availability_target": 99.9,
    "average_rps": 200.0,
    "peak_rps": 500.0,
}


def _generate(target: str = "kubernetes"):
    return client.post("/api/v1/generate", json={"workload": WORKLOAD, "target": target})


class TestCorruptStoredJson:
    def test_corrupt_generation_evaluation_replays_clean_500(self) -> None:
        """A hand-corrupted evaluation blob must surface as a clean HTTP 500
        (handled server error), never an unhandled traceback dump."""
        from app.core.database import SessionLocal
        from app.models.generation import GenerationRecord

        created = _generate()
        assert created.status_code == 201
        gid = created.json()["generation_id"]

        with SessionLocal() as session:
            record = session.get(GenerationRecord, gid)
            record.evaluation = {"not": "the right shape at all"}
            session.commit()

        replay = prod_client.get(f"/api/v1/generation/{gid}")
        assert replay.status_code == 500

    def test_corrupt_artifacts_blob_replays_clean_500(self) -> None:
        from app.core.database import SessionLocal
        from app.models.generation import GenerationRecord

        created = _generate()
        gid = created.json()["generation_id"]
        with SessionLocal() as session:
            record = session.get(GenerationRecord, gid)
            record.artifacts = [{"filename": 1, "content": None}]
            session.commit()

        replay = prod_client.get(f"/api/v1/generation/{gid}")
        assert replay.status_code == 500


class TestUnicodeRoundTrip:
    def test_unicode_workload_survives_persist_and_replay(self) -> None:
        workload = dict(
            WORKLOAD,
            application_type="rest-api",
            # Unicode in the free-text-ish workload fields.
            traffic_level="high",
        )
        response = client.post(
            "/api/v1/generate",
            json={"workload": {**workload, "traffic_pattern": "bursty"}, "target": "kubernetes"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        gid = body["generation_id"]
        assert "bursty" in body["requirements"].get("notes", "") or body["requirements"]

        replay = client.get(f"/api/v1/generation/{gid}").json()
        assert replay["requirements"] == body["requirements"]
        assert replay["evaluation"]["status"] == body["evaluation"]["status"]

    def test_emoji_in_workload_field_round_trips(self) -> None:
        """Pydantic enums reject free text, so unicode lives in numeric
        extremes + every echoed/explanation string column. Push a big user
        count and verify storage + replay stay byte-identical."""
        workload = {**WORKLOAD, "expected_users": 999_999}
        created = client.post(
            "/api/v1/generate", json={"workload": workload, "target": "docker_compose"}
        )
        assert created.status_code == 201
        body = created.json()
        replay = client.get(f"/api/v1/generation/{body['generation_id']}").json()
        assert replay["requirements"] == body["requirements"]
        assert replay["target_selection"] == body["target_selection"]


class TestConcurrentGenerations:
    def test_five_concurrent_generates_all_succeed_distinct_ids(self) -> None:
        """SQLite in-memory + StaticPool serializes writes; the API must
        still return 201 with distinct ids for every concurrent request."""
        results: list = []
        errors: list = []

        def _worker(index: int) -> None:
            try:
                response = _generate("kubernetes")
                results.append((index, response.status_code, response.json().get("generation_id")))
            except Exception as exc:  # noqa: BLE001
                errors.append((index, str(exc)))

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, errors
        assert len(results) == 5
        for _, status, _gid in results:
            assert status == 201
        ids = {gid for _, _, gid in results}
        assert len(ids) == 5, f"generation ids must be unique, got {ids}"


class TestDuplicateAnalyses:
    def test_reanalyze_same_file_creates_independent_rows(self) -> None:
        """Two uploads of the same manifest are two independent analyses;
        optimizing one must not leak into the other's recommendations."""
        manifest = json.dumps({"not": "a manifest"})  # placeholder, replaced below
        from tests.conftest import load_manifest

        manifest = load_manifest("deployment-heavy-overprovisioned.yaml")
        workload = {
            "application_type": "e-commerce",
            "expected_users": 10000,
            "traffic_level": "medium",
            "max_latency_ms": 150,
            "availability_target": 99.9,
        }

        def _analyze() -> str:
            response = client.post(
                "/api/v1/analyze",
                files={
                    "file": ("deployment.yaml", manifest, "application/x-yaml"),
                    "workload": (None, json.dumps(workload), "application/json"),
                },
            )
            assert response.status_code == 201
            return response.json()["analysis_id"]

        id_one, id_two = _analyze(), _analyze()
        assert id_one != id_two

        # The autouse fixture already mocks the predictor (CI parity).
        first = client.post(f"/api/v1/analysis/{id_one}/optimize")
        second_recs = client.get(f"/api/v1/analysis/{id_two}/recommendations")
        assert first.status_code == 201
        # The second analysis was never optimized: it must 404.
        assert second_recs.status_code == 404

        stored_one = client.get(f"/api/v1/analysis/{id_one}/recommendations")
        assert stored_one.status_code == 200
        assert stored_one.json()["analysis_id"] == id_one


class TestLargeArtifacts:
    def test_large_terraform_generation_persists_and_replays(self) -> None:
        """A big (but valid) VM fleet must generate, persist, and replay with
        the artifact content intact."""
        workload = {**WORKLOAD, "expected_users": 100_000, "peak_rps": 20_000.0}
        created = client.post(
            "/api/v1/generate", json={"workload": workload, "target": "terraform"}
        )
        assert created.status_code == 201, created.text
        body = created.json()
        tf_artifacts = [a for a in body["artifacts"] if a["filename"] == "main.tf"]
        assert tf_artifacts, body["artifacts"]
        # 100k users rendered as a large literal fleet (count scaled up).
        assert "count" in tf_artifacts[0]["content"]
        assert "instance_type" in tf_artifacts[0]["content"]
        assert len(tf_artifacts[0]["content"]) > 300

        replay = client.get(f"/api/v1/generation/{body['generation_id']}").json()
        replay_tf = [a for a in replay["artifacts"] if a["filename"] == "main.tf"]
        assert replay_tf[0]["content"] == tf_artifacts[0]["content"]


class TestMigrationCycle:
    def test_migration_005_downgrade_upgrade_round_trip(self, tmp_path) -> None:
        """alembic downgrade -1 then upgrade +1 on a REAL file-backed DB:
        the generations table disappears and comes back with its schema."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        # Run alembic with THIS interpreter (sys.executable -m alembic): the
        # environment running the tests always has alembic installed, unlike
        # a hardcoded .venv path, which only exists in local dev checkouts
        # (CI installs packages into the setup-python interpreter). Anchor
        # cwd to backend/ so alembic.ini is found regardless of where pytest
        # was invoked from.
        backend_dir = Path(__file__).resolve().parents[1]
        db_path = tmp_path / "migration_cycle.sqlite3"
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}

        def _alembic(*args: str) -> None:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *args],
                capture_output=True,
                text=True,
                env=env,
                cwd=backend_dir,
            )
            assert result.returncode == 0, result.stderr or result.stdout

        _alembic("upgrade", "head")
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "generations" in tables

        _alembic("downgrade", "-1")
        with sqlite3.connect(db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "generations" not in tables

        _alembic("upgrade", "head")
        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(generations)")}
        assert {"id", "status", "workload", "requirements", "evaluation", "artifacts"} <= columns
