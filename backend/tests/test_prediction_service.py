import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from sklearn.dummy import DummyRegressor

from app.schemas.unified_schema import FeatureVector
from app.services.prediction_service import (
    MODEL_FEATURE_COLUMNS,
    ModelArtifactsUnavailableError,
    ModelCompatibilityError,
    load_model_bundle,
    predict_utilization,
)


def _features() -> FeatureVector:
    return FeatureVector(
        application_type="rest-api",
        application_type_code=3,
        expected_users=1000,
        traffic_level="medium",
        traffic_score=2,
        max_latency_ms=200,
        availability_target=99.0,
        cpu=1.0,
        memory_gb=2.0,
        replicas=2,
        autoscaling_enabled=False,
        autoscaling_enabled_int=0,
        source_type="kubernetes",
        total_cpu_capacity=2.0,
        total_memory_capacity=4.0,
        users_per_replica=500.0,
    )


def _constant_model(value: float) -> DummyRegressor:
    features = np.zeros((2, len(MODEL_FEATURE_COLUMNS)))
    model = DummyRegressor(strategy="constant", constant=value)
    return model.fit(features, np.array([value, value]))


def _write_artifacts(directory: Path, feature_columns: list[str] | None = None) -> None:
    directory.mkdir()
    joblib.dump(_constant_model(0.25), directory / "cpu_utilization_model.joblib")
    joblib.dump(_constant_model(0.75), directory / "memory_utilization_model.joblib")
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "model_type": "RandomForestRegressor",
                "created_at": "2026-09-13T00:00:00+00:00",
                "feature_columns": feature_columns or list(MODEL_FEATURE_COLUMNS),
                "artifacts": {
                    "cpu_model": "cpu_utilization_model.joblib",
                    "memory_model": "memory_utilization_model.joblib",
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def clear_model_cache() -> None:
    load_model_bundle.cache_clear()
    yield
    load_model_bundle.cache_clear()


def test_predict_utilization_loads_models_and_preserves_feature_contract(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    _write_artifacts(model_dir)

    prediction = predict_utilization(_features(), model_dir)

    assert prediction.cpu_utilization == 0.25
    assert prediction.memory_utilization == 0.75
    assert prediction.model_type == "RandomForestRegressor"


def test_predict_utilization_reports_missing_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactsUnavailableError, match="python ml/train_model.py"):
        predict_utilization(_features(), tmp_path / "missing")


def test_predict_utilization_rejects_incompatible_feature_order(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    _write_artifacts(model_dir, feature_columns=list(reversed(MODEL_FEATURE_COLUMNS)))

    with pytest.raises(ModelCompatibilityError, match="feature order"):
        predict_utilization(_features(), model_dir)
