import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class RecommendationSetRecord(Base):
    __tablename__ = "recommendation_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    optimized_configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    totals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rejected_candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecommendationItemRecord(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    recommendation_set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recommendation_sets.id", ondelete="CASCADE"), nullable=False
    )
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    current_value: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)


def new_recommendation_set_id() -> str:
    return str(uuid.uuid4())


def new_recommendation_item_id() -> str:
    return str(uuid.uuid4())
