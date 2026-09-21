"""End-to-end API flow (authenticated), against SQLite."""


def test_profile_lifecycle(auth_client):
    assert auth_client.get("/profile").status_code == 404  # not set up yet

    made = auth_client.post(
        "/profile", json={"age_years": 34, "sex": "male", "height_cm": 168, "weight_kg": 75, "recorded_on": "2026-09-01"}
    )
    assert made.status_code == 201
    assert made.json()["activity_level"] == "sedentary"

    hist = auth_client.get("/health/history").json()
    assert hist["count"] == 1 and hist["entries"][0]["weight_kg"] == 75  # profile creation recorded the first weight

    assert auth_client.post("/profile", json={"age_years": 30, "sex": "female", "height_cm": 160, "weight_kg": 60}).status_code == 409

    upd = auth_client.put("/profile", json={"age_years": 35, "sex": "male", "height_cm": 169, "activity_level": "very_active"})
    assert upd.status_code == 200 and upd.json()["age_years"] == 35 and upd.json()["height_cm"] == 169
    assert auth_client.get("/profile").json()["activity_level"] == "very_active"


def test_profile_validation_messages_are_clear(auth_client):
    r = auth_client.post("/profile", json={"age_years": 17, "sex": "male", "height_cm": 168, "weight_kg": 75})
    assert r.status_code == 422
    (err,) = r.json()["detail"]
    assert err["loc"][-1] == "age_years" and "Age must be between 18 and 100" in err["msg"]
    assert auth_client.get("/profile").status_code == 404  # nothing was stored


def test_summary_metrics_match_the_formulas(profile_client):
    s = profile_client.get("/health/summary").json()
    m = s["metrics"]
    assert (m["bmi"], m["bmi_category"], m["bmi_category_label"]) == (26.6, "overweight", "Overweight")
    assert (m["bmr_kcal"], m["daily_calories_kcal"], m["activity_factor"]) == (1635, 2534, 1.55)
    assert s["latest_weight"]["weight_kg"] == 75
    assert s["goal"] is None
    assert "not medical advice" in s["disclaimer"]
    assert s["formulas"]["bmr"] == "Mifflin-St Jeor"


def test_summary_without_any_weight_history(profile_client):
    entry_id = profile_client.get("/health/history").json()["entries"][0]["id"]
    assert profile_client.delete(f"/health/weight/{entry_id}").status_code == 204
    s = profile_client.get("/health/summary").json()
    assert s["metrics"] is None and s["latest_weight"] is None and s["profile"]["age_years"] == 34


def test_one_entry_per_day_updates_instead_of_duplicating(profile_client):
    first = profile_client.post("/health/weight", json={"weight_kg": 74.5, "recorded_on": "2026-09-05", "note": "morning"})
    assert first.status_code == 201
    again = profile_client.post("/health/weight", json={"weight_kg": 74.0, "recorded_on": "2026-09-05"})
    assert again.status_code == 200                       # updated, not created
    assert again.json()["id"] == first.json()["id"] and again.json()["weight_kg"] == 74.0 and again.json()["note"] is None
    dates = [e["recorded_on"] for e in profile_client.get("/health/history").json()["entries"]]
    assert dates == ["2026-09-01", "2026-09-05"]          # no duplicate for 09-05


def test_history_is_ordered_filtered_and_carries_bmi(profile_client):
    for day, kg in (("2026-09-10", 74), ("2026-09-20", 73.2), ("2026-08-15", 77)):
        assert profile_client.post("/health/weight", json={"weight_kg": kg, "recorded_on": day}).status_code == 201
    h = profile_client.get("/health/history").json()
    assert [e["recorded_on"] for e in h["entries"]] == ["2026-08-15", "2026-09-01", "2026-09-10", "2026-09-20"]
    assert h["entries"][0]["bmi"] == 27.3 and h["entries"][0]["bmi_category"] == "overweight"
    assert [b["category"] for b in h["bmi_bands"]] == ["underweight", "normal", "overweight", "obesity"]
    part = profile_client.get("/health/history", params={"from": "2026-09-01", "to": "2026-09-10"}).json()
    assert [e["recorded_on"] for e in part["entries"]] == ["2026-09-01", "2026-09-10"]
    last2 = profile_client.get("/health/history", params={"limit": 2}).json()
    assert [e["recorded_on"] for e in last2["entries"]] == ["2026-09-10", "2026-09-20"]  # most recent kept, oldest first
    assert profile_client.get("/health/history", params={"from": "2026-09-10", "to": "2026-09-01"}).status_code == 422
    assert profile_client.get("/health/history", params={"limit": 0}).status_code == 422


def test_bmi_history_uses_the_height_at_recording_time(profile_client):
    before = profile_client.get("/health/history").json()["entries"][0]["bmi"]
    profile_client.put("/profile", json={"age_years": 34, "sex": "male", "height_cm": 190, "activity_level": "sedentary"})
    assert profile_client.get("/health/history").json()["entries"][0]["bmi"] == before  # old point unchanged
    profile_client.post("/health/weight", json={"weight_kg": 75, "recorded_on": "2026-09-02"})
    new = profile_client.get("/health/history").json()["entries"][-1]
    assert new["height_cm"] == 190 and new["bmi"] == 20.8


