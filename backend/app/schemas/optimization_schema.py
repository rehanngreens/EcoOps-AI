from enum import Enum

from pydantic import BaseModel, Field


class ConfigChange(BaseModel):
    """One parameter changed between the original and optimized manifest."""

    parameter: str
    from_value: str = Field(..., alias="from")
    to_value: str = Field(..., alias="to")

    model_config = {"populate_by_name": True}


class OptimizedConfigResponse(BaseModel):
    """Original and optimized manifests with a readable diff."""

    analysis_id: str
    source: str  # "stored_original" or "canonical"
    original_yaml: str
    optimized_yaml: str
    diff: list[str] = Field(default_factory=list)
    changes: list[ConfigChange] = Field(default_factory=list)
    disclaimer: str
