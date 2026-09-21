import pytest

from bmi_dashboard.services import calculations as c


def test_bmi_matches_the_worked_example():
    assert c.calculate_bmi(75, 168) == 26.6


@pytest.mark.parametrize(
    "bmi,code",
    [
        (15.0, "underweight"), (18.44, "underweight"),   # displays 18.4
        (18.45, "normal"), (18.5, "normal"),             # 18.45 displays 18.5
        (24.94, "normal"), (24.9, "normal"),
        (24.95, "overweight"), (25.0, "overweight"),     # 24.95 displays 25.0 -> number and label agree
        (29.94, "overweight"),
        (29.95, "obesity"), (30.0, "obesity"), (45.0, "obesity"),
    ],
)
def test_category_boundaries_use_the_displayed_value(bmi, code):
    assert c.bmi_category(bmi)[0] == code


def test_category_label():
    assert c.bmi_category(22.0) == ("normal", "Normal weight")


@pytest.mark.parametrize("sex,expected", [("male", 1635), ("female", 1469)])
def test_bmr_mifflin_st_jeor(sex, expected):
    # 10*75 + 6.25*168 - 5*34 = 1630; +5 (male) or -161 (female)
    assert c.calculate_bmr(75, 168, 34, sex) == expected


@pytest.mark.parametrize(
    "level,factor,kcal",
    [("sedentary", 1.2, 1962), ("lightly_active", 1.375, 2248), ("moderately_active", 1.55, 2534),
     ("very_active", 1.725, 2820), ("extra_active", 1.9, 3107)],  # 3106.5 rounds half UP, not to even
)
def test_daily_calories(level, factor, kcal):
    assert c.activity_factor(level) == factor
    assert c.daily_calorie_requirement(1635, level) == kcal


@pytest.mark.parametrize("args", [(0, 168), (-5, 168), (75, 0), (75, -1)])
def test_bmi_rejects_non_positive_inputs(args):
    with pytest.raises(ValueError):
        c.calculate_bmi(*args)


def test_bmr_rejects_bad_sex_and_age():
    with pytest.raises(ValueError):
        c.calculate_bmr(75, 168, 34, "other")
    with pytest.raises(ValueError):
        c.calculate_bmr(75, 168, 0, "male")


def test_unknown_activity_level():
    with pytest.raises(ValueError):
        c.activity_factor("couch_marathon")


def test_round_half_up_is_not_bankers_rounding():
    assert c.round_half_up(2.5) == 3 and c.round_half_up(0.5) == 1 and c.round_half_up(1.25, 1) == 1.3


def test_target_warning_only_for_underweight_range_and_never_a_recommendation():
    assert c.target_weight_warnings(70, 168) == []
    (warning,) = c.target_weight_warnings(45, 168)  # BMI 15.9
    assert "does not recommend" in warning
