"""Real-PostgreSQL tests: migrations, isolation from other tables, least privilege.

Skipped unless TEST_PG_ADMIN_URL points at a throwaway server, e.g.
  TEST_PG_ADMIN_URL=postgresql+psycopg://postgres:secret@localhost:5432/postgres
(needs the `psql` client, because the real provisioning SQL uses \\getenv).
Everything is created in uniquely named databases/roles and removed afterwards.
"""
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, ProgrammingError

ADMIN_URL = os.environ.get("TEST_PG_ADMIN_URL")
pytestmark = [
    pytest.mark.skipif(not ADMIN_URL, reason="TEST_PG_ADMIN_URL not set"),
    pytest.mark.skipif(shutil.which("psql") is None, reason="psql client not installed"),
]

SQL_FILE = Path(__file__).resolve().parents[3] / "scripts" / "sql" / "bmi_provision.sql"


def _admin(dbname: str | None = None):
    url = make_url(ADMIN_URL)
    return create_engine(url.set(database=dbname) if dbname else url, isolation_level="AUTOCOMMIT")


def _provision(dbname: str, role: str, password: str) -> subprocess.CompletedProcess:
    url = make_url(ADMIN_URL)
    env = {**os.environ, "PGPASSWORD": url.password or "", "BMI_DB_USER": role, "BMI_DB_PASSWORD": password}
    return subprocess.run(
        ["psql", "-h", url.host, "-p", str(url.port or 5432), "-U", url.username, "-d", dbname, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(SQL_FILE)],
        env=env, capture_output=True, text=True,
    )


def _bmi_url(dbname: str, role: str, password: str) -> str:
    return make_url(ADMIN_URL).set(database=dbname, username=role, password=password).render_as_string(hide_password=False)


def snapshot_public(engine) -> dict:
    """Everything observable about schema public: objects, columns, indexes and a hash of every row."""
    snap = {}
    with engine.connect() as c:
        snap["objects"] = [tuple(r) for r in c.execute(text(
            "SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2"))]
        snap["columns"] = [tuple(r) for r in c.execute(text(
            "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY 1, ordinal_position"))]
        snap["indexes"] = [tuple(r) for r in c.execute(text("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2"))]
        for (table,) in list(c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"))):
            snap[f"rows:{table}"] = tuple(c.execute(text(f'SELECT count(*), md5(coalesce(string_agg(t::text, \',\' ORDER BY t::text), \'\')) FROM public."{table}" t')).one())
    return snap


@pytest.fixture(scope="module")
def pg():
    tag = secrets.token_hex(4)
    db, role, password = f"bmi_it_{tag}", f"bmi_it_{tag}", secrets.token_hex(16)
    admin = _admin()
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{db}"'))
    dbadmin = _admin(db)
    with dbadmin.connect() as c:  # stand-ins for the production tables that must never be touched
        c.execute(text("CREATE TABLE public.items (id serial PRIMARY KEY, name varchar(255) NOT NULL, description varchar(1000), created_at timestamptz DEFAULT now())"))
        c.execute(text("CREATE TABLE public.invoice_audit_log (id bigserial PRIMARY KEY, vendor_name text, total_amount numeric, created_at timestamptz DEFAULT now())"))
        c.execute(text("INSERT INTO public.items(name) VALUES ('keep me'), ('and me')"))
        c.execute(text("INSERT INTO public.invoice_audit_log(vendor_name, total_amount) VALUES ('ACME', 12.50), ('Globex', 99)"))
    before = snapshot_public(dbadmin)
    done = _provision(db, role, password)
    assert done.returncode == 0, done.stderr
    yield {"db": db, "role": role, "password": password, "url": _bmi_url(db, role, password), "admin": dbadmin, "before": before, "tag": tag}
    dbadmin.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
        c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
    admin.dispose()


def test_provisioned_role_is_least_privilege(pg):
    with pg["admin"].connect() as c:
        attrs = c.execute(text("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=:r"), {"r": pg["role"]}).one()
        assert tuple(attrs) == (False, False, False, False, False, 10)
        assert c.execute(text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='bmi'")).scalar() == pg["role"]
        assert c.execute(text("SELECT has_schema_privilege(:r,'public','CREATE')"), {"r": pg["role"]}).scalar() is False
        readable = c.execute(text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','v','m','p') "
            "AND (has_table_privilege(:r,c.oid,'SELECT') OR has_table_privilege(:r,c.oid,'INSERT') OR has_table_privilege(:r,c.oid,'UPDATE') OR has_table_privilege(:r,c.oid,'DELETE'))"),
            {"r": pg["role"]}).scalar()
        assert readable == 0


def test_provisioning_is_idempotent(pg):
    again = _provision(pg["db"], pg["role"], pg["password"])
    assert again.returncode == 0, again.stderr


def test_provisioning_rejects_weak_password_and_bad_role_name(pg):
    assert _provision(pg["db"], pg["role"], "short").returncode != 0
    assert _provision(pg["db"], "Bad-Role; DROP TABLE x", secrets.token_hex(16)).returncode != 0


def test_provisioning_refuses_a_schema_owned_by_someone_else(pg):
    tag = secrets.token_hex(3)
    db = f"bmi_it_other_{tag}"
    with _admin().connect() as c:
        c.execute(text(f'CREATE DATABASE "{db}"'))
    try:
        with _admin(db).connect() as c:
            c.execute(text("CREATE SCHEMA bmi"))  # owned by the admin, not by the BMI role
        done = _provision(db, f"bmi_it_o{tag}", secrets.token_hex(16))
        assert done.returncode != 0 and "owned by a different role" in done.stderr
    finally:
        with _admin().connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
            c.execute(text(f'DROP ROLE IF EXISTS "bmi_it_o{tag}"'))


def test_migration_without_provisioning_fails_with_an_actionable_message(pg):
    from bmi_dashboard.migrations import run_migrations

    db = f"bmi_it_bare_{pg['tag']}"
    with _admin().connect() as c:
        c.execute(text(f'CREATE DATABASE "{db}"'))
    try:
        with pytest.raises(RuntimeError, match="provision"):
            run_migrations(_bmi_url(db, pg["role"], pg["password"]))
    finally:
        with _admin().connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))


