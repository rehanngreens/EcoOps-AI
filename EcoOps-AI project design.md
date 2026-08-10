# EcoOps AI

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

--------------------------------------------------
# 4. USER INPUT
--------------------------------------------------

The main user input is Infrastructure as Code.

Supported formats:

1. Terraform (.tf)
2. Kubernetes YAML manifests (.yaml / .yml)
3. Docker Compose (.yaml / .yml)

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

Performance requirements:

Maximum acceptable latency:
e.g. 150 ms

Availability requirement:
e.g. 99.9%

These values become part of the feature set and are used to make recommendations more context-aware.

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

--------------------------------------------------
# 22. DASHBOARD
--------------------------------------------------

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

The UI should be professional but not excessively complicated.

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

--------------------------------------------------
# 31. PROJECT IMPLEMENTATION ORDER
--------------------------------------------------

IMPORTANT:

Do NOT attempt to build everything simultaneously.

Follow this order.

PHASE 1:
Repository + project structure

PHASE 2:
Kubernetes parser

Goal:

Upload YAML
    ↓
Extract features
    ↓
Return JSON

PHASE 3:
Normalized feature schema

PHASE 4:
Dataset preprocessing

PHASE 5:
First ML model

PHASE 6:
Prediction API

PHASE 7:
Energy / carbon / cost estimation

PHASE 8:
Constraint engine

PHASE 9:
Recommendation engine

PHASE 10:
Optimized YAML generation

PHASE 11:
Frontend dashboard

PHASE 12:
Terraform parser

PHASE 13:
Docker Compose parser

PHASE 14:
Full integration

PHASE 15:
Testing

PHASE 16:
Dockerization

PHASE 17:
AWS deployment

--------------------------------------------------
# 32. MVP DEFINITION
--------------------------------------------------

The MVP is:

Kubernetes YAML
    ↓
Parser
    ↓
Feature extraction
    ↓
ML utilization prediction
    ↓
Energy estimate
    ↓
Carbon estimate
    ↓
Cost estimate
    ↓
Constraint checking
    ↓
Recommendation
    ↓
Dashboard

If this pipeline works, EcoOps AI has a working core.

Terraform and Docker Compose can then be added as extensions.

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

EcoOps AI should feel like an intelligent pre-deployment review assistant for cloud engineers.

The experience should be:

Engineer:

"I want to deploy this application."

EcoOps AI:

"Upload your infrastructure configuration and describe your expected workload."

Engineer uploads:

Terraform / Kubernetes / Docker Compose

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

That is the complete EcoOps AI concept.