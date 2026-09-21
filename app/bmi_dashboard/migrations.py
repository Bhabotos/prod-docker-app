"""Run Alembic migrations programmatically at application start."""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from bmi_dashboard.models import SCHEMA

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(APP_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(APP_DIR / "db_migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _check_schema_ready(url: str) -> None:
    """Fail early with an actionable message instead of a cryptic permission error."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            owner = conn.execute(
                text("SELECT schema_owner FROM information_schema.schemata WHERE schema_name = :s"), {"s": SCHEMA}
            ).scalar()
            if owner is None:
                raise RuntimeError(
                    f"schema '{SCHEMA}' does not exist. Provision the database role and schema first "
                    "(scripts/provision_bmi_db.sh --apply)."
                )
            if not conn.execute(text("SELECT has_schema_privilege(current_user, :s, 'CREATE')"), {"s": SCHEMA}).scalar():
                raise RuntimeError(f"role lacks CREATE on schema '{SCHEMA}' (owner is '{owner}')")
    finally:
        engine.dispose()


def run_migrations(url: str) -> None:
    _check_schema_ready(url)
    logger.info("Running BMI migrations (additive, schema '%s' only)", SCHEMA)
    command.upgrade(alembic_config(url), "head")
