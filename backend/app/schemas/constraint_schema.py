from enum import Enum

from pydantic import BaseModel, Field


class ConstraintStatus(str, Enum):
    """Outcome of one constraint check."""

    pass_ = "pass"
    fail = "fail"


class ConstraintCheck(BaseModel):
    """One named constraint check with a transparent explanation."""

    name: str
    status: ConstraintStatus
    required: str
    actual: str
    explanation: str


class ConstraintEvaluation(BaseModel):
    """Overall constraint evaluation for one configuration."""

    satisfied: bool
    checks: list[ConstraintCheck] = Field(default_factory=list)
    disclaimer: str
