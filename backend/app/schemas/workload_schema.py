from typing import Literal

from pydantic import BaseModel, Field, field_validator

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


class WorkloadProfile(BaseModel):
    application_type: ApplicationType = "rest-api"
    expected_users: int = Field(default=1000, ge=0)
    traffic_level: TrafficLevel = "medium"
    max_latency_ms: int = Field(default=200, gt=0)
    availability_target: float = Field(default=99.0, ge=0, le=100)

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
