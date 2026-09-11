# ML preprocessing

Offline pipeline that turns Google Cluster Workload Traces 2019 into train/test CSVs aligned with the Phase 3 `FeatureVector`.

This phase does **not** train a model and does **not** change the API.

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

## Next phase

Phase 5 trains a Random Forest on `datasets/processed/train.csv` and saves a model under `ml/models/`.
