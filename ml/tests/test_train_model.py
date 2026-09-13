import json
from pathlib import Path

import joblib
import pandas as pd
import pytest

from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS
from train_model import load_dataset, train_models


def _dataset(row_count: int) -> pd.DataFrame:
    rows = []
    for index in range(row_count):
        cpu = 0.25 + index * 0.05
        memory = 0.5 + index * 0.1
        rows.append(
            {
                "application_type_code": 3,
                "expected_users": 1000 + index * 50,
                "traffic_score": 2,
                "max_latency_ms": 200,
                "availability_target": 99.0,
                "cpu": cpu,
                "memory_gb": memory,
                "replicas": 1,
                "autoscaling_enabled_int": 0,
                "total_cpu_capacity": cpu,
                "total_memory_capacity": memory,
                "users_per_replica": 1000 + index * 50,
                "cpu_utilization": 0.2 + index * 0.03,
                "memory_utilization": 0.3 + index * 0.02,
            }
        )
    return pd.DataFrame(rows)


def test_load_dataset_rejects_missing_required_column(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.csv"
    _dataset(12).drop(columns=["cpu"]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(path)


def test_train_models_saves_artifacts_and_metadata(tmp_path: Path) -> None:
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    output_dir = tmp_path / "models"
    _dataset(16).to_csv(train_path, index=False)
    _dataset(8).to_csv(test_path, index=False)

    metadata = train_models(train_path, test_path, output_dir, n_estimators=5)

    assert metadata["feature_columns"] == FEATURE_COLUMNS
    assert metadata["target_columns"] == TARGET_COLUMNS
    assert metadata["training_rows"] == 16
    assert metadata["test_rows"] == 8
    assert set(metadata["metrics"]) == set(TARGET_COLUMNS)
    assert metadata["baseline_metrics"]["strategy"] == "training_target_mean"
    assert set(metadata["baseline_metrics"]) == {"strategy", *TARGET_COLUMNS}

    saved_metadata = json.loads((output_dir / "metadata.json").read_text())
    assert saved_metadata["random_state"] == 42
    cpu_model = joblib.load(output_dir / "cpu_utilization_model.joblib")
    assert len(cpu_model.predict(_dataset(2)[FEATURE_COLUMNS])) == 2
