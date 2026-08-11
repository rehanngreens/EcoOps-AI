from pydantic import BaseModel, Field


class InfrastructureConfiguration(BaseModel):
    source_type: str = Field(..., examples=["kubernetes"])
    application: str
    namespace: str = "default"
    replicas: int = 1
    cpu_request: float | None = None
    cpu_limit: float | None = None
    memory_request_gb: float | None = None
    memory_limit_gb: float | None = None
    autoscaling_enabled: bool = False
    container_image: str | None = None


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    analysis_id: str
    configuration: InfrastructureConfiguration


class AnalysisConfigurationResponse(BaseModel):
    analysis_id: str
    configuration: InfrastructureConfiguration
