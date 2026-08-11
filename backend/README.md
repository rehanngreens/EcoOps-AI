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

## Run with Docker (recommended)

From the repository root:

```bash
docker compose up --build
```

This starts PostgreSQL and the API. Migrations run automatically on backend startup.

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
| `POST` | `/api/v1/analyze` | Parse YAML, accept optional workload JSON, store and return features |
| `GET` | `/api/v1/analysis/{id}/configuration` | Retrieve a stored configuration |
| `GET` | `/api/v1/analysis/{id}/features` | Retrieve stored workload and ML-ready features |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@../infrastructure/kubernetes/deployment-heavy-overprovisioned.yaml" \
  -F 'workload={"application_type":"e-commerce","expected_users":10000,"traffic_level":"medium","max_latency_ms":150,"availability_target":99.9}'
```

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
