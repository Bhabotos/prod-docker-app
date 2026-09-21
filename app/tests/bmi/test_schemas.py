from datetime import date, timedelta, timezone, datetime

import pytest
from pydantic import ValidationError

from bmi_dashboard import schemas as S

OK = dict(age_years=34, sex="male", height_cm=168, weight_kg=75)


def _msgs(exc: ValidationError) -> str:
    return " | ".join(e["msg"] for e in exc.errors())


def test_valid_profile_defaults_activity():
    assert S.ProfileCreate(**OK).activity_level == "sedentary"


@pytest.mark.parametrize("age", [17, 101, 0, -3])
def test_age_must_be_an_adult_range(age):
    with pytest.raises(ValidationError) as e:
        S.ProfileCreate(**{**OK, "age_years": age})
    assert "Age must be between 18 and 100" in _msgs(e.value)


@pytest.mark.parametrize("field,value", [("height_cm", 99.9), ("height_cm", 250.1), ("weight_kg", 19.9), ("weight_kg", 400.1)])
def test_height_and_weight_ranges(field, value):
    with pytest.raises(ValidationError):
        S.ProfileCreate(**{**OK, field: value})


@pytest.mark.parametrize("field,value", [("height_cm", 100), ("height_cm", 250), ("weight_kg", 20), ("weight_kg", 400), ("age_years", 18), ("age_years", 100)])
def test_range_edges_are_accepted(field, value):
    S.ProfileCreate(**{**OK, field: value})


@pytest.mark.parametrize("bad", [True, "abc", float("nan"), float("inf")])
def test_numbers_reject_booleans_text_nan_inf(bad):
    for field in ("age_years", "height_cm", "weight_kg"):
        with pytest.raises(ValidationError):
            S.ProfileCreate(**{**OK, field: bad})


def test_sex_and_activity_are_enumerated():
    with pytest.raises(ValidationError):
        S.ProfileCreate(**{**OK, "sex": "other"})
    with pytest.raises(ValidationError):
        S.ProfileCreate(**{**OK, "activity_level": "athlete"})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        S.ProfileCreate(**OK, is_admin=True)


def test_entry_date_rules():
    today = datetime.now(timezone.utc).date()
    S.WeightIn(weight_kg=70, recorded_on=today + timedelta(days=1))  # timezones ahead of UTC
    with pytest.raises(ValidationError) as e:
        S.WeightIn(weight_kg=70, recorded_on=today + timedelta(days=2))
    assert "future" in _msgs(e.value)
    with pytest.raises(ValidationError):
        S.WeightIn(weight_kg=70, recorded_on=date(1989, 12, 31))


def test_note_is_trimmed_and_length_limited():
    assert S.WeightIn(weight_kg=70, note="  after run  ").note == "after run"
    assert S.WeightIn(weight_kg=70, note="   ").note is None
    with pytest.raises(ValidationError):
        S.WeightIn(weight_kg=70, note="x" * 201)


def test_goal_ranges():
    assert S.GoalCreate(target_weight_kg=70, daily_calorie_target=2000).daily_calorie_target == 2000
    for bad in ({"target_weight_kg": 19}, {"target_weight_kg": 70, "daily_calorie_target": 799}, {"target_weight_kg": 70, "daily_calorie_target": 6001}):
        with pytest.raises(ValidationError):
            S.GoalCreate(**bad)
