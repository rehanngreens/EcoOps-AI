# EcoOps AI

## Design Document Changelog (Two-Operating-Mode Revision)

Revision 2 of this document adds a second operating mode without invalidating any completed work.

**STATUS: Phases 1–11 of the implementation roadmap (Section 31) are COMPLETE and verified.** The following sections are affected by this revision: 2, 3, 4, 5, 6, 7, 8, 18, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 38, 40, 43, and new Section 44. All other sections are unchanged and remain fully in force.

**NEW REQUIREMENT (Revision 2):** EcoOps AI must support TWO operating modes:

- **MODE A — Existing IaC Analysis** (already implemented through Phase 11): user provides Terraform / Kubernetes / Docker Compose plus workload characteristics; the system analyzes, predicts, estimates, checks constraints, recommends, and generates an optimized copy of the original IaC. The original IaC is NEVER silently overwritten.
- **MODE B — Workload-to-Infrastructure Generation** (new, Phases 14–17): user provides only workload requirements through a frontend form (no IaC knowledge needed); the system normalizes requirements, estimates resource requirements, generates and evaluates candidate infrastructures through the SAME ML / estimation / constraint pipeline used by Mode A, ranks candidates, and generates valid IaC (Terraform, Kubernetes, Docker Compose, Terraform+Kubernetes, or a rule-based "Let EcoOps AI choose" target) for user review. Nothing is ever deployed automatically.

**Revised roadmap mapping:** Phases 1–13 keep their numbers and intent (12: Terraform parser, 13: Docker Compose parser — both still pending). NEW Phases 14–17 deliver Mode B. Old Phases 14–17 (integration, testing, Dockerization, AWS deployment) are renumbered to 18–21 with unchanged content. No completed phase is renumbered or rewritten.

**Implementation philosophy for Mode B:** deterministic templates and rules, reuse of every existing module, no LLM code generation, no new microservices, no autonomous agents. Details in Section 44.

## Project Type

EcoOps AI is a final-year B.Tech Computer Science Engineering main project.

Project title:

"ECOOPS AI: AN AI-POWERED CLOUD SUSTAINABILITY ADVISOR FOR INFRASTRUCTURE OPTIMIZATION"

The project combines:

- Artificial Intelligence / Machine Learning
- Cloud Computing
- Infrastructure as Code (IaC)
- Kubernetes
- Docker
- Terraform
- Data Engineering
- Sustainable / Green Computing
- Cloud resource optimization

The project is an APPLICATION / PROTOTYPE.

It is NOT intended to be a production-grade cloud management platform.

It must be technically impressive but achievable within a final-year B.Tech project timeline.

--------------------------------------------------
# 1. CORE PROBLEM
--------------------------------------------------

Cloud infrastructure is frequently overprovisioned.

Developers may allocate:

- excessive CPU
- excessive memory
- unnecessary replicas
- excessive storage
- inefficient instance types
- poorly configured autoscaling

This can result in:

- resource wastage
- unnecessary cloud cost
- higher energy consumption
- increased carbon emissions
- inefficient infrastructure

Existing cloud optimization approaches often focus on cost, performance, runtime monitoring, scheduling, or post-deployment optimization.

EcoOps AI focuses on PRE-DEPLOYMENT ANALYSIS.

The core idea:

Instead of:

    Write infrastructure
        ↓
    Deploy
        ↓
    Monitor
        ↓
    Discover inefficiency

EcoOps AI does:

    Write infrastructure
        ↓
    Upload to EcoOps AI
        ↓
    Analyze before deployment
        ↓
    Predict utilization / sustainability impact
        ↓
    Check performance constraints
        ↓
    Generate recommendations
        ↓
    Generate optimized configuration
        ↓
    Engineer reviews
        ↓
    Engineer decides whether to deploy

EcoOps AI DOES NOT automatically deploy infrastructure.

EcoOps AI DOES NOT automatically modify production infrastructure.

It is a decision-support / advisory system.

--------------------------------------------------
# 2. PRIMARY PROJECT OBJECTIVE
--------------------------------------------------

The main objective is:

"Analyze Infrastructure as Code configurations before cloud deployment, identify inefficient or overprovisioned resources, estimate resource utilization, energy consumption and carbon impact, and provide explainable recommendations that balance sustainability, cost and performance."

The system should also generate an optimized infrastructure configuration for engineer review.

UPDATED (Revision 2) — the objective now has two equally first-class paths:

1. **Analyze an existing IaC configuration** (Mode A) — the original objective above, already implemented.
2. **Design and generate an optimized infrastructure configuration from workload requirements** (Mode B) — same analysis and optimization machinery, applied to candidate infrastructures the system itself proposes, producing generated IaC for engineer review.

Both paths are decision support. Neither deploys anything.

--------------------------------------------------
# 3. PRIMARY USER
--------------------------------------------------

Primary user:

Cloud / DevOps engineer.

The user has an application and wants to deploy it to cloud infrastructure.

The user provides:

1. Infrastructure configuration
2. Workload characteristics / requirements

EcoOps AI analyzes both.

UPDATED (Revision 2) — two user types, corresponding to the two operating modes:

- **Mode A user:** an engineer who ALREADY HAS an infrastructure configuration (Terraform, Kubernetes, or Docker Compose) and wants it reviewed and optimized before deployment. This user understands IaC.
- **Mode B user:** an engineer (or developer, or student) who understands their APPLICATION and its cloud requirements but does NOT necessarily know Kubernetes or Terraform syntax. This user describes the workload through a form and selects a generation target; EcoOps AI designs candidate infrastructures, evaluates them, and generates the IaC for review.

The Mode B experience must never require the user to read or write IaC syntax. IaC is an OUTPUT for this user, not an input.

--------------------------------------------------
# 4. USER INPUT
--------------------------------------------------

UPDATED (Revision 2) — user input depends on the operating mode.

## Mode A input — Existing IaC analysis (implemented)

The main user input is Infrastructure as Code.

Supported formats:

1. Terraform (.tf)
2. Kubernetes YAML manifests (.yaml / .yml)
3. Docker Compose (.yaml / .yml)

The user uploads the IaC file AND provides a workload profile (Section 5). This is the implemented, verified flow.

## Mode B input — Workload-only generation (new)

The user does NOT provide an IaC file. The user describes the application workload through a simple frontend form:

- Application type:
  - Web application
  - E-commerce
  - REST API
  - Database
  - Machine learning
  - AI inference
  - Streaming
  - Batch processing
  - Microservices
- Expected users: predefined ranges (100 / 1,000 / 10,000 / 100,000) plus a custom value
- Average traffic / requests per second (custom value)
- Peak traffic / requests per second (custom value)
- Traffic pattern:
  - Low
  - Medium
  - High
  - Variable
  - Bursty
- Maximum acceptable latency (ms)
- Availability requirement (%)
- Storage requirement (GB)
- Autoscaling requirement (yes / no)
- Performance priority (low / medium / high)
- Cost priority (low / medium / high)
- Sustainability priority (low / medium / high)

The user also selects the **IaC generation target**:

- Terraform
- Kubernetes
- Docker Compose
- Terraform + Kubernetes
- Let EcoOps AI choose

If "Let EcoOps AI choose" is selected, the target is chosen by EXPLICIT, DOCUMENTED RULES based on the workload requirements and deployment requirements (see Section 44.4). Do NOT make arbitrary claims that an LLM magically knows the universally best technology — there is no LLM in this decision path.

Mode B users never see IaC syntax on the input side. IaC appears only as generated output they can preview, review, and download.

Examples:

Terraform:

resource "aws_instance" "web" {
    instance_type = "t3.large"
}

Kubernetes:

apiVersion: apps/v1
kind: Deployment

metadata:
  name: backend

spec:
  replicas: 5

  template:
    spec:
      containers:
        - name: backend
          image: backend:v1
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"

Docker Compose:

services:
  backend:
    image: backend:v1
    deploy:
      replicas: 3
    cpus: 2
    mem_limit: 4g

--------------------------------------------------
# 5. WORKLOAD PROFILE INPUT
--------------------------------------------------

Infrastructure alone is not sufficient to determine the correct resource requirement.

Therefore EcoOps AI should optionally collect workload characteristics.

UPDATED (Revision 2) — the workload profile is shared by both modes. It is defined in TWO VERSIONS:

