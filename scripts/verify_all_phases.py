"""Verify all phases 1-18 are working, phase by phase (live API + direct engine calls).

Expects the backend to already be listening on BACKEND_URL (default
http://127.0.0.1:8000). Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent

FIXTURES = {
    "kubernetes": ROOT / "infrastructure/kubernetes/deployment-heavy-overprovisioned.yaml",
    "terraform": ROOT / "infrastructure/terraform/main-heavy-overprovisioned.tf",
    "docker_compose": ROOT / "infrastructure/docker/compose-heavy-overprovisioned.yaml",
}

results: list[tuple[str, bool, str]] = []


def record(phase: str, ok: bool, detail: str = "") -> None:
    results.append((phase, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {phase}{'  — ' + detail if detail else ''}")


def main(client: httpx.Client | None = None) -> int:
    client = client or httpx.Client(timeout=60)
    # Phase 6: process reachable (uvicorn app) — health endpoint.
    try:
        health = client.get(f"{BACKEND}/health")
        record("API up", health.status_code == 200, f"GET /health -> {health.status_code}")
    except Exception as exc:  # noqa: BLE001
        record("API up", False, str(exc))
        print("\nBackend is not reachable; start it first.")
        return 1

    for source_type, path in FIXTURES.items():
        label = {"kubernetes": "Kubernetes", "terraform": "Terraform", "docker_compose": "Docker Compose"}[source_type]

        # Phase 2/12/13: validation endpoint.
        try:
            with path.open("rb") as fh:
                validate = client.post(f"{BACKEND}/api/v1/validate", files={"file": (path.name, fh)})
            record(f"{label} validate", validate.status_code == 200, f"-> {validate.status_code}")
            record(f"{label} validation verdict", validate.json().get("valid") is True, f"valid={validate.json().get('valid')}")
        except Exception as exc:  # noqa: BLE001
            record(f"{label} validate", False, str(exc))
            continue

        # Phase 6: analyze = parse -> features -> predict -> estimate -> persist.
        try:
            with path.open("rb") as fh:
                workload = {
                    "application_type": "e-commerce",
                    "expected_users": 10000,
                    "traffic_level": "medium",
                    "max_latency_ms": 150,
                    "availability_target": 99.9,
                    # Phase 14 v2 fields ride along to prove the additive merge:
                    "average_rps": 500.0,
                    "peak_rps": 1500.0,
                    "traffic_pattern": "bursty",
                    "storage_gb": 100.0,
                    "autoscaling_required": True,
                    "performance_priority": "high",
                    "cost_priority": "medium",
                    "sustainability_priority": "high",
                }
                analyze = client.post(
                    f"{BACKEND}/api/v1/analyze",
                    files={
                        "file": (path.name, fh),
                        "workload": (None, json.dumps(workload), "application/json"),
                    },
                )
            ok = analyze.status_code == 201
            record(f"{label} analyze", ok, f"-> {analyze.status_code}")
            if not ok:
                print("      " + analyze.text[:300])
                continue
            data = analyze.json()
            analysis_id = data["analysis_id"]

            config = data.get("configuration", {})
            record(f"{label} parse + source_type (Phase 2/12/13)", config.get("source_type") == source_type, f"={config.get('source_type')} app={config.get('application')}")

            features = data.get("features", {})
            record(f"{label} feature extraction (Phase 3)", bool(features), f"cpu={features.get('cpu')} replicas={features.get('replicas')} users/replica={features.get('users_per_replica')}")

            prediction = data.get("prediction", {})
            pred_ok = "cpu_utilization" in prediction and "memory_utilization" in prediction and prediction.get("model_type") == "RandomForestRegressor"
            record(f"{label} ML prediction (Phase 5)", pred_ok, f"cpu_util={prediction.get('cpu_utilization')} mem_util={prediction.get('memory_utilization')}")

            estimation = data.get("estimation", {})
            est_ok = all(k in estimation for k in ("estimated_cost_usd", "estimated_energy_kwh", "estimated_carbon_kg_co2e")) and estimation.get("disclaimer")
            record(f"{label} cost/energy/carbon + disclaimer (Phase 7)", est_ok, f"cost=${estimation.get('estimated_cost_usd')} energy={estimation.get('estimated_energy_kwh')} kWh carbon={estimation.get('estimated_carbon_kg_co2e')} kg")

            # Phase 8: constraint engine (analyze embeds it; GET re-fetches).
            constraints = data.get("constraints", {})
            cget = client.get(f"{BACKEND}/api/v1/analysis/{analysis_id}/constraints")
            cget_ok = cget.status_code == 200 and cget.json().get("analysis_id") == analysis_id
            record(f"{label} constraint checks (Phase 8)", bool(constraints.get("checks")) and cget_ok, f"satisfied={constraints.get('satisfied')} GET -> {cget.status_code}")

            # Phase 9: recommendation engine — works for all sources.
            optimize = client.post(f"{BACKEND}/api/v1/analysis/{analysis_id}/optimize")
            rs = optimize.json().get("recommendation_set", {}) if optimize.status_code in (200, 201) else {}
            record(f"{label} optimize (Phase 9)", optimize.status_code in (200, 201) and bool(rs), f"-> {optimize.status_code}, status={rs.get('status')}")

            # Phase 10/18: optimized config now works for all three sources.
            optimized = client.get(f"{BACKEND}/api/v1/analysis/{analysis_id}/optimized-config")
            if source_type == "kubernetes":
                oc_ok = optimized.status_code == 200 and "diff" in optimized.json() and "optimized_yaml" in optimized.json()
                record(f"{label} optimized config + diff (Phase 10)", oc_ok, f"-> {optimized.status_code}, changes={len(optimized.json().get('changes', []))}")
            else:
                odata = optimized.json() if optimized.status_code == 200 else {}
                oc_ok = (
                    optimized.status_code == 200
                    and odata.get("optimized_yaml", "").startswith("# Generated by EcoOps AI")
                    and bool(odata.get("diff"))
                )
                record(f"{label} optimized config + diff (Phase 18)", oc_ok, f"-> {optimized.status_code}, notes={len(odata.get('notes', []))}, diff_lines={len(odata.get('diff', []))}")

            # Phase 11-adjacent: weighted sustainability score.
            score = client.get(f"{BACKEND}/api/v1/analysis/{analysis_id}/score")
            sdata = score.json().get("score", {}) if score.status_code == 200 else {}
            total = sdata.get("score")
            grade = sdata.get("grade")
            record(f"{label} sustainability score", score.status_code == 200 and total is not None and sdata.get("components"), f"score={total} grade={grade} components={len(sdata.get('components', []))}")

            # Phase 14: persisted workload echoes v2 fields additively.
            echo = data.get("workload", {})
            v2_ok = echo.get("average_rps") == 500.0 and echo.get("traffic_pattern") == "bursty" and echo.get("sustainability_priority") == "high"
            record(f"{label} WorkloadProfile v2 echoed (Phase 14)", v2_ok, f"average_rps={echo.get('average_rps')} pattern={echo.get('traffic_pattern')} sustain={echo.get('sustainability_priority')}")
        except Exception as exc:  # noqa: BLE001
            record(f"{label} analysis flow", False, str(exc))

    # Phase 14 engine, called directly (pure functions, no HTTP).
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.schemas.workload_schema import WorkloadProfile
        from app.services.generation.requirement_engine import (
            estimate_requirements,
            validate_workload_requirements,
        )

        w1 = WorkloadProfile(application_type="e-commerce", average_rps=500, peak_rps=1500, traffic_pattern="bursty")
        w2 = WorkloadProfile(application_type="e-commerce", average_rps=500, peak_rps=1500, traffic_pattern="bursty")
        r1, r2 = estimate_requirements(w1), estimate_requirements(w2)
        record("Phase 14 engine determinism", r1 == r2, f"cpu={r1.cpu_cores} mem={r1.memory_gb} replicas={r1.replica_estimate}")

        bursty_problems = validate_workload_requirements(WorkloadProfile(traffic_pattern="bursty"))
        record("Phase 14 bursty advisory", len(bursty_problems) == 1, bursty_problems[0][:80] if bursty_problems else "")

        v1 = WorkloadProfile(application_type="rest-api", expected_users=1000)
        r = estimate_requirements(v1)
        record("Phase 14 v1-only profile works", r.cpu_cores > 0 and len(r.notes) > 0, f"cpu={r.cpu_cores} replicas={r.replica_estimate}")
    except Exception as exc:  # noqa: BLE001
        record("Phase 14 engine direct", False, str(exc))

    # Phases 14-18: Mode B generation, end-to-end over ALL FOUR targets.
    try:
        gen_workload = {
            "application_type": "e-commerce",
            "expected_users": 10000,
            "traffic_level": "high",
            "max_latency_ms": 250,
            "availability_target": 99.95,
            "average_rps": 500.0,
            "peak_rps": 2500.0,
            "traffic_pattern": "bursty",
            "storage_gb": 100.0,
            "autoscaling_required": True,
            "performance_priority": "high",
            "cost_priority": "medium",
            "sustainability_priority": "medium",
        }
        for target, rule_hint in (
            ("auto", None),
            ("kubernetes", None),
            ("terraform+kubernetes", None),
            ("docker_compose", None),
        ):
            gen = client.post(
                f"{BACKEND}/api/v1/generate",
                json={"workload": gen_workload, "target": target},
            )
            ok = gen.status_code == 201
            record(f"Mode B generate target={target} (Phases 14-16)", ok, f"-> {gen.status_code}")
            if not ok:
                print("      " + gen.text[:300])
                continue
            gdata = gen.json()
            ts = gdata.get("target_selection", {})
            artifacts = gdata.get("artifacts", [])
            all_valid = bool(artifacts) and all(a.get("round_trip_valid") for a in artifacts)
            record(
                f"Mode B artifacts validated target={target} (Phase 16)",
                all_valid,
                f"target={ts.get('target')} source={ts.get('source')} files={[a.get('filename') for a in artifacts]}",
            )
            gid = gdata.get("generation_id")
            replay = client.get(f"{BACKEND}/api/v1/generation/{gid}")
            replay_ok = (
                replay.status_code == 200
                and replay.json().get("artifacts") == artifacts
                and replay.json().get("evaluation", {}).get("status") == "recommended"
            )
            record(f"Mode B replay identical target={target} (Phase 17)", replay_ok, f"-> {replay.status_code}")
            summary = client.get(f"{BACKEND}/api/v1/generation/{gid}/configuration")
            record(
                f"Mode B architecture summary target={target} (Phase 17)",
                summary.status_code == 200 and bool(summary.json()),
                f"-> {summary.status_code}",
            )
            reopt = client.post(f"{BACKEND}/api/v1/generation/{gid}/optimize", json={})
            reopt_ok = reopt.status_code in (200, 201) and reopt.json().get("weights_used")
            record(
                f"Mode B optimize re-rank target={target} (Phase 17)",
                reopt_ok,
                f"-> {reopt.status_code}, weights={len(reopt.json().get('weights_used', {}))}",
            )

        # Infeasible path: an extreme profile must be a explained 422.
        infeasible = client.post(
            f"{BACKEND}/api/v1/generate",
            json={
                "workload": {
                    "application_type": "streaming",
                    "expected_users": 10000000,
                    "traffic_level": "high",
                    "max_latency_ms": 10,
                    "availability_target": 99.99,
                    "average_rps": 900000.0,
                    "peak_rps": 5000000.0,
                    "traffic_pattern": "bursty",
                    "storage_gb": 5000.0,
                    "autoscaling_required": True,
                    "performance_priority": "high",
                }
            },
        )
        infeasible_ok = infeasible.status_code == 422 and infeasible.json().get("detail")
        record("Mode B infeasible -> explained 422 (Phase 17)", infeasible_ok, f"-> {infeasible.status_code}")

        # Unknown generation id -> 404; invalid target -> 400.
        missing = client.get(f"{BACKEND}/api/v1/generation/does-not-exist")
        record("Mode B unknown id -> 404 (Phase 17)", missing.status_code == 404, f"-> {missing.status_code}")
        bad_target = client.post(
            f"{BACKEND}/api/v1/generate",
            json={"workload": gen_workload, "target": "puppet"},
        )
        record("Mode B invalid target -> 400 (Phase 17)", bad_target.status_code == 400, f"-> {bad_target.status_code}")
    except Exception as exc:  # noqa: BLE001
        record("Mode B end-to-end (Phases 14-17)", False, str(exc))

    return summarize()


def summarize() -> int:
    """Print the pass/fail rollup and return the process exit code."""
    print()
    failed = [name for name, ok, _ in results if not ok]
    total = len(results)
    print(f"{'ALL CHECKS PASSED' if not failed else 'FAILURES'}: {total - len(failed)}/{total}")
    for name in failed:
        print(f"  FAILED: {name}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
