"""Alembic environment for the BMI schema.

Hard rules enforced here:
  * only the `bmi` schema is ever considered (include_name/include_object);
  * the version table lives in `bmi`, never in `public`;
  * one advisory lock serialises concurrent starts;
  * online mode only - the URL is supplied at runtime, never written to disk.
"""
from alembic import context
from sqlalchemy import create_engine, pool, text

from bmi_dashboard.models import SCHEMA, Base

config = context.config
target_metadata = Base.metadata
ADVISORY_LOCK_KEY = 727_001


# Strict on purpose: only the `bmi` schema is ever considered.
# NOTE for `alembic revision --autogenerate`: run it over an ADMIN connection. The BMI role has
# search_path = bmi, which makes Alembic treat `bmi` as the default schema and report false diffs
# (tests/integration/test_postgres_migrations.py::test_models_and_migration_have_not_drifted does this).
def include_name(name, type_, parent_names):  # noqa: ANN001
    return name == SCHEMA if type_ == "schema" else True


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001
    if type_ == "table":
        return obj.schema == SCHEMA
    return True


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=SCHEMA,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            connection.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": ADVISORY_LOCK_KEY})
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported")
run_migrations_online()
