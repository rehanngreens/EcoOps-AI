from pydantic import BaseModel, Field


class ScoreComponent(BaseModel):
    """One normalized (0-1) score component with its methodology disclosed."""

    name: str
    raw_value: str
    score: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)
    explanation: str


class SustainabilityScore(BaseModel):
    """Composite weighted sustainability score (design doc section 23).

    Explicitly a documented prototype heuristic: a weighted mean of
    normalized component scores. It is not a scientifically validated
    benchmark and must always be presented with its methodology.
    """

    score: float = Field(..., ge=0, le=1)
    grade: str
    components: list[ScoreComponent]
    methodology: str
    disclaimer: str


class AnalysisScoreResponse(BaseModel):
    analysis_id: str
    score: SustainabilityScore
