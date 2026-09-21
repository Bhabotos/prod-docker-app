def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_reports_service_and_env(client):
    body = client.get("/").json()
    assert "service" in body and "env" in body


def test_item_crud_roundtrip(client):
    created = client.post("/items", json={"name": "widget", "description": "d"})
    assert created.status_code == 201
    item_id = created.json()["id"]

    assert client.get(f"/items/{item_id}").json()["name"] == "widget"

    updated = client.put(f"/items/{item_id}", json={"name": "gadget", "description": None})
    assert updated.status_code == 200
    assert updated.json()["name"] == "gadget"

    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404


def test_read_uses_cache_then_update_invalidates(client):
    item_id = client.post("/items", json={"name": "cached"}).json()["id"]

    first = client.get(f"/items/{item_id}")
    second = client.get(f"/items/{item_id}")
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"

    client.put(f"/items/{item_id}", json={"name": "fresh"})
    third = client.get(f"/items/{item_id}")
    assert third.headers["X-Cache"] == "MISS"
    assert third.json()["name"] == "fresh"


def test_missing_item_404_and_validation_422(client):
    assert client.get("/items/999999").status_code == 404
    assert client.put("/items/999999", json={"name": "x"}).status_code == 404
    assert client.delete("/items/999999").status_code == 404
    assert client.post("/items", json={}).status_code == 422


def test_list_items(client):
    client.post("/items", json={"name": "a"})
    assert isinstance(client.get("/items").json(), list)
