# EcoOps AI

> **An AI-powered pre-deployment cloud sustainability advisor that can either analyze an existing Infrastructure as Code configuration or design and generate an optimized infrastructure configuration from workload requirements.**

EcoOps AI helps Cloud and DevOps engineers review infrastructure *before* deployment, through two workflows:

- **Workflow A — Analyze Existing Infrastructure** *(implemented through Phase 11)*: upload Terraform, Kubernetes, or Docker Compose plus a workload profile. EcoOps AI identifies likely overprovisioning, predicts resource utilization, estimates cost, energy use, and carbon impact, and proposes constraint-aware optimizations as a separate optimized copy of the original IaC for human review.
- **Workflow B — Create Sustainable Infrastructure** *(designed; Phases 14–17)*: describe only the application workload in a plain-language form (no IaC knowledge needed), optionally letting EcoOps AI choose the target by explicit rules. The system designs candidate infrastructures, evaluates each through the same ML/estimation/constraint pipeline, ranks them, and generates valid IaC for review and download.

Both workflows are advisory decision support. EcoOps AI never deploys infrastructure, runs uploaded IaC, applies changes, or silently changes a user's files.

This repository implements the first eleven phases of the planned final-year B.Tech CSE prototype: Kubernetes analysis, ML utilization prediction, transparent cost/energy/carbon estimation, a constraint engine, and a recommendation engine. The remaining roadmap — including the two-mode extension — is documented below.

## Why EcoOps AI?

Cloud environments are often provisioned with more CPU, memory, replicas, storage, or instance capacity than a workload requires. This can increase operating cost, energy use, and associated carbon emissions.

Most optimization happens after deployment, using monitoring data. EcoOps AI shifts that review earlier:

```text
Write IaC → Upload to EcoOps AI → Analyze before deployment
          → Review recommendations → Deploy manually
```

The system is deliberately an advisory tool. It never deploys infrastructure, runs uploaded IaC, applies changes, or silently changes a user's files.

## Planned capabilities

- Accept Terraform, Kubernetes manifests, and Docker Compose configurations.
- Collect an optional workload profile, including application type, expected users, traffic level, latency target, and availability target.
- Normalize source-specific infrastructure data into one common representation.
- Predict CPU and memory utilization using a trained machine-learning model.
- Estimate cost, energy consumption, and carbon impact.
- Generate explainable, constraint-aware recommendations.
- Produce a separate optimized configuration that users can compare, review, and download.
- Present current and recommended configurations in a dashboard.

## Core workflow

```text
IaC configuration + workload profile
                │
                ▼
      Validation and parsing
                │
                ▼
Normalized infrastructure representation
                │
                ▼
  Feature extraction and ML prediction
                │
                ▼
Cost / energy / carbon estimation
                │
                ▼
 Constraint-aware recommendation engine
                │
                ▼
  Explainable optimized configuration
                │
                ▼
       Engineer review and decision
```

## Supported IaC formats

| Format | Coverage | Status |
| --- | --- | --- |
| Kubernetes YAML | Deployments, resource requests/limits, replicas, and autoscaling-related details | Implemented |
| Terraform | AWS EC2 subset: `aws_instance` (instance type via an AWS metadata table, count, tags.Name, storage), `provider "aws"` region, ASG detection. Variable interpolation and other resource types are rejected with clear errors | Implemented (Phase 12) |
| Docker Compose | `services` (primary-service selection for multi-service files with a visible warning), `deploy.replicas`, v3 `deploy.resources` limits/reservations plus v2-style `cpus:`/`mem_limit:`, Docker memory-unit semantics. Detected structurally (top-level `services:`) — no dedicated extension needed | Implemented (Phase 13) |

Terraform and Docker Compose analyses support the full prediction/estimation/constraint/score pipeline; optimized-manifest *generation* is Kubernetes-only until the IaC generation phase and returns an explicit 400 for other sources.

## Recommendation principles

EcoOps AI does not simply minimize resource allocation or cost. It evaluates candidate configurations against stated workload and performance constraints, such as latency, availability, expected users, and traffic level.

Each recommendation is intended to include:

- Current and suggested values
- An explanation of the finding
- Predicted or estimated cost, energy, and carbon impact
- Constraint evaluation result

Example: a lower CPU allocation can be recommended only when the predicted utilization and configured performance constraints indicate that the candidate remains acceptable.

## Estimation and limitations

The project distinguishes clearly between predictions and estimates:

- **Predicted:** CPU and memory utilization, from a trained model.
- **Estimated:** energy use, carbon impact, and cloud cost, from documented models and configurable metadata.