def test_migrating_creates_bmi_tables_and_leaves_public_byte_for_byte_unchanged(pg):
    from bmi_dashboard.migrations import run_migrations

    run_migrations(pg["url"])
    with pg["admin"].connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='bmi'"))}
        assert tables == {"profiles", "weight_entries", "goals", "alembic_version"}
        assert c.execute(text("SELECT version_num FROM bmi.alembic_version")).scalar() == "0001"
        assert c.execute(text("SELECT count(*) FROM pg_tables WHERE tablename='alembic_version' AND schemaname='public'")).scalar() == 0
    assert snapshot_public(pg["admin"]) == pg["before"]  # objects, columns, indexes AND every row hash


def test_migrating_twice_is_a_no_op(pg):
    from bmi_dashboard.migrations import run_migrations

    run_migrations(pg["url"])
    run_migrations(pg["url"])
    assert snapshot_public(pg["admin"]) == pg["before"]


def test_role_cannot_read_write_or_create_in_public(pg):
    engine = create_engine(pg["url"])
    try:
        for statement in ("SELECT * FROM public.items", "SELECT * FROM public.invoice_audit_log", "INSERT INTO public.items(name) VALUES ('x')",
                          "DELETE FROM public.items", "UPDATE public.items SET name='x'", "DROP TABLE public.items",
                          "CREATE TABLE public.sneaky (id int)", "ALTER TABLE public.items ADD COLUMN x int", "TRUNCATE public.invoice_audit_log"):
            with engine.connect() as c, pytest.raises(ProgrammingError):
                c.execute(text(statement))
        with engine.connect() as c:  # ...but its own schema works
            assert c.execute(text("SELECT count(*) FROM bmi.profiles")).scalar() == 0
            assert c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")).scalar() is False
    finally:
        engine.dispose()
    assert snapshot_public(pg["admin"]) == pg["before"]