- **WorkloadProfile v1 (implemented, Phase 3):** application type, expected users, traffic level, maximum acceptable latency, availability target. Mode A uses v1 and is unaffected by this revision.
- **WorkloadProfile v2 (new, Phase 14):** extends v1 with the Mode B fields from Section 4 — average RPS, peak RPS, traffic pattern (adds "bursty"), storage requirement, autoscaling requirement, performance priority, cost priority, sustainability priority. All v2 fields are OPTIONAL with documented defaults, so existing Mode A requests and the v1-based ML feature pipeline continue to work unchanged.

Both modes produce the SAME WorkloadProfile object, which feeds the SAME feature extraction and ML prediction pipeline. Mode B simply always supplies v2 values (its form requires them); Mode A may supply v1 only.

Example:

Application type:
- Web application
- E-commerce
- REST API
- Database
- Machine learning
- AI inference
- Streaming
- Batch processing
- Microservices

Expected users:
- 100
- 1,000
- 10,000
- 100,000
- custom

Traffic level:
- Low
- Medium
- High
- Variable
- Bursty (NEW in v2)

Performance requirements:

Maximum acceptable latency:
e.g. 150 ms

Availability requirement:
e.g. 99.9%

These values become part of the feature set and are used to make recommendations more context-aware.

NEW (v2): average RPS, peak RPS, storage requirement, autoscaling requirement, and the three priorities (performance / cost / sustainability) become inputs to the Mode B requirement engine and candidate-ranking objective (Section 44). The three priorities set the WEIGHTS used to rank candidate configurations; they never override hard constraint checks.

IMPORTANT:

Do not make recommendations based only on arbitrary CPU or memory thresholds.

Recommendations should consider:

- current infrastructure allocation
- predicted utilization
- workload characteristics
- performance constraints
- availability requirements
- cost
- energy
- carbon impact

--------------------------------------------------
# 6. HIGH LEVEL SYSTEM WORKFLOW
--------------------------------------------------

UPDATED (Revision 2) — the system exposes TWO workflows, one per operating mode. Both reuse the same central pipeline (parsing where applicable, normalization, feature extraction, ML prediction, estimation, constraint engine).

## Workflow A — Existing IaC (implemented)

Complete workflow:

USER
  |
  | Upload Terraform / Kubernetes / Docker Compose
  | + workload profile
  v
FRONTEND
  |
  v
BACKEND API
  |
  v
FILE VALIDATION
  |
  v
CONFIGURATION PARSER
  |
  +---- Terraform Parser
  |
  +---- Kubernetes Parser
  |
  +---- Docker Compose Parser
  |
  v
NORMALIZED INFRASTRUCTURE REPRESENTATION
  |
  v
FEATURE EXTRACTION
  |
  v
WORKLOAD + INFRASTRUCTURE FEATURES
  |
  v
ML PREDICTION ENGINE
  |
  +---- CPU utilization prediction
  |
  +---- Memory utilization prediction
  |
  v
ENERGY ESTIMATION
  |
  v
CARBON ESTIMATION
  |
  v
COST ESTIMATION
  |
  v
CONSTRAINT ENGINE
  |
  v
RECOMMENDATION ENGINE
  |
  v
CANDIDATE CONFIGURATIONS
  |
  v
EVALUATE CANDIDATES
  |
  +---- Performance
  +---- Cost
  +---- Energy
  +---- Carbon
  +---- Resource utilization
  |
  v
BEST ACCEPTABLE RECOMMENDATION
  |
  v
EXPLAINABILITY MODULE
  |
  v
OPTIMIZED CONFIGURATION GENERATOR
  |
  v
DASHBOARD
  |
  +---- Current configuration
  +---- Predictions
  +---- Cost
  +---- Energy
  +---- Carbon
  +---- Issues
  +---- Recommendations
  +---- Expected improvements
  +---- Optimized configuration
  +---- Explanation

## Workflow B — Workload Only (new, Phases 14–17)

USER
  |
  | Describe workload requirements in a form
  | + select IaC generation target
  v
FRONTEND (no IaC syntax shown to the user)
  |
  v
BACKEND API  (POST /api/v1/generate)
  |
  v
WORKLOAD REQUIREMENT ENGINE (normalize + validate requirements)
  |
  v
RESOURCE REQUIREMENT ESTIMATION (deterministic rules, Section 44)
  |
  v
TARGET SELECTION (only if "Let EcoOps AI choose"; explicit rules, Section 44.4)
  |
  v
CANDIDATE INFRASTRUCTURE GENERATOR (sizing + replica + autoscaling variants)
  |
  v
FOR EACH CANDIDATE — the SAME pipeline as Workflow A:
  |
  +---- Normalized infrastructure representation
  +---- FEATURE EXTRACTION
  +---- ML PREDICTION ENGINE (CPU / memory utilization)
  +---- ENERGY ESTIMATION
  +---- CARBON ESTIMATION
  +---- COST ESTIMATION
  +---- CONSTRAINT ENGINE (reject violating candidates)
  +---- SUSTAINABILITY SCORE (per candidate)
  |
  v
CANDIDATE RANKING (weighted objective from user priorities)
  |
  v
BEST ACCEPTABLE INFRASTRUCTURE
  |
  v
EXPLAINABILITY MODULE (why this configuration)
  |
  v
IaC GENERATION ENGINE (deterministic templates → Terraform / K8s / Compose)
  |
  v
VALIDATION (generated IaC must round-trip through the same parsers as Workflow A)
  |
  v
IMPACT SUMMARY (cost / energy / carbon / score of the selected candidate)
  |
  v
USER REVIEW (preview → download; nothing is deployed)

Rule: Workflow B must NOT minimize any single dimension. Candidate ranking balances performance, availability, resource utilization, cost, energy, carbon, and the stated workload requirements, under hard constraint checks (Section 18).

--------------------------------------------------
# 7. CORE ARCHITECTURE
--------------------------------------------------

The system should contain these major modules:

1. Frontend
2. Backend API
3. Configuration Parser
4. Feature Extraction Engine
5. ML Prediction Engine
6. Sustainability Estimation Engine
7. Constraint Engine
8. Recommendation Engine
9. Optimized Configuration Generator
10. Database
11. Testing
12. Optional cloud deployment

UPDATED (Revision 2) — Mode B adds the MINIMUM set of new modules; everything else above is REUSED unchanged by both workflows:

1. Workload Requirement Engine (new) — normalizes and validates workload requirements, computes resource requirements
2. Candidate Infrastructure Generator (new) — produces a small set of candidate normalized configurations
3. IaC Generation Engine (new) — deterministic templates that emit Terraform / Kubernetes / Docker Compose
4. Target Selection logic (new, small) — explicit rules for "Let EcoOps AI choose"

Modules 1–4 are backend services in the existing FastAPI app. They call the EXISTING feature extraction, ML prediction, estimation, constraint, and scoring services for every candidate. Do NOT create a separate optimization system, a separate API service, or a separate database for Mode B. See Section 44 for the design of these modules.

--------------------------------------------------
# 8. CONFIGURATION PARSER
--------------------------------------------------

The parser is one of the most important modules.

Its responsibility:

Take infrastructure files and convert them into a normalized structured representation.

The downstream ML and optimization modules must NOT care whether the input was Terraform, Kubernetes or Docker Compose.

All inputs should eventually become one common schema.

Example normalized representation:

{
    "application_type": "ecommerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,

    "cloud_provider": "aws",
    "region": "ap-south-1",

    "cpu": 4,
    "memory_gb": 8,
    "replicas": 5,
    "storage_gb": 100,

    "autoscaling_enabled": false,

    "source_type": "kubernetes"
}

The exact schema can evolve.

Do not create separate incompatible schemas for each parser.

NEW (Revision 2): generated IaC (Workflow B) must use this SAME normalized representation as its source. The IaC Generation Engine renders from the normalized schema, and every generated artifact is validated by parsing it back through the parser for its target format and comparing the resulting normalized configuration with the selected candidate (round-trip check, Section 44.6).

--------------------------------------------------
# 9. TERRAFORM PARSER
--------------------------------------------------

The Terraform parser should identify relevant cloud infrastructure parameters.

Examples:

- cloud provider
- region
- instance type
- instance count
- CPU / vCPU where available
- memory where available
- storage
- autoscaling
- network-related configuration when relevant
- resource types

For AWS EC2, instance type may need to be mapped to a metadata table containing:

