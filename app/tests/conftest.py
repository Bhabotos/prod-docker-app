"""Test fixtures.

The app reads DATABASE_URL / REDIS_URL / BMI_* at import time, so they are set
here *before* anything imports `main`. Tests run against throwaway SQLite files
and an in-memory fake Redis, so they need no running services. (Real-PostgreSQL
tests live in tests/integration and are skipped unless TEST_PG_ADMIN_URL is set.)
"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["REDIS_URL"] = "redis://unused:6379/0"
os.environ["LOG_LEVEL"] = "WARNING"

from bmi_dashboard.security import hash_password  # noqa: E402  (stdlib only, safe before env is set)

TEST_PASSWORD = "correct horse battery staple"
os.environ["BMI_DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'bmi.db')}"
os.environ["DASHBOARD_PASSWORD_HASH"] = hash_password(TEST_PASSWORD, n=2**10)  # cheap params: tests only
os.environ["SESSION_SECRET"] = "test-session-secret-0123456789-abcdefghij"
os.environ["COOKIE_SECURE"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.store, self.ttls = {}, {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, _ttl, value):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)
        self.ttls.pop(key, None)

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def ttl(self, key):
        return self.ttls.get(key, -1)


@pytest.fixture()
def client(monkeypatch):
    import main
    import redis_client as redis_module
    from bmi_dashboard import db, deps
    from bmi_dashboard.models import Base

    fake = FakeRedis()
    monkeypatch.setattr(main, "redis_client", fake)  # items cache
    monkeypatch.setattr(redis_module, "redis_client", fake)  # login rate limiter
    deps._limiter._memory.clear()
    with TestClient(main.app) as c:
        Base.metadata.drop_all(db.get_engine())  # fresh BMI tables for every test
        Base.metadata.create_all(db.get_engine())
        c.fake_redis = fake
        yield c


@pytest.fixture()
def auth_client(client):
    r = client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def profile_client(auth_client):
    """Authenticated client with a profile (34y male, 168 cm, 75 kg on 2026-09-01)."""
    r = auth_client.post(
        "/profile",
        json={"age_years": 34, "sex": "male", "height_cm": 168, "weight_kg": 75, "activity_level": "moderately_active", "recorded_on": "2026-09-01"},
    )
    assert r.status_code == 201, r.text
    return auth_client