def test_database_constraints_are_enforced(pg):
    engine = create_engine(pg["url"])
    try:
        def profile(c, subject="t", age=30, sex="male", height=170, level="sedentary"):
            return c.execute(text("INSERT INTO bmi.profiles(subject,age_years,sex,height_cm,activity_level) VALUES (:s,:a,:x,:h,:l) RETURNING id"),
                             {"s": subject, "a": age, "x": sex, "h": height, "l": level}).scalar()

        for kwargs in ({"age": 17}, {"age": 101}, {"sex": "other"}, {"height": 99}, {"height": 251}, {"level": "athlete"}):
            with engine.begin() as c, pytest.raises(IntegrityError):
                profile(c, subject=f"bad-{kwargs}", **kwargs)
        with engine.begin() as c:
            pid = profile(c, subject="ok")
            c.execute(text("INSERT INTO bmi.weight_entries(profile_id,recorded_on,weight_kg,height_cm) VALUES (:p,'2026-09-01',75,170)"), {"p": pid})
            c.execute(text("INSERT INTO bmi.goals(profile_id,target_weight_kg,starting_weight_kg,started_on) VALUES (:p,70,75,'2026-09-01')"), {"p": pid})
        with engine.begin() as c, pytest.raises(IntegrityError):   # one entry per day
            c.execute(text("INSERT INTO bmi.weight_entries(profile_id,recorded_on,weight_kg,height_cm) VALUES (:p,'2026-09-01',74,170)"), {"p": pid})
        with engine.begin() as c, pytest.raises(IntegrityError):   # one goal per profile
            c.execute(text("INSERT INTO bmi.goals(profile_id,target_weight_kg,starting_weight_kg,started_on) VALUES (:p,60,75,'2026-09-01')"), {"p": pid})
        for weight in (19, 401):
            with engine.begin() as c, pytest.raises(IntegrityError):
                c.execute(text("INSERT INTO bmi.weight_entries(profile_id,recorded_on,weight_kg,height_cm) VALUES (:p,'2026-09-02',:w,170)"), {"p": pid, "w": weight})
        with engine.begin() as c, pytest.raises(IntegrityError):   # calorie target range
            c.execute(text("UPDATE bmi.goals SET daily_calorie_target=100 WHERE profile_id=:p"), {"p": pid})
        with engine.begin() as c, pytest.raises(IntegrityError):   # foreign key
            c.execute(text("INSERT INTO bmi.weight_entries(profile_id,recorded_on,weight_kg,height_cm) VALUES (999999,'2026-09-03',70,170)"))
        with engine.begin() as c:                                   # cascade
            c.execute(text("DELETE FROM bmi.profiles WHERE id=:p"), {"p": pid})
            assert c.execute(text("SELECT (SELECT count(*) FROM bmi.weight_entries)+(SELECT count(*) FROM bmi.goals)")).scalar() == 0
    finally:
        engine.dispose()


def test_models_and_migration_have_not_drifted(pg):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from bmi_dashboard.migrations import run_migrations
    from bmi_dashboard.models import SCHEMA, Base

    run_migrations(pg["url"])  # independent of test order
    # Compare over an ADMIN connection (search_path=public): `bmi` is then an ordinary named schema.
    with pg["admin"].connect() as conn:
        ctx = MigrationContext.configure(conn, opts={
            "target_metadata": Base.metadata, "version_table_schema": SCHEMA, "include_schemas": True, "compare_type": True,
            "include_name": lambda name, type_, parent: name == SCHEMA if type_ == "schema" else True,
            "include_object": lambda obj, name, type_, reflected, compare_to: obj.schema == SCHEMA if type_ == "table" else True,
        })
        diff = compare_metadata(ctx, Base.metadata)
        assert diff == [], f"models and migrations differ: {diff}"


def test_full_api_flow_on_real_postgres(pg, monkeypatch):
    from conftest import TEST_PASSWORD, FakeRedis
    from fastapi.testclient import TestClient

    import main
    import redis_client as redis_module
    from bmi_dashboard.config import bmi_settings

    monkeypatch.setattr(bmi_settings, "bmi_database_url", pg["url"])
    monkeypatch.setattr(redis_module, "redis_client", FakeRedis())
    with TestClient(main.app) as c:  # lifespan runs the (already applied) migrations against Postgres
        assert c.post("/auth/login", json={"password": TEST_PASSWORD}).status_code == 200
        assert c.post("/profile", json={"age_years": 34, "sex": "male", "height_cm": 168, "weight_kg": 75, "activity_level": "moderately_active", "recorded_on": "2026-09-01"}).status_code == 201
        first = c.post("/health/weight", json={"weight_kg": 74.5, "recorded_on": "2026-09-05"})
        again = c.post("/health/weight", json={"weight_kg": 74.0, "recorded_on": "2026-09-05"})
        assert (first.status_code, again.status_code, first.json()["id"] == again.json()["id"]) == (201, 200, True)
        s = c.get("/health/summary").json()
        assert s["metrics"]["bmi"] == 26.2 and s["latest_weight"]["weight_kg"] == 74.0
        assert c.post("/goals", json={"target_weight_kg": 70, "starting_weight_kg": 75}).status_code == 201
        assert c.get("/goals").json()["progress"]["progress_percent"] == 20.0  # (75-74)/(75-70)
        assert [m["month"] for m in c.get("/health/monthly").json()["months"]] == ["2026-09"]
        entry_id = c.get("/health/history").json()["entries"][-1]["id"]
        assert c.delete(f"/health/weight/{entry_id}").status_code == 204
    assert snapshot_public(pg["admin"]) == pg["before"]  # the whole app flow never touched public


def test_downgrade_removes_only_bmi_objects(pg):
    from alembic import command

    from bmi_dashboard.migrations import alembic_config, run_migrations

    command.downgrade(alembic_config(pg["url"]), "base")
    with pg["admin"].connect() as c:
        left = {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='bmi'"))}
    assert left == {"alembic_version"}
    assert snapshot_public(pg["admin"]) == pg["before"]
    run_migrations(pg["url"])  # and it comes back
