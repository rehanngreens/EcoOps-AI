import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.parsers.docker_compose_parser import (
    DockerComposeParserError,
    parse_docker_compose,
    validate_docker_compose,
)
from app.parsers.kubernetes_parser import (
    KubernetesParserError,
    parse_kubernetes_yaml,
    validate_kubernetes_yaml,
)
from app.parsers.terraform_parser import (
    TerraformParserError,
    parse_terraform,
    validate_terraform,
)
from app.schemas.infrastructure_schema import (
    AnalysisConfigurationResponse,
    InfrastructureConfiguration,
    ValidationResponse,
)
from app.schemas.optimization_schema import OptimizedConfigResponse
from app.schemas.recommendation_schema import AnalysisRecommendationsResponse, OptimizeResponse
from app.schemas.score_schema import AnalysisScoreResponse
from app.schemas.unified_schema import (
    AnalysisConstraintsResponse,
    AnalysisFeaturesResponse,
    AnalyzeResponse,
)
from app.schemas.workload_schema import WorkloadProfile
from app.services import (
    analysis_service,
    config_generator_service,
    constraint_service,
    estimation_service,
    prediction_service,
    recommendation_service,
    score_service,
)
from app.services.config_generator_service import ConfigGenerationError
from app.services.feature_service import extract_features
from app.services.optimized_iac_service import (
    OptimizedIaCError,
    OPTIMIZED_IAC_DISCLAIMER,
)
from app.services import optimized_iac_service
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


_HCL_SIGNATURE = re.compile(
    r'^\s*(resource|provider|terraform|variable|module|output|data|locals)\s+"',
    re.MULTILINE,
)


def _looks_like_terraform(upload_text: str) -> bool:
    return bool(_HCL_SIGNATURE.search(upload_text))


def _looks_like_compose(upload_text: str) -> bool:
    """Structural Compose detection: a top-level 'services:' mapping.

    Compose and Kubernetes share the .yaml/.yml extension, so the choice is
    made by content: 'services:' -> Compose, 'kind:' -> Kubernetes.
    """
    return bool(re.search(r"^services\s*:", upload_text, re.MULTILINE))


