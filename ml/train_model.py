"""Train and evaluate Phase 5 CPU and memory utilization models."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from config import (
    CPU_MODEL_FILENAME,
    DEFAULT_N_ESTIMATORS,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MIN_SAMPLES_LEAF,
    MEMORY_MODEL_FILENAME,
    MODEL_METADATA_FILENAME,
    MODELS_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
    TEST_FILENAME,
    TRAIN_FILENAME,
)
from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS


def load_dataset(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load one processed CSV and validate its Phase 4 model contract."""
    frame = pd.read_csv(path)
    columns = FEATURE_COLUMNS + TARGET_COLUMNS
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    if frame.empty:
        raise ValueError(f"{path} contains no rows")

    values = frame[columns].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError(f"{path} contains missing or non-finite model values")
    targets = values[TARGET_COLUMNS]
    if ((targets < 0) | (targets > 1)).any().any():
        raise ValueError(f"{path} has utilization targets outside the [0, 1] range")
    return values[FEATURE_COLUMNS], targets


def _model(n_estimators: int, random_state: int) -> RandomForestRegressor:
    if n_estimators < 1:
        raise ValueError("n_estimators must be at least 1")
    return RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        max_depth=DEFAULT_MAX_DEPTH,
        min_samples_leaf=DEFAULT_MIN_SAMPLES_LEAF,
        n_jobs=-1,
    )


def _metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(root_mean_squared_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
    }


def train_models(
    train_path: Path,
    test_path: Path,
    output_dir: Path,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any]:
    """Train separate Random Forest models and write artifacts plus metadata."""
    train_features, train_targets = load_dataset(train_path)
    test_features, test_targets = load_dataset(test_path)

    cpu_model = _model(n_estimators, random_state)
    memory_model = _model(n_estimators, random_state)
    cpu_model.fit(train_features.to_numpy(), train_targets["cpu_utilization"])
    memory_model.fit(train_features.to_numpy(), train_targets["memory_utilization"])
    cpu_predictions = cpu_model.predict(test_features.to_numpy())
    memory_predictions = memory_model.predict(test_features.to_numpy())
    cpu_baseline_predictions = np.full(len(test_features), train_targets["cpu_utilization"].mean())
    memory_baseline_predictions = np.full(
        len(test_features), train_targets["memory_utilization"].mean()
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(cpu_model, output_dir / CPU_MODEL_FILENAME)
    joblib.dump(memory_model, output_dir / MEMORY_MODEL_FILENAME)
    metadata: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_type": "RandomForestRegressor",
        "n_estimators": n_estimators,
        "random_state": random_state,
        "feature_columns": FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "train_path": str(train_path),
        "test_path": str(test_path),
        "training_rows": int(len(train_features)),
        "model_parameters": {
            "max_depth": DEFAULT_MAX_DEPTH,
            "min_samples_leaf": DEFAULT_MIN_SAMPLES_LEAF,
        },
        "test_rows": int(len(test_features)),
        "artifacts": {
            "cpu_model": CPU_MODEL_FILENAME,
            "memory_model": MEMORY_MODEL_FILENAME,
        },
        "metrics": {
            "cpu_utilization": _metrics(test_targets["cpu_utilization"], cpu_predictions),
            "memory_utilization": _metrics(
                test_targets["memory_utilization"], memory_predictions
            ),
        },
        "baseline_metrics": {
            "strategy": "training_target_mean",
            "cpu_utilization": _metrics(
                test_targets["cpu_utilization"], cpu_baseline_predictions
            ),
            "memory_utilization": _metrics(
                test_targets["memory_utilization"], memory_baseline_predictions
            ),
        },
        "limitations": [
            "Training data uses Google Cluster trace resource fractions, not Kubernetes cores or GiB.",
            "Several workload fields are defaults because they are absent from the trace.",
            "Predictions are prototype estimates, not automatic deployment decisions.",
        ],
    }
    (output_dir / MODEL_METADATA_FILENAME).write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train EcoOps utilization models")
    parser.add_argument("--train-path", type=Path, default=PROCESSED_DIR / TRAIN_FILENAME)
    parser.add_argument("--test-path", type=Path, default=PROCESSED_DIR / TEST_FILENAME)
    parser.add_argument("--output-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--n-estimators", type=int, default=DEFAULT_N_ESTIMATORS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(
        json.dumps(
            train_models(
                args.train_path, args.test_path, args.output_dir, args.n_estimators
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
