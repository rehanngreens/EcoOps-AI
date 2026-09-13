"""Load Phase 5 artifacts and predict utilization from backend feature vectors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.config import get_settings
from app.schemas.unified_schema import FeatureVector, UtilizationPrediction

MODEL_FEATURE_COLUMNS = (
    "application_type_code",
    "expected_users",
    "traffic_score",
    "max_latency_ms",
    "availability_target",
    "cpu",
    "memory_gb",
    "replicas",
    "autoscaling_enabled_int",
    "total_cpu_capacity",
    "total_memory_capacity",
    "users_per_replica",
)


class ModelArtifactsUnavailableError(RuntimeError):
    """Raised when local model artifacts have not been generated."""


class ModelCompatibilityError(RuntimeError):
    """Raised when a saved model cannot accept the current feature contract."""


@dataclass(frozen=True)
class ModelBundle:
    cpu_model: Any
    memory_model: Any
    model_type: str
    model_created_at: str | None


def _artifact_path(directory: Path, metadata: dict[str, Any], key: str) -> Path:
    artifacts = metadata.get("artifacts")
    name = artifacts.get(key) if isinstance(artifacts, dict) else None
    if not isinstance(name, str) or Path(name).name != name:
        raise ModelCompatibilityError(f"Model metadata has an invalid {key} artifact name")
    return directory / name


@lru_cache
def load_model_bundle(model_dir: str) -> ModelBundle:
    """Load and validate artifacts once per configured model directory."""
    directory = Path(model_dir)
    metadata_path = directory / "metadata.json"
    if not metadata_path.is_file():
        raise ModelArtifactsUnavailableError(
            "Model artifacts are unavailable. Run: python ml/train_model.py"
        )

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelCompatibilityError("Model metadata is unreadable; retrain the models") from exc

    if metadata.get("feature_columns") != list(MODEL_FEATURE_COLUMNS):
        raise ModelCompatibilityError(
            "Model feature order is incompatible with the backend; retrain the models"
        )

    cpu_path = _artifact_path(directory, metadata, "cpu_model")
    memory_path = _artifact_path(directory, metadata, "memory_model")
    if not cpu_path.is_file() or not memory_path.is_file():
        raise ModelArtifactsUnavailableError(
            "Model artifacts are incomplete. Run: python ml/train_model.py"
        )

    try:
        return ModelBundle(
            cpu_model=joblib.load(cpu_path),
            memory_model=joblib.load(memory_path),
            model_type=str(metadata.get("model_type", "unknown")),
            model_created_at=metadata.get("created_at"),
        )
    except Exception as exc:  # Joblib can raise several serializer-specific errors.
        raise ModelCompatibilityError("Model artifacts could not be loaded; retrain the models") from exc


def _feature_row(features: FeatureVector) -> np.ndarray:
    values = np.asarray(
        [[float(getattr(features, column)) for column in MODEL_FEATURE_COLUMNS]], dtype=float
    )
    if not np.isfinite(values).all():
        raise ModelCompatibilityError("Features contain non-finite model values")
    return values


def _utilization(value: float) -> float:
    if not np.isfinite(value):
        raise ModelCompatibilityError("Model returned a non-finite prediction")
    return float(np.clip(value, 0, 1))


def predict_utilization(
    features: FeatureVector,
    model_dir: Path | None = None,
) -> UtilizationPrediction:
    """Return bounded CPU and memory utilization predictions for one feature vector."""
    directory = model_dir or get_settings().model_dir
    bundle = load_model_bundle(str(directory))
    row = _feature_row(features)
    cpu_prediction = _utilization(float(bundle.cpu_model.predict(row)[0]))
    memory_prediction = _utilization(float(bundle.memory_model.predict(row)[0]))
    return UtilizationPrediction(
        cpu_utilization=cpu_prediction,
        memory_utilization=memory_prediction,
        model_type=bundle.model_type,
        model_created_at=bundle.model_created_at,
    )