def _parse_upload(file: UploadFile, upload_text: str) -> InfrastructureConfiguration:
    """Detect the IaC format and parse with the matching parser.

    Order matters: .tf extensions or HCL signatures route to Terraform;
    then a top-level 'services:' mapping routes to the Compose parser
    (Compose and Kubernetes share the YAML extension, so this is decided
    by structure, not suffix); everything else falls through to the
    Kubernetes parser, preserving its existing error behavior.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".tf" or _looks_like_terraform(upload_text):
        try:
            parsed = parse_terraform(upload_text)
        except TerraformParserError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return InfrastructureConfiguration.model_validate(parsed)

    if _looks_like_compose(upload_text):
        try:
            parsed = parse_docker_compose(upload_text)
        except DockerComposeParserError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return InfrastructureConfiguration.model_validate(parsed)

    try:
        parsed = parse_kubernetes_yaml(upload_text)
    except KubernetesParserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return InfrastructureConfiguration.model_validate(parsed)


# Phase 18: the Phase 10 Kubernetes-only gate on optimized-config generation
# is gone — per-source dispatch below covers Kubernetes (Phase 10 rewrite),
# Terraform and Docker Compose (Phase 16 templates + round-trip validation).


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
    upload_text = _decode_upload(content)
    if Path(file.filename or "").suffix.lower() == ".tf" or _looks_like_terraform(upload_text):
        errors = validate_terraform(upload_text)
    elif _looks_like_compose(upload_text):
        errors = validate_docker_compose(upload_text)
    else:
        errors = validate_kubernetes_yaml(upload_text)
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
    configuration = _parse_upload(file, yaml_text)
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
        original_yaml=yaml_text,
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


@router.get(
    "/analysis/{analysis_id}/score",
    response_model=AnalysisScoreResponse,
)
def get_analysis_score(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisScoreResponse:
    """Compute the weighted sustainability score for a stored analysis.

    Methodology, component breakdown, and disclaimer are included so the
    dashboard never presents the score as an authoritative benchmark
    (design doc section 23).
    """
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

    configuration = analysis_service.to_configuration(record)
    workload = analysis_service.to_workload(record)
    estimation = estimation_service.estimate_sustainability(features, prediction)
    constraints = constraint_service.evaluate_constraints(features, prediction)

    score = score_service.compute_score(
        configuration=configuration,
        workload=workload,
        features=features,
        prediction=prediction,
        estimation=estimation,
        constraints=constraints,
    )
    return AnalysisScoreResponse(analysis_id=record.id, score=score)


@router.post(
    "/analysis/{analysis_id}/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_201_CREATED,
)
def optimize_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> OptimizeResponse:
    """Generate, evaluate, rank, and persist scale-down recommendations."""
    try:
        return recommendation_service.run_optimization(db, analysis_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        ) from None
    except (ModelArtifactsUnavailableError, ModelCompatibilityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get(
    "/analysis/{analysis_id}/recommendations",
    response_model=AnalysisRecommendationsResponse,
)
def get_analysis_recommendations(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisRecommendationsResponse:
    """Return the persisted recommendation set for one analysis."""
    try:
        stored = recommendation_service.get_recommendations(db, analysis_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        ) from None

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendations for analysis '{analysis_id}' not found; run optimize first",
        )

    return AnalysisRecommendationsResponse(
        analysis_id=stored.analysis_id,
        recommendation_set=stored.recommendation_set,
        scores=stored.scores,
    )


@router.get(
    "/analysis/{analysis_id}/optimized-config",
    response_model=OptimizedConfigResponse,
)
def get_optimized_config(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> OptimizedConfigResponse:
    """Generate the optimized IaC artifact from the stored recommendation.

    Phase 18: per-source dispatch. Kubernetes keeps the Phase 10
    manifest-preserving rewrite; Terraform and Docker Compose render
    through the Phase 16 templates with the same mandatory round-trip
    validation. The original upload is never modified in any path.
    """
    record = analysis_service.get_analysis(db, analysis_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        )

    try:
        stored = recommendation_service.get_recommendations(db, analysis_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        ) from None

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Recommendations for analysis '{analysis_id}' not found; "
                f"run optimize first"
            ),
        )

    if stored.recommendation_set.status.value != "recommended":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Analysis '{analysis_id}' has no accepted recommendation; "
                f"the current configuration is kept"
            ),
        )

    optimized_configuration = stored.recommendation_set.optimized_configuration
    if optimized_configuration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' has no optimized configuration stored",
        )

    optimized = InfrastructureConfiguration.model_validate(optimized_configuration)
    baseline = analysis_service.to_configuration(record)
    original_text = record.original_yaml or ""
    source_type = baseline.source_type

    disclaimer = (
        "The optimized manifest is a proposal generated from advisory "
        "estimates. The original configuration is preserved unchanged; "
        "review the diff and deploy manually only if you accept it."
    )

    if source_type == "kubernetes":
        try:
            generated = config_generator_service.generate_optimized_config(
                original_text, optimized, baseline
            )
        except ConfigGenerationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return OptimizedConfigResponse(
            analysis_id=record.id,
            source=generated_source(original_text),
            original_yaml=(
                original_text
                if original_text.strip()
                else generated_canonical_original(optimized)
            ),
            optimized_yaml=generated.optimized_yaml,
            diff=generated.diff_lines,
            changes=generated.changes,
            disclaimer=disclaimer,
        )

    # Phase 18: Terraform and Docker Compose via the Phase 16 templates.
    try:
        generated = optimized_iac_service.generate_optimized_iac(
            original_text, optimized, baseline, source_type
        )
    except OptimizedIaCError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return OptimizedConfigResponse(
        analysis_id=record.id,
        source=generated_source(original_text),
        original_yaml=original_text,
        optimized_yaml=generated.optimized_text,
        diff=generated.diff_lines,
        changes=[],
        notes=list(generated.notes),
        disclaimer=OPTIMIZED_IAC_DISCLAIMER,
    )


def generated_source(original_text: str) -> str:
    return "stored_original" if original_text.strip() else "canonical"


def generated_canonical_original(optimized: InfrastructureConfiguration) -> str:
    import yaml

    return yaml.dump(
        config_generator_service._rebuild_original_from_baseline_needed(optimized),
        sort_keys=False,
    )