EcoOps AI does not claim exact emissions, guaranteed savings, guaranteed performance, or universally optimal infrastructure. Results are decision-support estimates; the engineer remains responsible for reviewing and deploying any configuration.

## Proposed technology stack

| Area | Technologies |
| --- | --- |
| Frontend | React, Tailwind CSS, Chart.js or Recharts |
| Backend | Python, FastAPI |
| ML and data | pandas, NumPy, scikit-learn; optional XGBoost |
| Parsing | Python HCL parser and PyYAML |
| Database | PostgreSQL |
| Development and delivery | Git, GitHub, Docker, AWS (optional deployment) |

The initial utilization model is expected to use a simple, explainable regressor such as Random Forest. Google Cluster Workload Trace data is a proposed training source; it is not a normal user input.

## MVP scope

The minimum viable product is the following pipeline:

```text
Kubernetes YAML
  → validation and parsing
  → normalized features
  → utilization prediction
  → cost, energy, and carbon estimates
  → constraint checking
  → recommendations
  → dashboard
```

The first development milestone is intentionally smaller:

```text
Kubernetes YAML upload → validation → parser → normalized JSON API response
```

## Planned API

Implemented endpoints are marked below; the interactive FastAPI docs are also available at `/docs` when the server runs. The `GET /api/v1/analysis/{id}` aggregate endpoint is still a design target; analysis data is currently exposed via the per-resource endpoints.

| Method | Endpoint | Purpose | Status |
| --- | --- | --- | --- |
| `POST` | `/api/v1/validate` | Validate an uploaded Kubernetes YAML | Implemented |
| `POST` | `/api/v1/analyze` | Analyze IaC + workload: parse, predict utilization, estimate cost/energy/carbon, evaluate constraints | Implemented |
| `GET` | `/api/v1/analysis/{id}/configuration` | Retrieve stored normalized configuration | Implemented |
| `GET` | `/api/v1/analysis/{id}/features` | Retrieve stored workload profile and ML-ready features | Implemented |
| `GET` | `/api/v1/analysis/{id}/constraints` | Retrieve the constraint feasibility evaluation (recomputed from stored analysis) | Implemented |
| `POST` | `/api/v1/analysis/{id}/optimize` | Generate, evaluate, rank, and persist scale-down recommendations; returns baseline and optimized sustainability scores with improvement | Implemented |
| `GET` | `/api/v1/analysis/{id}/recommendations` | Retrieve the persisted recommendation set | Implemented |
| `GET` | `/api/v1/analysis/{id}/optimized-config` | Retrieve the optimized manifest, a diff against the original, and the change list (Kubernetes sources only; Terraform sources get an explicit 400) | Implemented |
| `GET` | `/api/v1/analysis/{id}/score` | Compute the weighted sustainability score with disclosed methodology and configurable weights | Implemented |
| `GET` | `/api/v1/analysis/{id}` | Retrieve an aggregate analysis result | Planned |

## Planned repository layout

```text
EcoOps-AI/
├── backend/                 # FastAPI application and services
├── frontend/                # React application
├── ml/                      # Training, evaluation, and saved-model workflow
├── parsers/                 # IaC parsing utilities
├── datasets/                # Dataset documentation and preprocessing inputs
├── infrastructure/          # Terraform, Kubernetes, and Docker examples
├── tests/                   # Unit and integration tests
├── docs/                    # Design and technical documentation
├── scripts/                 # Development utilities
├── README.md
└── docker-compose.yml
```

## Security boundaries

- Uploaded infrastructure files are parsed as data; they are never executed.
- EcoOps AI must never run `terraform apply`, `kubectl apply`, `docker compose up`, or any deployment command on user input.
- The application should validate file type and size, sanitize uploads, and avoid arbitrary shell execution.
- Cloud credentials, API keys, passwords, and other secrets must not be stored in the repository or analysis records.

## Development roadmap

Phases 1–11 are **done**. Revised roadmap (design doc §31):

1. Create the repository structure. (done)
2. Implement Kubernetes YAML validation and parsing. (done)
3. Define the normalized infrastructure schema. (done)
4. Prepare data and train an initial utilization model. (done)
5. Add prediction, estimation, constraint, and recommendation services. (done — phases 5–9)
6. Generate optimized YAML while preserving the original configuration. (done — phase 10)
7. Build the dashboard and integrate the API. (done — phase 11)
8. Add Terraform and Docker Compose parsers. (done — phases 12–13)
9. Workload-to-infrastructure generation: requirement engine, candidate generation/evaluation, IaC generation templates with target selection, and the Mode B API + dashboard entry points. (new phases 14–17)
10. Test, containerize, and optionally deploy. (phases 18–21, renumbered from 14–17)

