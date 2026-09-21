"""Test fixtures.

The app reads DATABASE_URL / REDIS_URL at import time, so they are set here
*before* anything imports `main`. Tests run against a throwaway SQLite file
and an in-memory fake Redis, so they need no running services.
"""
import os
import tempfile

_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["REDIS_URL"] = "redis://unused:6379/0"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, _ttl, value):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture()
def client(monkeypatch):
    import main

    fake = FakeRedis()
    monkeypatch.setattr(main, "redis_client", fake)
    with TestClient(main.app) as c:
        c.fake_redis = fake
        yield c
