"""Engine/session for the BMI feature - a separate connection (and, in
production, a separate least-privilege role) from the rest of the app."""
import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from bmi_dashboard.models import SCHEMA

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def init_engine(url: str) -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    if url.startswith("sqlite"):
        # SQLite has no schemas: map "bmi" to none (tests only).
        _engine = create_engine(
            url, connect_args={"check_same_thread": False}, execution_options={"schema_translate_map": {SCHEMA: None}}
        )

        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _record):  # noqa: ANN001
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    else:
        _engine = create_engine(url, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_engine():
    if _engine is None:
        raise RuntimeError("BMI database engine is not initialised")
    return _engine


def get_session():
    """FastAPI dependency: one session per request, rolled back on error."""
    if _session_factory is None:
        raise RuntimeError("BMI database engine is not initialised")
    session: Session = _session_factory()
    try:
        yield session
    finally:
        session.close()