## Contributing

Keep modules small and independently testable. In particular, parsers, ML code, API routes, estimation logic, and optimization logic should remain separate. Use configuration files or environment variables for settings, add tests for important logic, and never commit secrets, cloud credentials, full datasets, or generated artifacts unless they are intentionally versioned.

## Project status

**Phases 1–16 implemented:** Kubernetes parsing, normalized features, dataset preprocessing, utilization-model training (including a documented synthetic Kubernetes-scale demand component, see `ml/synthetic_augment.py`), prediction API, transparent cost/energy/carbon estimation, the constraint engine (five configurable feasibility checks), the recommendation engine (constraint-gated candidate ranking with persisted results via `POST /analysis/{id}/optimize`), optimized YAML generation (`GET /analysis/{id}/optimized-config` returns the optimized manifest, a unified diff against the preserved original, and the change list), the weighted sustainability score (`GET /analysis/{id}/score`, disclosed methodology and configurable weights per design doc §23), the React dashboard with a guided three-family demo section (Kubernetes / Terraform / Docker Compose), the **Terraform parser** (Phase 12: AWS EC2 subset with content-based `.tf` detection), and the **Docker Compose parser** (Phase 13: structural detection via top-level `services:`, v3 + v2 resource syntax, primary-service selection with visible warnings for multi-service files), and the **Workload Requirement Engine** (Phase 14, first Mode B module: `WorkloadProfile` v2 optional fields — RPS, traffic pattern incl. bursty, storage, autoscaling, priorities — plus a deterministic requirement estimator with documented sizing rules, discrete ladders, and replica minimums shared with the constraint engine's availability and user-capacity checks). **Phase 15** adds the **Candidate Infrastructure Generator + evaluation loop**: 4–6 deterministic candidate configurations per request (lean/balanced/headroom/elastic sizing variants, conditional economy-storage, and a Terraform-style VM baseline from the Phase 12 instance-type table), each evaluated through the existing prediction/estimation/constraint/score pipeline with priority-derived weights, hard constraint gating, deterministic ranking, and a full infeasible-path explanation). **Phase 16** completes Mode B's core: **"Let EcoOps AI choose" target selection** (explicit first-match-wins rules — batch→Compose, database→Terraform(+K8s), autoscaling/bursty→Kubernetes HPA, ML/AI→Kubernetes, huge-scale/high-availability→Terraform+Kubernetes, else Compose) and the **IaC Generation Engine**, which renders the winning candidate into deterministic Terraform / Kubernetes / Docker Compose / Terraform+Kubernetes artifacts, each MANDATORILY round-trip-validated through the same parser that handles user uploads before anything is returned. Mode B artifacts are prototypes for review — EcoOps AI never deploys anything. Optimized-file *analysis-output* generation stays Kubernetes-only with an explicit 400 for other sources (a Mode A limitation, unchanged).

**Design revision 2 (two operating modes):** the design document now specifies Mode B — workload-to-infrastructure generation (new Phases 14–17, after the Terraform/Docker Compose parsers in Phases 12–13; integration/testing/Docker/AWS renumbered 18–21). See [EcoOps-AI project design.md](<EcoOps-AI project design.md>) for the authoritative specification, especially §4, §6, §27, §31, §32, §40, §43, and §44.

## Frontend dashboard (Phase 11)

The React dashboard (Vite + Tailwind + Recharts, in `frontend/`) covers all design-doc §22 sections: sustainability score with grade and component breakdown, cost/energy/carbon estimates, predicted utilization chart, current configuration, problems detected (failed constraint checks), constraint-gated recommendations with savings and a before/after score comparison, and the optimized YAML with colored diff and download. A guided **demo section** opens a two-level picker — choose *Kubernetes demos* or *Terraform demos*, then a well/moderate/heavy scenario — which stages the bundled manifest and pre-fills its canonical (editable) workload; custom uploads work exactly as before.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to the backend)
```

Run the backend first (default `http://localhost:8000`, override with `BACKEND_PORT` or `VITE_API_URL`). The dev server must stay on port 5173 (or 3000) because those are the backend's CORS allow-listed origins.

## Run the whole stack with Docker

```bash
docker compose up -d --build
```

Starts Postgres, the FastAPI backend (port 8000), and the dashboard as a static nginx container (port 5173) that proxies `/api` to the backend — no CORS involved in this mode. Open http://localhost:5173. Trained model artifacts (`ml/models/`) must exist on the host before `up` (they are volume-mounted read-only; see the ML README to train them).

## License

No license has been selected yet. Add a license file before distributing or accepting external contributions.