def test_delete_weight(profile_client):
    e = profile_client.post("/health/weight", json={"weight_kg": 70, "recorded_on": "2026-09-03"}).json()
    assert profile_client.delete(f"/health/weight/{e['id']}").status_code == 204
    assert profile_client.delete(f"/health/weight/{e['id']}").status_code == 404
    assert profile_client.delete("/health/weight/99999").status_code == 404
    assert profile_client.delete("/health/weight/not-a-number").status_code == 422


def test_weight_validation(profile_client):
    for body in ({"weight_kg": 19}, {"weight_kg": 401}, {"weight_kg": "abc"}, {"weight_kg": 70, "recorded_on": "2999-01-01"},
                 {"weight_kg": 70, "recorded_on": "not-a-date"}, {"weight_kg": 70, "note": "x" * 201}, {}):
        assert profile_client.post("/health/weight", json=body).status_code == 422, body


def test_monthly_progress(profile_client):
    for day, kg in (("2026-08-03", 78), ("2026-08-29", 76.5), ("2026-09-20", 75.0)):
        profile_client.post("/health/weight", json={"weight_kg": kg, "recorded_on": day})
    months = {m["month"]: m for m in profile_client.get("/health/monthly", params={"months": 24}).json()["months"]}
    assert months["2026-08"]["change_kg"] == -1.5 and months["2026-08"]["entries"] == 2
    assert months["2026-09"]["first_weight_kg"] == 75.0  # 09-01 (75) and 09-20 (75)
    assert profile_client.get("/health/monthly", params={"months": 0}).status_code == 422


def test_goal_lifecycle_and_progress(profile_client):
    assert profile_client.get("/goals").status_code == 404
    g = profile_client.post("/goals", json={"target_weight_kg": 70, "daily_calorie_target": 2200})
    assert g.status_code == 201
    body = g.json()
    assert body["starting_weight_kg"] == 75 and body["daily_calorie_requirement"] == 2534 and body["daily_calorie_target"] == 2200
    assert body["progress"]["status"] == "in_progress" and body["progress"]["progress_percent"] == 0.0
    assert profile_client.post("/goals", json={"target_weight_kg": 65}).status_code == 409

    profile_client.post("/health/weight", json={"weight_kg": 72.5, "recorded_on": "2026-09-15"})
    g = profile_client.get("/goals").json()
    assert g["current_weight_kg"] == 72.5 and g["progress"]["progress_percent"] == 50.0 and g["progress"]["remaining_kg"] == 2.5
    assert profile_client.get("/health/summary").json()["goal"]["progress"]["progress_percent"] == 50.0

    profile_client.post("/health/weight", json={"weight_kg": 76, "recorded_on": "2026-09-18"})
    behind = profile_client.get("/goals").json()["progress"]
    assert behind["status"] == "behind" and behind["progress_percent"] == 0.0 and behind["raw_progress_percent"] < 0

    upd = profile_client.put("/goals", json={"target_weight_kg": 72, "restart_progress": True})
    assert upd.status_code == 200 and upd.json()["starting_weight_kg"] == 76 and upd.json()["daily_calorie_target"] is None


def test_goal_edge_cases_and_warnings(profile_client):
    same = profile_client.post("/goals", json={"target_weight_kg": 75}).json()
    assert same["progress"]["status"] == "target_equals_start" and same["progress"]["progress_percent"] is None
    low = profile_client.put("/goals", json={"target_weight_kg": 45}).json()
    assert low["warnings"] and "does not recommend" in low["warnings"][0]
    assert profile_client.put("/goals", json={"target_weight_kg": 19}).status_code == 422
    assert profile_client.put("/goals", json={"target_weight_kg": 70, "daily_calorie_target": 100}).status_code == 422


def test_goal_requires_profile_and_put_requires_goal(auth_client):
    assert auth_client.post("/goals", json={"target_weight_kg": 70}).status_code == 404  # no profile yet
    auth_client.post("/profile", json={"age_years": 34, "sex": "female", "height_cm": 165, "weight_kg": 60})
    assert auth_client.put("/goals", json={"target_weight_kg": 58}).status_code == 404


def test_limits_endpoint_feeds_the_forms(profile_client):
    lim = profile_client.get("/health/limits").json()
    assert lim["age"] == {"min": 18, "max": 100} and lim["sexes"] == [{"value": "male", "label": "Male"}, {"value": "female", "label": "Female"}]
    assert [a["value"] for a in lim["activity_levels"]] == ["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]
    assert lim["activity_levels"][0]["factor"] == 1.2


def test_female_bmr_path(auth_client):
    auth_client.post("/profile", json={"age_years": 34, "sex": "female", "height_cm": 168, "weight_kg": 75, "recorded_on": "2026-09-01"})
    assert auth_client.get("/health/summary").json()["metrics"]["bmr_kcal"] == 1469


def test_existing_endpoints_are_untouched(client):
    assert client.get("/health").json() == {"status": "ok"}  # liveness probe stays public and unchanged
    created = client.post("/items", json={"name": "still works"})
    assert created.status_code == 201
    assert client.delete(f"/items/{created.json()['id']}").status_code == 204