- vCPU
- memory
- architecture
- approximate pricing
- other relevant properties

Do NOT hard-code large amounts of provider metadata into random source files.

Keep infrastructure metadata in a structured configuration or service.

Terraform parsing should initially focus on the infrastructure features needed by the ML and recommendation pipeline.

--------------------------------------------------
# 10. KUBERNETES PARSER
--------------------------------------------------

The Kubernetes parser should support common Deployment-style manifests.

Extract:

- deployment name
- namespace
- replicas
- container image
- CPU requests
- CPU limits
- memory requests
- memory limits
- storage where relevant
- autoscaling configuration
- HPA configuration
- service information where relevant

Example:

replicas: 5

resources:
  requests:
    cpu: 2
    memory: 4Gi
  limits:
    cpu: 4
    memory: 8Gi

Should become normalized features.

--------------------------------------------------
# 11. DOCKER COMPOSE PARSER
--------------------------------------------------

Extract:

- services
- replicas
- CPU allocation
- memory limits
- images
- storage
- resource constraints

Docker Compose support can initially be simpler than Kubernetes support.

Priority:

1. Kubernetes
2. Terraform
3. Docker Compose

Build the first complete end-to-end pipeline using Kubernetes.

Then extend the parser to Terraform and Docker Compose.

--------------------------------------------------
# 12. ML MODEL
--------------------------------------------------

The ML model should NOT blindly predict every project output.

Recommended first ML task:

Predict resource utilization.

Primary outputs:

- predicted CPU utilization
- predicted memory utilization

Inputs can include:

- allocated CPU
- allocated memory
- replicas
- storage
- autoscaling
- application type
- expected users
- traffic level
- performance requirements
- infrastructure characteristics

Possible models:

1. Random Forest Regressor
2. Gradient Boosting
3. XGBoost

Start with Random Forest because it is simple, explainable and suitable for a final-year project.

Compare models if practical.

Do not use deep learning simply because it sounds advanced.

Use the simplest model that performs well.

--------------------------------------------------
# 13. DATASET
--------------------------------------------------

Primary starting dataset:

Google Cluster Workload Trace / Google Cluster Workload Traces 2019 sample.

The dataset is intended primarily for workload/resource utilization modeling.

Potentially use additional public cloud workload datasets later if necessary.

Do NOT download enormous datasets unnecessarily.

The dataset is used during TRAINING.

The dataset is NOT a user input during normal application operation.

Training flow:

Dataset
   ↓
Cleaning
   ↓
Feature engineering
   ↓
Train/test split
   ↓
Model training
   ↓
Evaluation
   ↓
Save trained model
   ↓
model.pkl / appropriate serialized model

Application flow:

User IaC
   ↓
Parser
   ↓
Features
   ↓
Saved model
   ↓
Prediction

--------------------------------------------------
# 14. IMPORTANT DATASET LIMITATION
--------------------------------------------------

The Google workload dataset may not contain all features needed by EcoOps AI.

Do not fabricate real-world measurements.

If a required feature is unavailable:

- derive it using a documented methodology
- use an established model
- use a clearly documented synthetic component
- or explicitly state the limitation

Do NOT claim that the ML model directly learned carbon emissions if it was only trained on CPU/memory traces.

--------------------------------------------------
# 15. ENERGY ESTIMATION
--------------------------------------------------

Energy should be handled carefully.

The ML model can predict utilization.

Energy can then be estimated using a documented energy model based on:

- resource utilization
- infrastructure characteristics
- workload behavior

The project should clearly distinguish:

PREDICTION:

Predicted CPU / memory utilization

from:

ESTIMATION:

Estimated energy consumption

Do not present estimated energy as directly measured physical power unless actual measurement data exists.

--------------------------------------------------
# 16. CARBON ESTIMATION
--------------------------------------------------

Carbon impact can be estimated from energy and carbon intensity.

Conceptually:

carbon impact =
energy consumption × carbon intensity

Carbon intensity depends on region / electricity mix.

The system should clearly label this as an estimate.

Do not claim exact real-world emissions.

--------------------------------------------------
# 17. COST ESTIMATION
--------------------------------------------------

Cost estimation does not necessarily require ML.

It can be calculated from:

- cloud provider
- region
- instance type
- number of instances
- storage
- estimated runtime
- other relevant resources

Use provider pricing data or a configurable pricing table.

Keep pricing logic separate from ML.

Do not hard-code prices throughout the application.

--------------------------------------------------
# 18. CONSTRAINT-AWARE OPTIMIZATION
--------------------------------------------------

This is one of the most important concepts in EcoOps AI.

The system must NOT simply minimize CPU, memory, cost or carbon.

It must optimize under constraints.

Example constraints:

Maximum latency:
150 ms

Availability:
99.9%

Expected users:
10,000

Traffic:
Medium

The system should reject recommendations that violate important constraints.

Conceptually:

Current configuration
        |
        v
Generate candidate configuration
        |
        v
Predict behavior
        |
        v
Check constraints
        |
    +---+---+
    |       |
  FAIL    PASS
    |       |
 Reject    Evaluate
            |
            v
       Cost / Energy /
       Carbon / Performance
            |
            v
      Rank candidates
            |
            v
   Best acceptable configuration

NEW (Revision 2): Workflow B reuses this EXACT loop unchanged — except the candidate configurations come from the Candidate Infrastructure Generator (Section 44.2) instead of the recommendation engine, and there is no "current configuration" to compare against. Constraint failures are recorded and surfaced as explanations; a candidate that violates an important constraint is never selectable, regardless of its ranking score.

--------------------------------------------------
# 19. RECOMMENDATION ENGINE
--------------------------------------------------

The recommendation engine should combine:

- ML predictions
- infrastructure rules
- workload characteristics
- constraints
- cost estimation
- energy estimation
- carbon estimation

It should generate recommendations such as:

- reduce CPU allocation
- reduce memory allocation
- reduce replica count
- enable autoscaling
- adjust autoscaling thresholds
- change instance type
- modify resource requests/limits
- optimize storage
- choose a more efficient architecture where supported

Do NOT make arbitrary recommendations.

Every recommendation must have:

1. Current value
2. Suggested value
3. Reason
4. Expected impact
5. Constraint check result

Example:

{
    "parameter": "cpu",
    "current": "4 cores",
    "recommended": "2 cores",
    "reason": "Predicted utilization is low relative to allocated CPU.",
    "expected_cost_reduction": "...",
    "expected_energy_reduction": "...",
    "expected_carbon_reduction": "...",
    "performance_constraint": "satisfied"
}

--------------------------------------------------
# 20. EXPLAINABILITY
--------------------------------------------------

EcoOps AI should explain recommendations.

Bad:

"Reduce CPU."

Good:

"CPU allocation is 4 cores while predicted utilization is approximately 24%. A candidate configuration using 2 cores satisfies the specified performance constraints and is estimated to reduce resource consumption."

The system should show WHY a recommendation was made.

For ML predictions, where appropriate, use interpretable methods such as:

- feature importance
- SHAP (optional)

Do not make SHAP mandatory if it adds unnecessary complexity.

--------------------------------------------------
# 21. OPTIMIZED CONFIGURATION GENERATION
--------------------------------------------------

After accepting recommendations, generate a modified configuration.

Example:

Original:

replicas: 5

resources:
  requests:
    cpu: "4"
    memory: "8Gi"

Optimized:

replicas: 3

resources:
  requests:
    cpu: "2"
    memory: "4Gi"

The system must NEVER silently overwrite the user's original configuration.

Keep:

- Original configuration
- Recommended configuration

separate.

Allow the user to:

- preview diff
- download optimized file

NEW (Revision 2) — IaC generation for Mode B:

Workflow B has no original file. The IaC Generation Engine produces a NEW configuration artifact from the selected candidate's normalized representation, using deterministic templates (one template set per target: Terraform, Kubernetes, Docker Compose, Terraform+Kubernetes).

Generation rules:

1. Templates are deterministic and readable — no LLM-generated IaC, no shell-outs, no execution.
2. Every generated artifact is validated by a round-trip parse through the parser of its target format (Section 44.6). If the round-trip check fails, generation fails with an error; nothing invalid is ever shown to the user.
3. Generated IaC is stored SEPARATELY as new output and clearly labeled "Generated" in the UI and API. It is never mixed with, or presented as a modification of, any user-uploaded file.
4. Generated IaC is never deployed, applied, or executed by the system (Section 29 applies fully to Mode B).
5. The user can preview, review, and download the generated file(s). Deployment remains a manual human action, exactly as in Mode A.

