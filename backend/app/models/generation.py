"""Mode B generation records (design doc sections 44, 25).

One row per generation request: the normalized requirements, the full
candidate evaluation (eligible and rejected candidates alike), the target
selection, and the generated IaC artifacts. JSON columns mirror the Pydantic
schemas so the API can replay a stored generation without re-running the
pipeline.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class GenerationRecord(Base):
    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    workload: Mapped[dict] = mapped_column(JSON, nullable=False)
    requirements: Mapped[dict] = mapped_column(JSON, nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    target_source: Mapped[str] = mapped_column(String(16), nullable=False)
    target_explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    evaluation: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifacts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    selected_configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disclaimer: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def new_generation_id() -> str:
    return str(uuid.uuid4())
