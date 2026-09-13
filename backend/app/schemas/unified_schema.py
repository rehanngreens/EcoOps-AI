from pydantic import BaseModel, Field

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


class AnalyzeResponse(BaseModel):
    analysis_id: str
    configuration: InfrastructureConfiguration
    workload: WorkloadProfile
    features: FeatureVector
    prediction: UtilizationPrediction
class AnalysisFeaturesResponse(BaseModel):

    analysis_id: str
    workload: WorkloadProfile
    features: FeatureVector