--------------------------------------------------
# 22. DASHBOARD
--------------------------------------------------

UPDATED (Revision 2) — the dashboard exposes TWO clear entry points on its landing page:

# EcoOps AI

### What do you want to do?

**[ Analyze Existing Infrastructure ]**   **[ Create Sustainable Infrastructure ]**

## Entry point 1 — Analyze Existing Infrastructure (implemented, Phase 11)

User uploads:

- Terraform
- Kubernetes
- Docker Compose

Then enters workload information (the workload form already implemented).

## Entry point 2 — Create Sustainable Infrastructure (new, Phase 17)

User enters workload requirements (Section 4, Mode B form) and selects the desired IaC target (including "Let EcoOps AI choose"). The form uses plain language, sensible defaults, and helper text. The second workflow must NOT force the user to understand IaC syntax — this is important because the application should be usable by someone who understands application/cloud requirements but does not necessarily know Kubernetes or Terraform syntax.

## Mode A result view (implemented)

The dashboard should contain:

### Overview

- Sustainability score
- Cost estimate
- Energy estimate
- Carbon estimate
- Resource utilization

### Current configuration

Show:

- CPU
- memory
- replicas
- storage
- autoscaling
- cloud provider
- region

### Problems detected

Example:

- CPU overprovisioning
- memory overprovisioning
- unnecessary replicas
- autoscaling disabled

### Recommendations

For every recommendation show:

- current
- recommended
- reason
- estimated impact

### Comparison

Current vs optimized:

Cost
Energy
Carbon
Resource utilization
Performance constraints

### Configuration

Show optimized Terraform / Kubernetes / Docker Compose.

## Mode B result view (new)

After generation, show:

### Recommended Infrastructure

- Architecture summary (plain-language description of the selected design)
- CPU
- Memory
- Replica count
- Storage
- Autoscaling
- Cloud provider / region where applicable

### Estimated Impact

- Estimated cost
- Estimated energy consumption
- Estimated carbon impact
- Sustainability score (with methodology disclosure, same score as Mode A)

All values labeled as estimates.

### Why this configuration?

An explainable summary: which constraints were checked and passed, which candidates were rejected and why, what the ranking objective optimized for given the user's priorities, and the prediction basis for the selected candidate. Rejected candidates and their rejection reasons MUST be visible.

### Generated Configuration

Show the generated:

- Terraform, and/or
- Kubernetes YAML, and/or
- Docker Compose

depending on the selected target. Syntax-highlighted, with a per-target download button and a preview/review step before download. Do NOT automatically deploy anything; display an explicit notice that deployment is manual.

If "Let EcoOps AI choose" was used, display WHICH target was selected and the rule that triggered the selection.

--------------------------------------------------
# 23. SUSTAINABILITY SCORE
--------------------------------------------------

EcoOps AI may have a composite score.

Example conceptual components:

- resource efficiency
- energy efficiency
- carbon impact
- cost efficiency
- constraint compliance

Do NOT arbitrarily claim that a score is scientifically accurate.

Clearly define the scoring methodology.

Example:

Sustainability score = weighted normalized metrics.

The weights should be configurable.

NEW (Revision 2): the same score is computed for EVERY Mode B candidate configuration, and the candidate ranking (Section 44.5) uses it as the primary ordering metric after hard constraint filtering. When the user's stated priorities (performance / cost / sustainability) deviate from the default weights, the ranking objective uses priority-derived weights; the score endpoint itself keeps disclosing the exact methodology and weights used, so nothing is hidden from the user.

--------------------------------------------------
# 24. TECHNOLOGY STACK
--------------------------------------------------

Recommended stack:

Frontend:
- React
- Tailwind CSS
- Chart.js / Recharts

Backend:
- Python
- FastAPI

ML:
- Python
- pandas
- NumPy
- scikit-learn
- optional XGBoost

Parsing:
- Python HCL parser for Terraform
- PyYAML for Kubernetes / Docker Compose
- additional validation libraries where necessary

Database:
- PostgreSQL

Development:
- Git
- GitHub
- Docker

Deployment:
- AWS

Potential AWS components:
- EC2 / ECS for application hosting
- S3 for file/object storage if required
- RDS PostgreSQL if database deployment is required

Do not introduce unnecessary AWS services.

--------------------------------------------------
# 25. BACKEND ARCHITECTURE
--------------------------------------------------

Suggested FastAPI structure:

backend/
    app/
        main.py

        api/
            routes/

        core/
            config.py

        models/
            database_models.py

        schemas/
            request_schemas.py
            response_schemas.py

        parsers/
            terraform_parser.py
            kubernetes_parser.py
            docker_compose_parser.py

        ml/
            predictor.py
            model_loader.py

        services/
            analysis_service.py
            energy_service.py
            carbon_service.py
            cost_service.py
            recommendation_service.py
            optimization_service.py

            # NEW (Revision 2) — Mode B services, same app, no new processes:
            generation/
                requirement_engine.py          # Workload Requirement Engine
                candidate_generator.py         # Candidate Infrastructure Generator
                target_selector.py             # "Let EcoOps AI choose" rules
                iac_generator.py               # IaC Generation Engine (templates)
                generation_service.py          # orchestration of Workflow B

        utils/

    tests/

Keep responsibilities separated.

Do not put the entire project into main.py.

--------------------------------------------------
# 26. FRONTEND ARCHITECTURE
--------------------------------------------------

Suggested:

frontend/
    src/
        components/
        pages/
        services/
        hooks/
        types/
        utils/

Important pages:

1. Landing page
2. Analysis / Upload page
3. Workload profile page
4. Analysis result page
5. Recommendation page
6. Configuration comparison page

UPDATED (Revision 2) — the landing page becomes the two-entry-point choice (Section 22), and the following pages/flows are added for Mode B:

7. Generation form page (workload requirements + target selection; plain language, no IaC syntax)
8. Generation result page (recommended infrastructure, estimated impact, "why this configuration?", generated IaC with preview/download)

The generation form reuses the existing workload form component; the result page reuses the existing score, estimate, and configuration display components. The UI should be professional but not excessively complicated.

--------------------------------------------------
# 27. API DESIGN
--------------------------------------------------

Potential endpoints:

POST /api/v1/analyze

Upload infrastructure file + workload profile.

Returns analysis ID.

GET /api/v1/analysis/{id}

Returns analysis result.

POST /api/v1/analysis/{id}/optimize

Runs recommendation / optimization.

GET /api/v1/analysis/{id}/recommendations

Returns recommendations.

GET /api/v1/analysis/{id}/configuration

Returns normalized configuration.

GET /api/v1/analysis/{id}/optimized-config

Returns optimized configuration.

POST /api/v1/validate

Validates uploaded IaC.

These are initial suggestions and may evolve.

NOTE: the implemented Mode A API (Phases 6–11) matches this design and adds per-resource endpoints — see the README API table for the exact implemented list. Mode A endpoints are unchanged by this revision.

UPDATED (Revision 2) — new design-level endpoints for Mode B (Phases 14–17), reusing the same backend and database:

POST /api/v1/generate

Input:

- workload profile (v2 fields required, Section 5)
- generation target (terraform | kubernetes | docker_compose | terraform+kubernetes | auto)
- cloud/deployment preferences (optional; provider, region where applicable)
- constraints (already embedded in the workload profile: latency, availability)

Behavior:

- Normalizes requirements
- Estimates resource requirements
- Generates candidate infrastructures (Section 44.2)
- Evaluates every candidate through the SAME ML / estimation / constraint / score pipeline
- Ranks candidates and selects the best acceptable one
- Generates IaC for the selected candidate (after target selection if "auto")
- Validates the generated IaC by round-trip parse (Section 44.6)

Returns:

- generation/analysis ID (a record of source_mode "workload_generation")

GET /api/v1/generation/{id}

Returns:

- selected architecture (normalized configuration)
- resource requirements
- all evaluated candidates with their estimates and constraint results (including rejected ones and why)
- predicted utilization
- cost / energy / carbon estimates
- explanation (why this configuration; target-selection rule if "auto")

GET /api/v1/generation/{id}/configuration

Returns:

- the generated IaC text for the selected target (labeled "Generated")
- per-target file names
- the round-trip validation result
- download metadata

