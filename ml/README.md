# ML pipeline

Offline pipeline that turns Google Cluster Workload Traces 2019 into train/test CSVs aligned with the Phase 3 `FeatureVector`.

The preprocessing phase does **not** change the API. Phase 5 adds local model
training; Phase 6 will connect the saved models to the backend API.

## Setup

```bash
cd ml
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You can also reuse `backend/.venv` and install `ml/requirements.txt` into it.

## Input files

Place shards under:

```text
datasets/google-cluster-2019/cell_a/
  instance_events-000000000000.json.gz
  instance_usage-000000000000.json.gz
```

These files are gitignored. Do not commit them.

## Run

From the `ml/` directory:

```bash
python preprocess.py --max-rows 50000
```

Read entire shards (slow, high memory):

```bash
python preprocess.py --all-rows
```

Output (also gitignored):

```text
datasets/processed/
  train.csv
  test.csv
  metadata.json
```

## Column contract

Inputs (`X`) match Phase 3 numeric features:

`application_type_code`, `expected_users`, `traffic_score`, `max_latency_ms`, `availability_target`, `cpu`, `memory_gb`, `replicas`, `autoscaling_enabled_int`, `total_cpu_capacity`, `total_memory_capacity`, `users_per_replica`

Targets (`y`):

`cpu_utilization`, `memory_utilization` in `[0, 1]`

## Mapping

| Training column | Source |
| --- | --- |
| `cpu`, `memory_gb` | `instance_events.resource_request` when IDs join; otherwise `instance_usage.maximum_usage` |
| `cpu_utilization` | average usage / allocated CPU |
| `replicas` | always `1` (no Kubernetes replica field in the trace) |
| `application_type_code` | proxy from `scheduling_class`, else `3` (rest-api) |
| `expected_users`, `traffic_score`, `max_latency_ms`, `availability_target` | documented defaults matching the backend workload schema |

Google resource values are **fractions of a machine**, not Kubernetes cores or GiB. They are still usable as relative allocation/usage signals for a prototype model.

The first events shard and first usage shard often **do not share instance IDs**. When that happens, preprocessing records `allocation_source = instance_usage.maximum_usage_fallback` in `metadata.json`.

## Tests

From the repository root:

```bash
pip install -r ml/requirements.txt
pytest -v ml/tests
```

Tests use tiny JSONL fixtures, not the 400MB shards.

## Phase 5: train utilization models

After preprocessing has produced `train.csv` and `test.csv`, run this command
from the repository root:

```bash
python ml/train_model.py
```

The script trains separate `RandomForestRegressor` models for CPU and memory
utilization, evaluates them against the untouched test split, and writes local
artifacts under `ml/models/`:

```text
cpu_utilization_model.joblib
memory_utilization_model.joblib
metadata.json
```

`metadata.json` records the exact feature order, row counts, evaluation metrics
(MAE, RMSE, and R²), and the model limitations. It also records a mean-target
baseline so model quality is compared against a simple no-feature prediction.
These generated artifacts are gitignored and must not be committed.

For a quick smoke test with fewer trees:

```bash
python ml/train_model.py --n-estimators 10
```
