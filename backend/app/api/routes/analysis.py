import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.parsers.kubernetes_parser import (
    KubernetesParserError,
    parse_kubernetes_yaml,
    validate_kubernetes_yaml,
)
from app.schemas.infrastructure_schema import (
    AnalysisConfigurationResponse,
    InfrastructureConfiguration,
    ValidationResponse,
)
from app.schemas.unified_schema import (
    AnalysisConstraintsResponse,
    AnalysisFeaturesResponse,
    AnalyzeResponse,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services import (
    analysis_service,
    constraint_service,
    estimation_service,
    prediction_service,
)
from app.services.feature_service import extract_features
from app.services.prediction_service import (
    ModelArtifactsUnavailableError,
    ModelCompatibilityError,
)

router = APIRouter(prefix="/api/v1")
settings = get_settings()

ALLOWED_EXTENSIONS = {ext.lower() for ext in settings.allowed_upload_extension_list}


def _validate_upload(file: UploadFile, content: bytes) -> None:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Allowed: {allowed}",
        )

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds maximum upload size of "
                f"{settings.max_upload_size_bytes} bytes"
            ),
        )


def _decode_upload(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be UTF-8 encoded text",
        ) from exc


def _parse_upload(yaml_text: str) -> InfrastructureConfiguration:
    try:
        parsed = parse_kubernetes_yaml(yaml_text)
    except KubernetesParserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return InfrastructureConfiguration.model_validate(parsed)


def _parse_workload(raw: str | None) -> WorkloadProfile:
    if raw is None or not raw.strip():
        return WorkloadProfile()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workload JSON",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workload must be a JSON object",
        )

    try:
        return WorkloadProfile.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


@router.post("/validate", response_model=ValidationResponse)
async def validate_manifest(file: UploadFile) -> ValidationResponse:
    content = await file.read()
    _validate_upload(file, content)
    yaml_text = _decode_upload(content)
    errors = validate_kubernetes_yaml(yaml_text)
    return ValidationResponse(valid=not errors, errors=errors)


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_201_CREATED)
async def analyze_manifest(
    file: UploadFile,
    workload: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    content = await file.read()
    _validate_upload(file, content)
    yaml_text = _decode_upload(content)
    configuration = _parse_upload(yaml_text)
    workload_profile = _parse_workload(workload)
    features = extract_features(configuration, workload_profile)
    try:
        prediction = prediction_service.predict_utilization(features)
    except (ModelArtifactsUnavailableError, ModelCompatibilityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    record = analysis_service.create_analysis(
        db,
        configuration,
        workload_profile,
        features,
    )
    estimation = estimation_service.estimate_sustainability(features, prediction)
    constraints = constraint_service.evaluate_constraints(features, prediction)
    return AnalyzeResponse(
        analysis_id=record.id,
        configuration=configuration,
        workload=workload_profile,
        features=features,
        prediction=prediction,
        estimation=estimation,
        constraints=constraints,
    )


@router.get(
    "/analysis/{analysis_id}/configuration",
    response_model=AnalysisConfigurationResponse,
)
def get_analysis_configuration(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisConfigurationResponse:
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        )
    return AnalysisConfigurationResponse(
        analysis_id=record.id,
        configuration=analysis_service.to_configuration(record),
    )


@router.get(
    "/analysis/{analysis_id}/features",
    response_model=AnalysisFeaturesResponse,
)
def get_analysis_features(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisFeaturesResponse:
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        )

    features = analysis_service.to_features(record)
    if features is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Features for analysis '{analysis_id}' not found",
        )

    return AnalysisFeaturesResponse(
        analysis_id=record.id,
        workload=analysis_service.to_workload(record),
        features=features,
    )


@router.get(
    "/analysis/{analysis_id}/constraints",
    response_model=AnalysisConstraintsResponse,
)
def get_analysis_constraints(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisConstraintsResponse:
    """Recompute constraint feasibility from the stored analysis record."""
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        )

    features = analysis_service.to_features(record)
    if features is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Features for analysis '{analysis_id}' not found",
        )

    try:
        prediction = prediction_service.predict_utilization(features)
    except (ModelArtifactsUnavailableError, ModelCompatibilityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    constraints = constraint_service.evaluate_constraints(features, prediction)
    return AnalysisConstraintsResponse(
        analysis_id=record.id,
        constraints=constraints,
    )
