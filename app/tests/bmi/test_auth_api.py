from conftest import TEST_PASSWORD

from bmi_dashboard.config import bmi_settings


def test_protected_routes_need_a_session(client):
    for path in ("/profile", "/health/summary", "/health/history", "/goals", "/auth/me"):
        r = client.get(path)
        assert r.status_code == 401, path
        assert r.json() == {"detail": "Not authenticated."}


def test_wrong_password_gives_a_generic_error(client):
    r = client.post("/auth/login", json={"password": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect password."
    assert "set-cookie" not in r.headers


def test_login_sets_a_hardened_cookie_and_me_works(client, monkeypatch):
    monkeypatch.setattr(bmi_settings, "cookie_secure", True)
    r = client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
    assert TEST_PASSWORD not in r.text and TEST_PASSWORD not in cookie
    assert "bmi_session=" in r.headers["set-cookie"]


def test_session_grants_access_and_logout_revokes_it(auth_client):
    assert auth_client.get("/auth/me").json() == {"authenticated": True}
    assert auth_client.post("/auth/logout").status_code == 200
    assert auth_client.get("/auth/me").status_code == 401


def test_tampered_cookie_is_rejected(client):
    client.cookies.set("bmi_session", "forged.token")
    assert client.get("/auth/me").status_code == 401


def test_brute_force_is_throttled_even_for_the_right_password(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"password": "bad"}).status_code == 401
    blocked = client.post("/auth/login", json={"password": "bad"})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    assert client.post("/auth/login", json={"password": TEST_PASSWORD}).status_code == 429


def test_successful_login_clears_the_failure_counter(client):
    for _ in range(4):
        client.post("/auth/login", json={"password": "bad"})
    assert client.post("/auth/login", json={"password": TEST_PASSWORD}).status_code == 200
    assert client.post("/auth/login", json={"password": "bad"}).status_code == 401  # counter restarted


def test_cross_origin_writes_are_rejected(auth_client):
    r = auth_client.post("/auth/login", json={"password": TEST_PASSWORD}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = auth_client.post("/profile", json={}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    same = auth_client.post("/auth/logout", headers={"Origin": "http://testserver"})
    assert same.status_code == 200


def test_responses_are_never_cacheable(profile_client):
    for path in ("/profile", "/health/summary", "/health/history", "/health/limits"):
        assert profile_client.get(path).headers["cache-control"] == "no-store", path


def test_login_body_is_validated(client):
    assert client.post("/auth/login", json={}).status_code == 422
    assert client.post("/auth/login", json={"password": ""}).status_code == 422
    assert client.post("/auth/login", json={"password": "x", "extra": 1}).status_code == 422