POST /api/v1/generation/{id}/optimize

Runs candidate evaluation / optimization again if required — for example after the user adjusts requirements or priorities, or to re-run ranking with modified weights. Deterministic and idempotent.

Design notes:

- These are design-level endpoints; implementation may reuse existing endpoints where that is cleaner (e.g., if a generation record is stored as an analysis record with source_mode "workload_generation", the existing per-analysis endpoints may serve parts of the response).
- The generation result must include rejected candidates and rejection reasons for explainability — do not return only the winner.

--------------------------------------------------
# 28. DATABASE
--------------------------------------------------

Potential entities:

User

Project

Analysis

InfrastructureConfiguration

Prediction

Recommendation

OptimizationResult

The database should store metadata and analysis results.

Do not store secrets.

Do not store cloud credentials.

UPDATED (Revision 2) — additive data-model extension ONLY. Do not redesign the existing schema; the existing `analyses` and recommendation tables stay as they are.

An analysis record must be able to distinguish between the two operating modes:

- source_mode:
  - existing_iac       (Mode A — the current, already-implemented behavior)
  - workload_generation (Mode B — new)

- source_type:
  - terraform
  - kubernetes
  - docker_compose
  - generated           (NEW — Mode B output)

- workload_profile (JSON, already stored; v2 fields added inside it)

- infrastructure_configuration (JSON, already stored; for Mode B this is the SELECTED candidate)

- candidate_configurations (NEW, JSON or separate table where applicable): the evaluated candidate set, each with its normalized configuration, predictions, estimates, constraint results, score, and acceptance/rejection reason

- selected_configuration: a reference (id or index) into the candidate set — the best acceptable candidate

- recommendations: unchanged (Mode A); Mode B exposes the candidate ranking instead

- impact estimates: unchanged storage pattern (predictions / estimates on the analysis record)

- generated_iac (NEW, Text + target + file name): the generated Terraform / Kubernetes / Docker Compose text, stored separately and labeled as generated

Implementation guidance: the smallest change is to add nullable columns to the existing analyses table (source_mode, source_type, candidate_configurations, selected_configuration, generated_iac) or a small companion `generations` table linked to it. Existing Mode A rows simply get source_mode = "existing_iac" (or a sensible default at read time). No migration of existing data is required beyond adding columns.

--------------------------------------------------
# 29. SECURITY
--------------------------------------------------

This is a prototype, but basic security is required.

Never execute uploaded Terraform files.

Never run:

terraform apply

kubectl apply

docker compose up

or any other deployment command on user input.

The system is an ANALYZER.

Uploaded IaC should be parsed as text / structured configuration.

Do not allow arbitrary shell execution.

Validate file types.

Limit file size.

Sanitize uploaded files.

Do not expose API keys.

--------------------------------------------------
# 30. PROJECT DEMO
--------------------------------------------------

The final demonstration should use prepared sample infrastructure files.

Prepare at least 3 scenarios.

Scenario 1:

GOOD CONFIGURATION

Expected result:

Few/no recommendations.

Scenario 2:

MODERATELY INEFFICIENT CONFIGURATION

Expected result:

Some recommendations.

Scenario 3:

HEAVILY OVERPROVISIONED CONFIGURATION

Expected result:

Multiple recommendations.

Example:

Bad configuration:

CPU = 8
Memory = 16GB
Replicas = 8
Autoscaling = disabled

Workload:

E-commerce
10,000 users
Medium traffic

EcoOps AI should analyze it and potentially recommend a more appropriate configuration IF the model and constraint engine support that conclusion.

Never hard-code fake results just to make the demo look good.

Demo outputs should be generated by the actual system.

UPDATED (Revision 2) — the final demonstration should also include Mode B scenarios:

Scenario 4:

WORKLOAD-ONLY, "LET ECOPS AI CHOOSE" TARGET

Input: an application workload description only (e.g., bursty e-commerce, 10,000 users, high availability, autoscaling required).

Expected result: the target-selection rule fires visibly, candidate configurations are evaluated, a best acceptable one is selected, and generated IaC is shown and downloadable.

Scenario 5:

WORKLOAD-ONLY, EXPLICIT TARGET

Input: same workload, but the user explicitly picks Kubernetes (or Terraform + Kubernetes).

Expected result: valid generated IaC for the chosen target that round-trip parses to the selected configuration.

Scenarios 4–5 must run on the real pipeline — never hard-coded outputs.

--------------------------------------------------
# 31. PROJECT IMPLEMENTATION ORDER
--------------------------------------------------

IMPORTANT:

Do NOT attempt to build everything simultaneously.

Follow this order.

STATUS (Revision 2): Phases 1–18 are COMPLETE and verified. The order below is the authoritative continuation. Phases 12 and 13 keep their original numbers and intent. Mode B is delivered in NEW Phases 14–17, after the core optimization pipeline is stable (including both remaining parsers) and before final integration/testing. The old Phases 14–17 are renumbered to 18–21 with unchanged content — this is the only renumbering, it affects only PENDING phases, and no completed phase number changes.

PHASE 1:
Repository + project structure                                    [DONE]

PHASE 2:
Kubernetes parser                                                  [DONE]

Goal:

Upload YAML
    ↓
Extract features
    ↓
Return JSON

PHASE 3:
Normalized feature schema                                          [DONE]

PHASE 4:
Dataset preprocessing                                              [DONE]

PHASE 5:
First ML model                                                     [DONE]

PHASE 6:
Prediction API                                                     [DONE]

PHASE 7:
Energy / carbon / cost estimation                                  [DONE]

PHASE 8:
Constraint engine                                                  [DONE]

PHASE 9:
Recommendation engine                                              [DONE]

PHASE 10:
Optimized YAML generation                                          [DONE]

PHASE 11:
Frontend dashboard                                                 [DONE]

PHASE 12:
Terraform parser                                                   [DONE — AWS EC2 subset: aws_instance + provider region + ASG detection, instance-type metadata table, content-based format detection in /analyze and /validate; optimized-file generation remains Kubernetes-only with an explicit 400 for Terraform sources until Phase 16]

PHASE 13:
Docker Compose parser                                              [DONE — services-based subset: primary-service selection for multi-service files with visible warnings, deploy.replicas, v3 deploy.resources + v2 cpus/mem_limit syntaxes, Docker memory-unit semantics; detected structurally via top-level 'services:' since Compose and Kubernetes share the YAML extension; optimized-file generation remains Kubernetes-only with an explicit 400 until Phase 16]

PHASE 14 (NEW — Mode B, part 1):
Workload Requirement Engine                         [DONE — WorkloadProfile v2 additive optional fields (average_rps, peak_rps, traffic_pattern incl. "bursty", storage_gb, autoscaling_required, performance/cost/sustainability priorities) with peak>=average cross-validation, v1 payloads and the ML feature pipeline untouched; backend/app/services/generation/requirement_engine.py with the documented REQUIREMENT_RULES table, discrete CPU/memory sizing ladders, availability-tier replica minimums imported from the constraint engine as the single source of truth, peak factors (derived from RPS ratio when given, pattern/app-type defaults otherwise), and validate_workload_requirements advisory checks for the Phase 17 endpoint; "bursty" never reaches v1 traffic_level; verified 177 tests passing with and without model artifacts]

Goal:

Workload form input (v2 fields)
    ↓
Normalize + validate requirements
    ↓
Deterministic resource requirement estimation (Section 44.1)
    ↓
WorkloadProfile v2 schema finalized (additive, Mode A unaffected)

