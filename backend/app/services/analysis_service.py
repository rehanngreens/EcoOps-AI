from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.schemas.infrastructure_schema import InfrastructureConfiguration
from app.schemas.unified_schema import FeatureVector
from app.schemas.workload_schema import WorkloadProfile


def create_analysis(
    db: Session,
    configuration: InfrastructureConfiguration,
    workload: WorkloadProfile,
    features: FeatureVector,
) -> Analysis:
    record = Analysis(
        id=str(uuid4()),
        configuration=configuration.model_dump(),
        workload=workload.model_dump(),
        features=features.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_analysis(db: Session, analysis_id: str) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def to_configuration(record: Analysis) -> InfrastructureConfiguration:
    return InfrastructureConfiguration.model_validate(record.configuration)


def to_workload(record: Analysis) -> WorkloadProfile:
    if record.workload is None:
        return WorkloadProfile()
    return WorkloadProfile.model_validate(record.workload)


def to_features(record: Analysis) -> FeatureVector | None:
    if record.features is None:
        return None
    return FeatureVector.model_validate(record.features)
