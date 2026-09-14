# EcoOps AI

> **An AI-powered cloud sustainability advisor for pre-deployment infrastructure optimization.**

EcoOps AI helps Cloud and DevOps engineers review Infrastructure as Code (IaC) *before* deployment. It analyzes infrastructure allocations alongside a workload profile to identify likely overprovisioning, predict resource utilization, estimate cost, energy use, and carbon impact, and propose constraint-aware optimizations for human review.

This repository implements the first nine phases of the planned final-year B.Tech CSE prototype: Kubernetes analysis, ML utilization prediction, transparent cost/energy/carbon estimation, a constraint engine, and a recommendation engine. The remaining roadmap is documented below.

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

| Format | Planned coverage | Priority |
| --- | --- | --- |
| Kubernetes YAML | Deployments, resource requests/limits, replicas, and autoscaling-related details | MVP |
| Terraform | Cloud provider, region, instance types/counts, storage, and autoscaling details | Extension |
| Docker Compose | Services, replicas, CPU, memory, and storage constraints | Extension |

Kubernetes is the first end-to-end implementation target. Terraform and Docker Compose support follow once the MVP is stable.

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
| `GET` | `/api/v1/analysis/{id}/optimized-config` | Retrieve the optimized manifest, a diff against the original, and the change list | Implemented |
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

1. Create the repository structure.
2. Implement Kubernetes YAML validation and parsing.
3. Define the normalized infrastructure schema.
4. Prepare data and train an initial utilization model.
5. Add prediction, estimation, constraint, and recommendation services. (done - phases 5-9)
6. Generate optimized YAML while preserving the original configuration. (done - phase 10)
7. Build the dashboard and integrate the API.
8. Add Terraform and Docker Compose parsers.
9. Test, containerize, and optionally deploy.

## Contributing

Keep modules small and independently testable. In particular, parsers, ML code, API routes, estimation logic, and optimization logic should remain separate. Use configuration files or environment variables for settings, add tests for important logic, and never commit secrets, cloud credentials, full datasets, or generated artifacts unless they are intentionally versioned.

## Project status

**Phases 1–10 implemented:** Kubernetes parsing, normalized features, dataset preprocessing, utilization-model training (including a documented synthetic Kubernetes-scale demand component, see `ml/synthetic_augment.py`), prediction API, transparent cost/energy/carbon estimation, the constraint engine (five configurable feasibility checks), the recommendation engine (constraint-gated candidate ranking with persisted results via `POST /analysis/{id}/optimize`), and optimized YAML generation (`GET /analysis/{id}/optimized-config` returns the optimized manifest, a unified diff against the preserved original, and the change list). The sustainability score (`GET /analysis/{id}/score`) is a weighted mean of five normalized components with fully disclosed methodology and configurable weights per design doc §23. Remaining: dashboard (Phase 11), and Terraform/Docker Compose parsers (Phases 12–13). See [EcoOps-AI project design.md](<EcoOps-AI project design.md>) for the roadmap.

## License

No license has been selected yet. Add a license file before distributing or accepting external contributions.