PHASE 15 (NEW — Mode B, part 2):
Candidate Infrastructure Generator + evaluation loop   [DONE — backend/app/services/generation/candidate_generator.py produces the curated deterministic candidate set (lean/balanced/headroom/elastic along the sizing and replica axes, conditional economy-storage excluded for database/streaming, plus a Terraform-style vm-baseline chosen from the Phase 12 instance-metadata table) as normalized InfrastructureConfigurations; backend/app/services/generation/evaluation_service.py reuses the EXISTING pipeline per candidate (feature extraction -> ML prediction -> estimation -> Phase 8 constraints -> weighted score), with priority-derived ScoreWeights (low/medium/high multipliers over the settings base, normalized and disclosed), hard eligibility gating, deterministic ranking (score, then cost/energy/CPU tie-breaks), and the all-rejected "infeasible" path with per-check explanations; the Phase 14 requirement engine gained a user-capacity replica floor reusing the constraint engine's formula so candidates are never born failing Phase 8 checks; predictor mocked in tests for CI parity; verified 211 tests passing with and without model artifacts]

Goal:

Resource requirements
    ↓
Candidate normalized configurations (sizing / replica / autoscaling variants)
    ↓
Reuse feature extraction + ML prediction + estimation + constraint engine + score for EACH candidate
    ↓
Persisted candidate set with per-candidate results

PHASE 16 (NEW — Mode B, part 3):
IaC Generation Engine + Target Selection            [DONE — backend/app/services/generation/target_selector.py implements the section 44.4 first-match-wins rule list (batch->Compose; database->TF+K8s or TF-alone without storage; autoscaling+bursty/e-commerce/streaming->K8s HPA; ML/AI-inference->K8s; plain autoscaling->K8s; >=100k users or >=99.9% availability->TF+K8s; else Compose) with explicit user choice bypassing the rules and invalid targets rejected; backend/app/services/generation/iac_templates.py renders deterministic literal-value artifacts from the repo's infrastructure/ manifest shapes (Kubernetes Deployment + annotation-based autoscaling, Terraform aws_instance+provider with gp3 root volume, Docker Compose v3 deploy.resources, and the TF+K8s combo emitting BOTH artifacts); backend/app/services/generation/iac_generation_service.py enforces the MANDATORY section 44.6 round-trip guarantee: every artifact is re-parsed through the SAME parser used for user uploads and must reproduce the candidate's resource fields exactly (per-target field sets), with parser raises and undersized/unrenderable shapes wrapped as generation failures so nothing unvalidated is returned; instance-type selection lives once in aws_instance_metadata.smallest_covering_instance_type shared by the Phase 15 VM baseline and the Terraform template; cross-target normalization (container limits, autoscaling drop with visible note) verified; 248 tests passing with and without model artifacts]

Goal:

Selected candidate (normalized)
    ↓
Deterministic templates → Terraform / Kubernetes / Docker Compose / Terraform+Kubernetes
    ↓
Round-trip validation through the Phase 2/12/13 parsers (Section 44.6)
    ↓
"Let EcoOps AI choose" explicit rules (Section 44.4)

PHASE 17 (NEW — Mode B, part 4):
Mode B API + dashboard workflow                      [DONE — POST /api/v1/generate runs the full pipeline (requirement engine -> candidates -> evaluation -> target selection -> IaC rendering) and persists everything in the new `generations` table (migration 005) including rejected candidates; GET /generation/{id} replays a stored generation without re-running the pipeline, /configuration returns the architecture summary, /optimize re-ranks with the stored target; infeasible generations are an explicit 422 with per-check explanations and are still persisted; invalid targets 400, unknown ids 404; frontend gains the two-entry landing ("Analyze existing infrastructure" / "Create sustainable infrastructure"), a workload-only form (no IaC knowledge needed) with target selection incl. "Let EcoOps AI choose", and a result screen with architecture summary, why-this-configuration, impact estimates, rejected-candidate list, and validated-artifact preview/download; predictor mocked in tests for CI parity; 261 backend + 34 frontend tests passing, live smoke verified all endpoints end-to-end with the real model and Mode A regression clean]

PHASE 18 (was 14):
Full integration                                                   [DONE — backend/app/services/optimized_iac_service.py closes the Phase 10 gate by REUSE: optimized analysis-output generation now covers Terraform (Phase 16 template with instance-shape adaptation — re-selection when the stored type does not cover the optimized sizing, cpu/memory snapped to the discrete instance spec, fractional storage rounded up, autoscaling dropped, resource-safe application names — every adaptation a visible note) and Docker Compose (request/limit separation: reservations carry requests, limits carry limits; storage noted as not expressible), each artifact MANDATORILY round-trip validated through the same Phase 12/13 parser used for user uploads and diffed against the never-modified stored original; the Kubernetes Phase 10 path is byte-identical in behavior; per-source dispatch replaces the explicit 400 in GET /analysis/{id}/optimized-config, impossible cases stay explicit 503/400, the response schema gains additive `notes`; the Compose template upgrade (true limits) applies to Mode B generation too; frontend: OptimizedConfigPanel renders all three formats with format-aware filename, notes section and download, DashboardPage offers the full recommendation + optimized-config flow for every source; the Mode B generate page gains the guided demo section with design-doc section 30 scenarios 4 (bursty e-commerce, "Let EcoOps AI choose") and 5 (same workload, explicit Kubernetes); scripts/verify_all_phases.py extended to 63 live checks including Mode B end-to-end for all four targets and the new Mode A per-source paths; verified 280 backend tests with and without model artifacts (CI parity), 22 ML, 38 frontend, live smoke all green]

PHASE 19 (was 15):
Testing                                                            [pending]

PHASE 20 (was 16):
Dockerization                                                      [pending]

PHASE 21 (was 17):
AWS deployment                                                     [pending]

Revised-phase-mapping summary (explicit, as required):

| Original phase | Revised phase | Status |
|---|---|---|
| 1–11 | 1–11 (unchanged) | DONE |
| 12 (Terraform parser) | 12 (unchanged) | DONE (AWS EC2 subset) |
| 13 (Docker Compose parser) | 13 (unchanged) | DONE (services subset) |
| — (did not exist) | 14 (Workload Requirement Engine) | DONE |
| — (did not exist) | 15 (Candidate Generator + evaluation) | DONE |
| — (did not exist) | 16 (IaC Generation + Target Selection) | DONE |
| — (did not exist) | 17 (Mode B API + dashboard) | DONE |
| 14 (Full integration) | 18 | DONE |
| 15 (Testing) | 19 | renumbered |
| 16 (Dockerization) | 20 | renumbered |
| 17 (AWS deployment) | 21 | renumbered |

Phase ordering rationale: the parsers land BEFORE Mode B so that Phase 16 can generate and round-trip-validate Terraform and Docker Compose targets immediately, and so that Mode B candidates in Phase 15 can include Terraform-style normalized configurations (instance types) rather than Kubernetes-only shapes.

--------------------------------------------------
# 32. MVP DEFINITION
--------------------------------------------------

UPDATED (Revision 2) — the project has TWO MVP demonstrations, one per operating mode. Both must work end-to-end.

## MVP A — Existing IaC analysis (achieved, Phases 1–11)

Kubernetes/IaC
    ↓
Workload
    ↓
Analysis
    ↓
Prediction
    ↓
Sustainability
    ↓
Optimization
    ↓
Optimized IaC

## MVP B — Workload-to-infrastructure generation (Phases 14–17)

Workload
    ↓
Infrastructure design
    ↓
Optimization
    ↓
Sustainability analysis
    ↓
Generated IaC

MVP B is successful when:

- accepts workload-only input
- creates a normalized workload representation
- estimates required infrastructure
- evaluates candidate configurations
- respects important constraints
- estimates cost
- estimates energy
- estimates carbon
- selects the best acceptable configuration according to the implemented objective
- generates valid IaC for the selected target
- explains the reasoning
- allows user review
- does not automatically deploy

If MVP A's pipeline works, EcoOps AI has a working analysis core. MVP B proves the same core can also DESIGN infrastructure. Terraform and Docker Compose can then be added as extensions on both paths.

--------------------------------------------------
# 33. VERSION 2 / ADVANCED FEATURES
--------------------------------------------------

Optional features only AFTER the MVP works:

- SHAP explanations
- XGBoost comparison
- multiple cloud providers
- richer Terraform support
- richer Kubernetes support
- automated IaC diff generation
- cloud pricing comparison
- regional carbon-intensity comparison
- historical analysis
- recommendation ranking
- scenario simulation
- user authentication
- cloud deployment
- monitoring integration

Do not implement these before the MVP is stable.

--------------------------------------------------
# 34. GITHUB STRUCTURE
--------------------------------------------------

Recommended:

EcoOps-AI/

    backend/

    frontend/

    ml/

    parsers/

    datasets/

    infrastructure/

        terraform/

        kubernetes/

        docker/

    tests/

    docs/

    scripts/

    README.md

    .gitignore

    docker-compose.yml

The actual structure can be refined during implementation.

UPDATED (Revision 2) — the Mode B services live inside the existing backend app (see Section 25):

backend/app/services/generation/

and the IaC generation templates live beside the parsers:

backend/app/parsers/templates/

No new top-level services, repositories, or processes are introduced.

--------------------------------------------------
# 35. GIT WORKFLOW
--------------------------------------------------

main:
Stable code only.

develop:
Integration branch.

Feature branches can be created when necessary.

Examples:

feature/kubernetes-parser
feature/ml-model
feature/recommendation-engine
feature/frontend
feature/terraform-parser
feature/workload-generation
feature/iac-generation

The primary developer may own most feature branches.

Never force push to main.

Never commit:

- datasets
- secrets
- .env
- API keys
- passwords
- cloud credentials
- generated model artifacts unless intentionally versioned

Use .gitignore.

--------------------------------------------------
# 36. TEAM WORKING MODEL
--------------------------------------------------

The project has five students.

Primary technical responsibility:

Rehann:
~95% of implementation / architecture / integration.

Krishna:
~5% technical contribution, primarily ML/dataset assistance.

Other members have limited technical experience.

Therefore the codebase should be designed so that:

- architecture remains understandable
- modules are independently testable
- documentation is maintained
- no critical module depends on an inexperienced contributor
- Rehann can integrate and debug the complete project

Do not create unnecessary microservices or distributed architecture.

Keep the application modular but simple.

--------------------------------------------------
# 37. CODING PRINCIPLES
--------------------------------------------------

When generating code:

1. Prefer simple, maintainable solutions.
2. Avoid unnecessary complexity.
3. Use typed schemas where appropriate.
4. Add error handling.
5. Add logging.
6. Write unit tests for important logic.
7. Keep ML code separate from API code.
8. Keep parsers separate from optimization logic.
9. Do not hard-code fake predictions.
10. Do not hard-code fake sustainability results.
11. Do not silently modify user files.
12. Preserve original input.
13. Use configuration files/environment variables for settings.
14. Do not expose secrets.
15. Write documentation for non-obvious logic.

--------------------------------------------------
# 38. IMPORTANT PROJECT PRINCIPLE
--------------------------------------------------

EcoOps AI is NOT:

"AI automatically decides how much infrastructure every application needs."

Instead:

"EcoOps AI uses infrastructure configuration, workload characteristics, machine learning predictions, sustainability estimation and performance constraints to provide evidence-based optimization recommendations."

The system should acknowledge uncertainty.

Predictions are estimates.

Recommendations are advisory.

The engineer makes the final deployment decision.

UPDATED (Revision 2) — this principle extends to Mode B:

"AI automatically designs and provisions infrastructure for every application." is also NOT what EcoOps AI does.

Mode B is requirement-based DESIGN SUPPORT, not autonomous provisioning. The system derives resource requirements from documented deterministic rules, evaluates candidates with the same evidence-based pipeline (ML predictions, estimates, constraints), and presents a ranked selection with full reasoning. The generated IaC is a PROPOSAL for human review — the engineer still reviews, downloads, and deploys manually. Uncertainty language (estimated / predicted / expected) applies to Mode B outputs exactly as it does to Mode A.

--------------------------------------------------
# 39. WHAT NOT TO CLAIM
--------------------------------------------------

Do not claim:

- exact carbon emissions
- guaranteed cost savings
- guaranteed performance
- perfect ML predictions
- production-ready cloud optimization
- automatic cloud deployment
- universal optimal infrastructure
- that the ML model knows the exact infrastructure required for any application

Instead use language such as:

- estimated
- predicted
- expected
- benchmark-based
- constraint-aware
- advisory
- prototype

--------------------------------------------------
# 40. SUCCESS CRITERIA
--------------------------------------------------

EcoOps AI should be considered successful if:

1. It accepts supported IaC files.
2. It correctly parses infrastructure parameters.
3. It normalizes configurations into a common schema.
4. It accepts workload characteristics.
5. It produces ML-based resource utilization predictions.
6. It estimates energy consumption.
7. It estimates carbon impact.
8. It estimates cloud cost.
9. It identifies inefficient configurations.
10. It generates constraint-aware recommendations.
11. It explains why recommendations were made.
12. It generates an optimized configuration.
13. It shows current vs optimized metrics.
14. It never automatically deploys infrastructure.
15. The complete workflow can be demonstrated locally.

UPDATED (Revision 2) — additional success criteria for Mode B (workload generation):

16. It accepts workload-only input (no IaC file).
17. It creates a normalized workload representation from the form input.
18. It estimates required infrastructure from documented, deterministic rules.
19. It evaluates multiple candidate configurations through the shared ML / estimation / constraint pipeline.
20. It respects important constraints (candidates violating them are rejected, visibly).
21. It estimates cost, energy, and carbon for every candidate.
22. It selects the best acceptable configuration according to the implemented ranking objective and the user's stated priorities.
23. It generates valid IaC for the selected target (Terraform, Kubernetes, Docker Compose, or Terraform+Kubernetes), validated by round-trip parsing.
24. It explains the reasoning (requirements → resources → candidates → selection → generation, including rejected candidates).
25. It allows user review (preview and download; no automatic deployment ever).
26. Both MVP A and MVP B (Section 32) can be demonstrated end-to-end locally.

--------------------------------------------------
# 41. DEVELOPMENT RULE FOR CODEX
--------------------------------------------------

Do NOT immediately generate the entire project.

Build incrementally.

Before implementing a major module:

1. Inspect the existing repository.
2. Understand the current architecture.
3. Reuse existing code.
4. Avoid duplicate functionality.
5. Explain the planned changes.
6. Implement the smallest working version.
7. Run tests.
8. Fix errors.
9. Update documentation.

When a requirement is ambiguous, prefer asking for clarification rather than inventing a major architectural decision.

Never silently change the project's core scope.

--------------------------------------------------
# 42. FIRST DEVELOPMENT TASK
--------------------------------------------------

The first implementation task is NOT ML.

First build:

Kubernetes YAML upload
        ↓
Validation
        ↓
Parser
        ↓
Normalized JSON
        ↓
API response

Example expected output:

{
    "source_type": "kubernetes",
    "application": "backend",
    "replicas": 5,
    "cpu_request": 2,
    "cpu_limit": 4,
    "memory_request_gb": 4,
    "memory_limit_gb": 8,
    "autoscaling_enabled": false
}

Only after this works should ML integration begin.

--------------------------------------------------
# 43. FINAL PROJECT VISION
--------------------------------------------------

UPDATED (Revision 2) — the final project vision is:

"An AI-powered pre-deployment cloud sustainability advisor that can either analyze an existing Infrastructure as Code configuration or design and generate an optimized infrastructure configuration from workload requirements."

The two paths should be clearly visible:

Engineer already has infrastructure:
→ Analyze → Optimize → Review

Engineer only has application/workload requirements:
→ Design → Optimize → Generate → Review

EcoOps AI should feel like an intelligent pre-deployment review assistant for cloud engineers.

The experience should be:

Engineer:

"I want to deploy this application."

EcoOps AI:

"Do you already have your infrastructure configuration, or should I help you design it from your workload requirements?"

## Path A — the engineer already has infrastructure

Engineer uploads:

Terraform / Kubernetes / Docker Compose

and describes the expected workload.

EcoOps AI:

"I analyzed your configuration."
"Here is the predicted utilization."
"Here is the estimated cost."
"Here is the estimated energy consumption."
"Here is the estimated carbon impact."
"These resources appear overprovisioned."
"Here are alternative configurations."
"This recommendation satisfies your performance constraints."
"Here is why I recommend it."
"Here is the expected impact."
"Here is the optimized configuration."

Engineer:

"Review → Download → Deploy manually."

## Path B — the engineer only has application/workload requirements

Engineer describes:

Application type, users, traffic, latency, availability, storage, autoscaling, and priorities — in a plain-language form.

EcoOps AI:

"I designed a candidate infrastructure from your requirements."
"Here is the recommended architecture and its resources."
"Here is the predicted utilization."
"Here is the estimated cost, energy, and carbon impact."
"Every constraint you set is satisfied by this configuration."
"Here are the alternatives I evaluated and why they were not selected."
"Here is why this configuration was chosen."
"Here is the generated Terraform / Kubernetes / Docker Compose."

Engineer:

"Review → Download → Deploy manually."

Nothing is ever deployed automatically on either path.

That is the complete EcoOps AI concept.

--------------------------------------------------
# 44. MODE B ARCHITECTURE DETAIL (NEW — Revision 2)
--------------------------------------------------

This section is the implementation specification for the new Mode B modules (Phases 14–17). It defines exactly enough to build them; anything not specified here follows the existing codebase conventions.

## 44.1 Workload Requirement Engine (Phase 14)

Purpose: turn the Mode B form input into a validated WorkloadProfile v2 and a resource-requirement estimate.

Steps:

1. Normalize and validate the v2 workload fields (Section 5). Reject impossible combinations with clear errors (e.g., peak RPS below average RPS; availability target below 90% with "high" performance priority is allowed but flagged as unusual, never silently changed).
2. Estimate a BASE resource requirement deterministically, per application type. Documented starting rules (all constants live in a configurable table, not scattered hard-codes; values are starting points refined during Phase 14 testing):

   - Per-request concurrency factor by application type (e.g., rest-api and web-application handle more requests per CPU-core than machine-learning or ai-inference; database and streaming get a memory-dominant profile; batch gets a throughput profile dominated by total work rather than latency).
   - CPU requirement ≈ f(peak RPS, app-type factor), rounded up to a discrete CPU size (0.5 / 1 / 2 / 4 / 8 cores).
   - Memory requirement ≈ g(CPU, app-type memory ratio, storage-adjacent needs for database/streaming), rounded to discrete sizes (1 / 2 / 4 / 8 / 16 / 32 GiB).
   - Replica count: minimum 2 when availability target ≥ 99.9% or autoscaling required; minimum 1 otherwise; expected-replica estimate derived from average vs peak RPS ratio.
   - Storage: taken directly from the user's storage requirement (no invention).
   - Latency and availability requirements are NOT consumed here — they are constraints consumed later by the constraint engine. The requirement engine only records them.

3. Output: a structured requirement object (required CPU, memory, replica estimate, storage, autoscaling flag) that feeds candidate generation. This object is intermediate — it is persisted as part of the generation record for explainability, but it is NOT itself an infrastructure configuration.

IMPORTANT: these rules are deterministic and documented. They may be crude — that is acceptable for a B.Tech prototype as long as they are honest, labeled as estimates, and visible in the explanation. Do NOT train a second ML model to "predict infrastructure size"; the existing utilization model provides the evidence downstream.

## 44.2 Candidate Infrastructure Generator (Phase 15)

Purpose: produce a SMALL set (target: 3–6, never more than ~10) of concrete candidate configurations from the requirement estimate.

Candidates vary along exactly three axes:

1. Sizing: undersized (requirement −1 step), required (the estimate), headroom (+1 step) — subject to a floor of the minimum viable size.
2. Replica strategy: fixed replicas at the estimate; fixed replicas at the availability minimum; autoscaling enabled (min = availability minimum, max = peak-RPS-derived ceiling).
3. Storage: as requested; plus one economy option where the app type tolerates it (never for database/streaming).

Each candidate becomes a NORMALIZED InfrastructureConfiguration — the same schema Mode A produces from parsers. This is the key architectural reuse point: downstream, candidates are indistinguishable from parsed infrastructure.

## 44.3 Candidate evaluation (reuse — no new code paths)

Every candidate is evaluated through the EXISTING pipeline, in the existing services:

Feature extraction → ML utilization prediction → energy estimation → carbon estimation → cost estimation → constraint engine → sustainability score.

Constraint inputs per candidate: the user's latency, availability, users, and traffic requirements (the same five feasibility checks implemented in Phase 8, using the candidate's allocations in place of a parsed configuration's).

Output per candidate: predictions, estimates, constraint results (per-check pass/fail with explanations), and score. All of it is persisted with the generation record — rejected candidates included.

A candidate with ANY failed important constraint is marked ineligible. Ineligible candidates can never be selected, regardless of score. If ALL candidates are ineligible, the generation fails with an explanatory response (which constraints failed and why) — the system must NOT return a constraint-violating configuration "as a best effort". The user can relax requirements and retry.

## 44.4 Target Selection — "Let EcoOps AI choose" (Phase 16)

Explicit, ordered rules evaluated against the normalized requirements. The FIRST matching rule wins, and the matched rule is reported in the explanation. No ML, no LLM, no magic.

1. If application type = batch processing → **Docker Compose** (or Terraform for VM-based batch): scheduled, non-latency-critical work does not need an orchestrator.
2. Else if application type = database → **Terraform + Kubernetes**: managed-or-StatefulSet data tier via Terraform-provisioned storage; if no storage requirement was given, prefer **Terraform** alone (managed database).
3. Else if autoscaling required AND (traffic pattern = bursty OR application type ∈ {e-commerce, streaming}) → **Kubernetes** (HPA is the designed mechanism).
4. Else if application type = machine-learning or ai-inference → **Kubernetes** (GPU scheduling semantics) — with Terraform available for node provisioning at V2.
5. Else if autoscaling required → **Kubernetes**.
6. Else if expected users ≥ 100,000 OR availability ≥ 99.9% → **Terraform + Kubernetes**.
7. Else (simple small services) → **Docker Compose**; if cloud-provider resources (managed DB, object storage, VPC) were implied by the requirements → **Terraform + Docker Compose** pattern rendered as Terraform (+ Compose for the app tier).

Explicitly selected targets skip this module entirely. When the user chooses "Terraform + Kubernetes", the generation engine emits BOTH artifacts (Terraform for provider resources + Kubernetes manifests for the workloads) and validates each with its own parser.

## 44.5 Candidate ranking (Phase 15/16)

Ranking objective over eligible candidates:

- Primary metric: the sustainability score (Section 23) computed per candidate.
- Priority-derived weights: the user's performance / cost / sustainability priorities (low / medium / high) adjust the score's component weights within the existing configurable-weights mechanism. High performance priority increases the weight of the utilization/performance components; high cost priority increases cost-efficiency weight; high sustainability priority increases energy/carbon weights.
- Deterministic tie-breaking: lower cost, then lower energy, then lower CPU.
- The EXACT weights used for a generation are stored with the record and disclosed in the response and UI — same transparency rule as the Mode A score endpoint.

The system must NOT simply minimize CPU, memory, cost, or carbon: hard constraints gate eligibility first, and the weighted objective balances the remaining dimensions.

## 44.6 IaC Generation and round-trip validation (Phase 16)

The IaC Generation Engine renders the selected candidate's normalized configuration through deterministic, readable templates — one template set per target (Terraform, Kubernetes, Docker Compose, Terraform+Kubernetes combo).

Mandatory validation: every generated artifact is parsed back through the SAME parser that handles user uploads of that format (Phase 2 Kubernetes parser; Phase 12 Terraform parser; Phase 13 Docker Compose parser). The re-parsed normalized configuration must reproduce the selected candidate's resource fields (cpu, memory, replicas, storage, autoscaling) exactly. Any mismatch is a generation failure (HTTP 500-class error, logged); nothing unvalidated is returned to the user. This is the strongest correctness guarantee available without executing anything — and execution remains forbidden (Section 29).

Template guidance: start from the repo's existing `infrastructure/` example manifests as template shapes; keep templates boring, commented, and version-controlled in `backend/app/parsers/templates/`. Region/provider metadata comes from the existing configurable pricing/metadata tables (Section 9 principle) — never hard-coded in templates.

## 44.7 Explainability for Mode B (Phase 17)

The generation response and result screen must include, in plain language:

1. The derived resource requirements and the rule/constants that produced them.
2. The target selection rule that fired (if "auto").
3. Per-candidate: allocations, score, constraint results, and the estimate values used in ranking.
4. Why each rejected candidate was rejected (failed check names + explanations).
5. Why the winner won (weight disclosure + tie-break notes where relevant).
6. The estimate/prediction disclaimer language from Sections 15/16/39, applied to every number shown.

## 44.8 Testing requirements for Mode B

- Requirement engine: deterministic outputs for representative inputs; validation rejections for impossible inputs.
- Candidate generator: candidate count within bounds; floor/ceiling respected; deterministic given the same input.
- Evaluation loop: reuse means the existing per-service tests carry over; add one integration test per candidate axis (sizing/replica/storage).
- Target selection: table-driven tests over the rule list, including first-match-wins precedence.
- IaC generation: for each target, render → parse round-trip equality on resource fields; golden-file tests for template output.
- API: contract tests for the four generation endpoints, including the all-candidates-rejected failure path.
- Frontend: form validation, result-screen rendering with real response shapes, preview/download interactions.

END OF SECTION 44 — END OF DESIGN DOCUMENT.