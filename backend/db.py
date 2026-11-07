"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _record) -> None:  # noqa: ANN001
            connection.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def configure(url: str) -> Engine:
    """Point the app at another database. Used by tests and CLI tools."""
    global engine
    engine = build_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    with SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit on success, roll back on any error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
