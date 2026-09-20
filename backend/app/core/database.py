from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

if settings.database_url.startswith("sqlite"):
    # In-memory SQLite must share ONE connection (StaticPool): every new
    # connection would otherwise see its own empty database. File-backed
    # SQLite must NOT share one connection — concurrent requests interleave
    # statements on a single connection and commit fails with "cannot commit
    # transaction - SQL statements in progress" (found by the Phase 19
    # concurrency test). Pooled per-checkout connections + sqlite's busy
    # timeout serialize writers correctly instead.
    connect_args = {"check_same_thread": False, "timeout": 30}
    if ":memory:" in settings.database_url:
        engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(settings.database_url, connect_args=connect_args)
else:
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
