"""Guards against forgetting authentication on a new route."""
import pytest
from fastapi.routing import APIRoute

# Routes that are public ON PURPOSE. A new route must be added here deliberately.
PUBLIC = {
    ("GET", "/"), ("GET", "/health"),
    ("POST", "/items"), ("GET", "/items"), ("GET", "/items/{item_id}"), ("PUT", "/items/{item_id}"), ("DELETE", "/items/{item_id}"),
    ("POST", "/auth/login"), ("POST", "/auth/logout"),
}


def _routes():
    import main

    for r in main.app.routes:
        if isinstance(r, APIRoute):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                yield m, r.path


def test_every_non_public_route_rejects_anonymous_requests(client):
    checked = 0
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        url = path.replace("{entry_id}", "1")
        r = client.request(method, url, json={} if method in {"POST", "PUT"} else None)
        assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a session"
        checked += 1
    # profile 3 + health 6 (limits, summary, history, monthly, weight POST/DELETE) + goals 3 + auth/me 1.
    # Exact on purpose: fails if a route silently vanishes OR a new one appears without being reviewed here.
    assert checked == 13


def test_route_inventory_is_what_we_expect():
    have = set(_routes())
    for expected in [
        ("GET", "/profile"), ("POST", "/profile"), ("PUT", "/profile"),
        ("GET", "/health/summary"), ("GET", "/health/history"), ("GET", "/health/monthly"), ("GET", "/health/limits"),
        ("POST", "/health/weight"), ("DELETE", "/health/weight/{entry_id}"),
        ("GET", "/goals"), ("POST", "/goals"), ("PUT", "/goals"), ("GET", "/auth/me"),
    ]:
        assert expected in have, expected


def test_feature_is_disabled_cleanly_when_not_configured(client, monkeypatch):
    from bmi_dashboard.config import bmi_settings

    monkeypatch.setattr(bmi_settings, "session_secret", "")
    assert bmi_settings.missing() == ["SESSION_SECRET (min 32 chars)"]
    for method, path in (("POST", "/auth/login"), ("GET", "/profile"), ("GET", "/health/summary")):
        r = client.request(method, path, json={"password": "x"} if method == "POST" else None)
        assert r.status_code == 503, (method, path)
    assert client.get("/health").json() == {"status": "ok"}  # the rest of the app is unaffected


@pytest.mark.parametrize("gap", ["dashboard_password_hash", "bmi_database_url"])
def test_any_missing_setting_disables_the_feature(monkeypatch, gap):
    from bmi_dashboard.config import bmi_settings

    monkeypatch.setattr(bmi_settings, gap, "")
    assert bmi_settings.enabled is False and bmi_settings.missing()
