from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.schemas.infrastructure_schema import InfrastructureConfiguration


def create_analysis(
    db: Session,
    configuration: InfrastructureConfiguration,
) -> Analysis:
    record = Analysis(
        id=str(uuid4()),
        configuration=configuration.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_analysis(db: Session, analysis_id: str) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def to_configuration(record: Analysis) -> InfrastructureConfiguration:
    return InfrastructureConfiguration.model_validate(record.configuration)
