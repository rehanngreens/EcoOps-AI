import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.analysis import Analysis

get_settings.cache_clear()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = PROJECT_ROOT / "infrastructure" / "kubernetes"

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_analyses() -> None:
    with SessionLocal() as session:
        session.query(Analysis).delete()
        session.commit()
    yield


def load_manifest(name: str) -> str:
    return (MANIFESTS_DIR / name).read_text(encoding="utf-8")
