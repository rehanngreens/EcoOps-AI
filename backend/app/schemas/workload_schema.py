from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ApplicationType = Literal[
    "web-application",
    "e-commerce",
    "rest-api",
    "database",
    "machine-learning",
    "ai-inference",
    "streaming",
    "batch",
    "microservices",
]

TrafficLevel = Literal["low", "medium", "high", "variable"]

# v2 (Mode B): richer traffic-pattern input. "bursty" is deliberately ONLY a
# v2 traffic_pattern value — it must never be assigned to v1 traffic_level,
# which feeds feature_service.TRAFFIC_SCORES (a KeyError otherwise).
TrafficPattern = Literal["low", "medium", "high", "variable", "bursty"]

Priority = Literal["low", "medium", "high"]


class WorkloadProfile(BaseModel):
    # v1 fields (Mode A, Phase 3) — unchanged defaults and validation.
    application_type: ApplicationType = "rest-api"
    expected_users: int = Field(default=1000, ge=0)
    traffic_level: TrafficLevel = "medium"
    max_latency_ms: int = Field(default=200, gt=0)
    availability_target: float = Field(default=99.0, ge=0, le=100)

    # v2 fields (Mode B, Phase 14) — all optional so v1 payloads, stored
    # analysis JSON, and the ML feature pipeline are unaffected. The ML
    # pipeline consumes ONLY the v1 fields.
    average_rps: float | None = Field(default=None, ge=0)
    peak_rps: float | None = Field(default=None, ge=0)
    traffic_pattern: TrafficPattern | None = None
    storage_gb: float | None = Field(default=None, ge=0)
    autoscaling_required: bool | None = None
    performance_priority: Priority = "medium"
    cost_priority: Priority = "medium"
    sustainability_priority: Priority = "medium"

    @field_validator("traffic_level", mode="before")
    @classmethod
    def normalize_traffic_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @field_validator("application_type", mode="before")
    @classmethod
    def normalize_application_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @model_validator(mode="after")
    def check_peak_not_below_average(self) -> "WorkloadProfile":
        if (
            self.average_rps is not None
            and self.peak_rps is not None
            and self.peak_rps < self.average_rps
        ):
            raise ValueError(
                f"peak_rps ({self.peak_rps}) must be >= average_rps ({self.average_rps})"
            )
        return self
