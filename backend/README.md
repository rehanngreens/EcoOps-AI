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

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API root: http://localhost:8000/
- Health check: http://localhost:8000/health
- OpenAPI docs: http://localhost:8000/docs

## Test

```bash
pytest
```
