from pydantic import BaseModel, Field

from app.schemas.constraint_schema import ConstraintEvaluation
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.workload_schema import WorkloadProfile


class UnifiedConfiguration(BaseModel):
    """Merged infrastructure and workload representation for downstream ML."""

    application_type: str
    expected_users: int
    traffic_level: str
    max_latency_ms: int
    availability_target: float
    cpu: float
    memory_gb: float
    replicas: int
    storage_gb: float | None = None
    autoscaling_enabled: bool
    source_type: str


class FeatureVector(BaseModel):
    """Flat ML-ready feature vector derived from infra + workload."""

    application_type: str
    application_type_code: int
    expected_users: int
    traffic_level: str
    traffic_score: int
    max_latency_ms: int
    availability_target: float
    cpu: float
    memory_gb: float
    replicas: int
    storage_gb: float | None = None
    autoscaling_enabled: bool
    autoscaling_enabled_int: int = Field(..., ge=0, le=1)
    source_type: str
    total_cpu_capacity: float
    total_memory_capacity: float
    users_per_replica: float


class UtilizationPrediction(BaseModel):
    """CPU and memory utilization returned by the trained Phase 5 models."""

    cpu_utilization: float = Field(..., ge=0, le=1)
    memory_utilization: float = Field(..., ge=0, le=1)
    model_type: str
    model_created_at: str | None = None

class EstimationAssumptions(BaseModel):
    """Configurable prototype assumptions used for cost, energy, and carbon estimates."""

    period_hours: float = Field(..., gt=0)
    cpu_cost_per_vcpu_hour_usd: float = Field(..., ge=0)
    memory_cost_per_gb_hour_usd: float = Field(..., ge=0)
    cpu_power_watts_per_active_vcpu: float = Field(..., ge=0)
    memory_power_watts_per_active_gb: float = Field(..., ge=0)
    data_center_pue: float = Field(..., ge=1)
    carbon_intensity_gco2_per_kwh: float = Field(..., ge=0)


class SustainabilityEstimation(BaseModel):
    """Transparent cost, energy, and carbon estimate for one analysis period."""

    estimated_cost_usd: float = Field(..., ge=0)
    estimated_energy_kwh: float = Field(..., ge=0)
    estimated_carbon_kg_co2e: float = Field(..., ge=0)
    active_cpu_vcpus: float = Field(..., ge=0)
    active_memory_gb: float = Field(..., ge=0)
    assumptions: EstimationAssumptions
    disclaimer: str


class AnalyzeResponse(BaseModel):
    analysis_id: str
    configuration: InfrastructureConfiguration
    workload: WorkloadProfile
    features: FeatureVector
    prediction: UtilizationPrediction
    estimation: SustainabilityEstimation
    constraints: ConstraintEvaluation


class AnalysisFeaturesResponse(BaseModel):
    analysis_id: str
    workload: WorkloadProfile
    features: FeatureVector


class AnalysisConstraintsResponse(BaseModel):
    analysis_id: str
    constraints: ConstraintEvaluation
