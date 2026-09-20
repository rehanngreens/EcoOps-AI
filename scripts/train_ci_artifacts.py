"""Generate REAL-but-synthetic model artifacts for CI and local CI rehearsal.

The production training pipeline (ml/preprocess.py -> ml/train_model.py)
needs the manually downloaded Google cluster trace. CI runners and local
CI rehearsals have no trace, so this script writes a deterministic
synthetic dataset with the exact Phase 4 model contract (feature_mapping
columns) and trains the real RandomForest models from ml/train_model.py
with a small forest for speed.

The resulting artifacts are intentionally NOT the production model: they
make the live API smoke (boot backend -> run verify_all_phases.py) run
end-to-end without any manual downloads. `train_models` writes the same
filenames and metadata shape the prediction service expects.

Usage: python scripts/train_ci_artifacts.py [--output-dir ml/models]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import pandas as pd  # noqa: E402

from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS  # noqa: E402
from train_model import train_models  # noqa: E402

APP_CODES = {  # mirrors feature_service.APPLICATION_TYPE_CODES
    "rest-api": 3,
    "e-commerce": 2,
    "streaming": 1,
    "batch": 0,
}
TRAFFIC_SCORES = {"low": 1, "medium": 2, "high": 3}


def synthetic_frame(rows: int) -> pd.DataFrame:
    """Deterministic rows spanning the realistic feature space.

    Utilization responds to allocation the way the real trace-trained model
    does (smaller per-replica CPU -> higher predicted utilization), so the
    smoke exercises constraint gating and ranking realistically.
    """
    records: list[dict] = []
    traffic_names = list(TRAFFIC_SCORES)
    for index in range(rows):
        app = list(APP_CODES)[index % len(APP_CODES)]
        traffic_name = traffic_names[index % len(traffic_names)]
        traffic = TRAFFIC_SCORES[traffic_name]
        cpu = [0.25, 0.5, 1.0, 2.0, 4.0][index % 5]
        memory = [0.5, 1.0, 2.0, 4.0, 8.0][index % 5]
        replicas = [1, 2, 3, 4, 8][index % 5]
        users = 500 + (index % 20) * 500
        cpu_util = min(0.95, max(0.05, 0.30 / cpu + 0.05 * (traffic - 2)))
        mem_util = min(0.95, max(0.10, 0.5 - 0.05 * (memory / 2 - 1)))
        records.append(
            {
                "application_type_code": APP_CODES[app],
                "expected_users": users,
                "traffic_score": traffic,
                "max_latency_ms": 100 + (index % 4) * 50,
                "availability_target": [99.0, 99.5, 99.9, 99.95][index % 4],
                "cpu": cpu,
                "memory_gb": memory,
                "replicas": replicas,
                "autoscaling_enabled_int": index % 2,
                "total_cpu_capacity": cpu * replicas,
                "total_memory_capacity": memory * replicas,
                "users_per_replica": users / replicas,
                "cpu_utilization": round(cpu_util, 4),
                "memory_utilization": round(mem_util, 4),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ml" / "models")
    parser.add_argument("--rows", type=int, default=240)
    parser.add_argument("--n-estimators", type=int, default=20)
    args = parser.parse_args()

    frame = synthetic_frame(args.rows)
    train_path = args.output_dir / "_ci_train.csv"
    test_path = args.output_dir / "_ci_test.csv"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.head(int(args.rows * 0.75)).to_csv(train_path, index=False)
    frame.tail(max(8, int(args.rows * 0.25))).to_csv(test_path, index=False)

    metadata = train_models(train_path, test_path, args.output_dir, n_estimators=args.n_estimators)
    train_path.unlink()
    test_path.unlink()
    print(
        f"CI artifacts written to {args.output_dir} "
        f"(rows={metadata['training_rows']}, n_estimators={args.n_estimators})"
    )


if __name__ == "__main__":
    main()
