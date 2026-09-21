from datetime import date

from bmi_dashboard.services.progress import goal_progress, monthly_summary


def test_normal_loss_progress():
    p = goal_progress(77, 75, 70)  # (77-75)/(77-70)
    assert (p.status, p.direction, p.progress_percent, p.remaining_kg) == ("in_progress", "lose", 28.6, 5.0)


def test_goal_achieved_and_overshoot_is_clamped():
    assert goal_progress(77, 70, 70).status == "achieved"
    p = goal_progress(77, 68, 70)
    assert (p.status, p.progress_percent, p.raw_progress_percent) == ("achieved", 100.0, 128.6)


def test_current_above_starting_weight_is_behind_not_negative_display():
    p = goal_progress(77, 78, 70)
    assert (p.status, p.progress_percent, p.raw_progress_percent) == ("behind", 0.0, -14.3)


def test_target_equals_starting_weight_avoids_division_by_zero():
    p = goal_progress(75, 75, 75)
    assert (p.status, p.progress_percent, p.raw_progress_percent, p.direction) == ("target_equals_start", None, None, "maintain")


def test_gain_goal_uses_the_same_formula():
    p = goal_progress(60, 62, 70)
    assert (p.direction, p.progress_percent) == ("gain", 20.0)
    assert goal_progress(60, 58, 70).status == "behind"


def test_missing_history():
    p = goal_progress(77, None, 70)
    assert (p.status, p.progress_percent, p.remaining_kg) == ("no_data", None, None)


def test_monthly_summary_groups_and_orders():
    rows = [(date(2026, 9, 20), 75.0), (date(2026, 8, 3), 78.0), (date(2026, 8, 29), 76.5), (date(2026, 9, 1), 76.0)]
    aug, sep = monthly_summary(rows)
    assert aug["month"] == "2026-08" and aug["entries"] == 2
    assert (aug["first_weight_kg"], aug["last_weight_kg"], aug["change_kg"]) == (78.0, 76.5, -1.5)
    assert (sep["first_weight_kg"], sep["last_weight_kg"], sep["change_kg"], sep["average_weight_kg"]) == (76.0, 75.0, -1.0, 75.5)


def test_monthly_summary_empty():
    assert monthly_summary([]) == []
