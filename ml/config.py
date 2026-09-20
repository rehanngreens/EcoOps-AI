from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_TRACE_DIR = PROJECT_ROOT / "datasets" / "google-cluster-2019" / "cell_a"
EVENTS_FILENAME = "instance_events-000000000000.json.gz"
USAGE_FILENAME = "instance_usage-000000000000.json.gz"

PROCESSED_DIR = PROJECT_ROOT / "datasets" / "processed"
TRAIN_FILENAME = "train.csv"
TEST_FILENAME = "test.csv"
METADATA_FILENAME = "metadata.json"

MODELS_DIR = PROJECT_ROOT / "ml" / "models"
CPU_MODEL_FILENAME = "cpu_utilization_model.joblib"
MEMORY_MODEL_FILENAME = "memory_utilization_model.joblib"
MODEL_METADATA_FILENAME = "metadata.json"

DEFAULT_MAX_ROWS = 50_000
TEST_SIZE = 0.2
RANDOM_STATE = 42
DEFAULT_N_ESTIMATORS = 100
DEFAULT_MAX_DEPTH = 16
DEFAULT_MIN_SAMPLES_LEAF = 10

# Documented synthetic Kubernetes-scale demand rows (design doc section 14).
# Combined with real trace rows; see ml/synthetic_augment.py.
SYNTHETIC_ROW_COUNT = 20_000

# Workload fields are not present in the Google trace. Defaults match
# backend/app/schemas/workload_schema.py so runtime FeatureVector columns align.
DEFAULT_APPLICATION_TYPE_CODE = 3  # rest-api
DEFAULT_EXPECTED_USERS = 1000
DEFAULT_TRAFFIC_SCORE = 2  # medium
DEFAULT_MAX_LATENCY_MS = 200
DEFAULT_AVAILABILITY_TARGET = 99.0
DEFAULT_REPLICAS = 1
DEFAULT_AUTOSCALING_ENABLED_INT = 0
