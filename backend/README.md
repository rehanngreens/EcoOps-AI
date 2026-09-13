# EcoOps AI Backend

FastAPI backend for pre-deployment infrastructure analysis.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional, for tests
cp .env.example .env
```

## Required model artifacts

Before submitting an analysis, train the local Phase 5 models from the
repository root:

```bash
source backend/.venv/bin/activate
python ml/train_model.py
```

The generated `ml/models/` artifacts are intentionally gitignored. If they are
missing or incompatible, `POST /api/v1/analyze` returns a clear `503` response.

## Run with Docker (recommended)

From the repository root:

```bash
docker compose up --build
```

This starts PostgreSQL and the API. Migrations run automatically on backend startup.
Docker Compose mounts the locally generated `ml/models/` directory read-only at `/models`.

- API: http://localhost:8000/
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

## Run locally (without Docker)

1. Start PostgreSQL and create the `ecoops` database (or adjust `DATABASE_URL` in `.env`).
2. Apply migrations:

```bash
cd backend
alembic upgrade head
```

3. Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/validate` | Validate an uploaded Kubernetes YAML file |
| `POST` | `/api/v1/analyze` | Parse YAML, return utilization predictions, and estimate cost, energy, and carbon |
| `GET` | `/api/v1/analysis/{id}/configuration` | Retrieve a stored configuration |
| `GET` | `/api/v1/analysis/{id}/features` | Retrieve stored workload and ML-ready features |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@../infrastructure/kubernetes/deployment-heavy-overprovisioned.yaml" \
  -F 'workload={"application_type":"e-commerce","expected_users":10000,"traffic_level":"medium","max_latency_ms":150,"availability_target":99.9}'
```

## Phase 7 estimation assumptions

`POST /api/v1/analyze` returns allocation-based cost and utilization-based
energy/carbon estimates. Its response includes every assumption used: period
hours, CPU/memory pricing, CPU/memory power, PUE, and carbon intensity.

The values are configurable through the `ESTIMATION_*`, `*_COST_*`,
`*_POWER_*`, `DATA_CENTER_PUE`, and `CARBON_INTENSITY_GCO2_PER_KWH` environment
variables. They are prototype assumptions—not measured energy, an exact cloud
bill, or exact real-world emissions.

## Database migrations

```bash
alembic upgrade head          # apply migrations
alembic revision -m "message" # create a new migration
```

## Test

Tests use an in-memory SQLite database automatically.

```bash
pytest
```
