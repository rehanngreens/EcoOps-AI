import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.analysis import Analysis
from app.models.generation import GenerationRecord
from app.models.recommendation import RecommendationItemRecord, RecommendationSetRecord

get_settings.cache_clear()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = PROJECT_ROOT / "infrastructure" / "kubernetes"
TERRAFORM_DIR = PROJECT_ROOT / "infrastructure" / "terraform"
COMPOSE_DIR = PROJECT_ROOT / "infrastructure" / "docker"

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables() -> None:
    with SessionLocal() as session:
        session.query(RecommendationItemRecord).delete()
        session.query(RecommendationSetRecord).delete()
        session.query(GenerationRecord).delete()
        session.query(Analysis).delete()
        session.commit()
    yield


def load_manifest(name: str) -> str:
    return (MANIFESTS_DIR / name).read_text(encoding="utf-8")


def load_terraform(name: str) -> str:
    return (TERRAFORM_DIR / name).read_text(encoding="utf-8")


def load_compose(name: str) -> str:
    return (COMPOSE_DIR / name).read_text(encoding="utf-8")
