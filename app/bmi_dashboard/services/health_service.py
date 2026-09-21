"""Turns stored rows into the API's response models using the pure calculators."""
from bmi_dashboard import limits as L
from bmi_dashboard import schemas as S
from bmi_dashboard.services import calculations as calc
from bmi_dashboard.services.progress import goal_progress, monthly_summary


def entry_out(entry) -> S.WeightEntryOut:  # noqa: ANN001
    """BMI uses the height snapshotted on the entry, so old points don't shift when height is edited."""
    bmi = calc.calculate_bmi(entry.weight_kg, entry.height_cm)
    code, label = calc.bmi_category(bmi)
    return S.WeightEntryOut(
        id=entry.id, recorded_on=entry.recorded_on, weight_kg=entry.weight_kg, height_cm=entry.height_cm,
        bmi=bmi, bmi_category=code, bmi_category_label=label, note=entry.note,
    )


def build_metrics(profile, weight_kg: float) -> S.MetricsOut:  # noqa: ANN001
    bmi = calc.calculate_bmi(weight_kg, profile.height_cm)
    code, label = calc.bmi_category(bmi)
    bmr = calc.calculate_bmr(weight_kg, profile.height_cm, profile.age_years, profile.sex)
    return S.MetricsOut(
        weight_kg=weight_kg, height_cm=profile.height_cm, bmi=bmi, bmi_category=code, bmi_category_label=label,
        bmr_kcal=bmr, activity_level=profile.activity_level, activity_factor=calc.activity_factor(profile.activity_level),
        daily_calories_kcal=calc.daily_calorie_requirement(bmr, profile.activity_level),
    )


def build_goal(goal, profile, latest) -> S.GoalOut:  # noqa: ANN001
    current = latest.weight_kg if latest else None
    progress = goal_progress(goal.starting_weight_kg, current, goal.target_weight_kg)
    requirement = build_metrics(profile, current).daily_calories_kcal if current is not None else None
    return S.GoalOut(
        target_weight_kg=goal.target_weight_kg, starting_weight_kg=goal.starting_weight_kg, started_on=goal.started_on,
        daily_calorie_target=goal.daily_calorie_target, daily_calorie_requirement=requirement, current_weight_kg=current,
        progress=S.ProgressOut(
            status=progress.status, direction=progress.direction, progress_percent=progress.progress_percent,
            raw_progress_percent=progress.raw_progress_percent, remaining_kg=progress.remaining_kg,
        ),
        warnings=calc.target_weight_warnings(goal.target_weight_kg, profile.height_cm),
        created_at=goal.created_at, updated_at=goal.updated_at,
    )


def build_summary(profile, latest, goal) -> S.SummaryOut:  # noqa: ANN001
    return S.SummaryOut(
        profile=S.ProfileOut.model_validate(profile),
        latest_weight=S.LatestWeightOut(id=latest.id, recorded_on=latest.recorded_on, weight_kg=latest.weight_kg) if latest else None,
        metrics=build_metrics(profile, latest.weight_kg) if latest else None,
        goal=build_goal(goal, profile, latest) if goal else None,
        disclaimer=L.DISCLAIMER,
        formulas={"bmi": "weight (kg) / height (m)^2", "bmr": "Mifflin-St Jeor", "calories": "BMR x activity factor"},
    )


def bmi_bands() -> list[S.BmiBandOut]:
    return [S.BmiBandOut(category=c, label=lbl, min=lo, max=hi) for c, lbl, lo, hi in calc.BMI_BANDS]


def build_history(entries) -> S.HistoryOut:  # noqa: ANN001
    return S.HistoryOut(entries=[entry_out(e) for e in entries], bmi_bands=bmi_bands(), count=len(entries))


def build_monthly(entries) -> S.MonthlyOut:  # noqa: ANN001
    return S.MonthlyOut(months=[S.MonthOut(**m) for m in monthly_summary([(e.recorded_on, e.weight_kg) for e in entries])])


def limits_payload() -> dict:
    return {
        "age": {"min": L.AGE_MIN, "max": L.AGE_MAX},
        "height_cm": {"min": L.HEIGHT_MIN_CM, "max": L.HEIGHT_MAX_CM},
        "weight_kg": {"min": L.WEIGHT_MIN_KG, "max": L.WEIGHT_MAX_KG},
        "calorie_target": {"min": L.CALORIE_TARGET_MIN, "max": L.CALORIE_TARGET_MAX},
        "note_max_length": L.NOTE_MAX_LENGTH,
        "sexes": [{"value": k, "label": v} for k, v in L.SEXES.items()],
        "activity_levels": [{"value": k, "label": lab, "factor": f} for k, (lab, f) in L.ACTIVITY_LEVELS.items()],
        "bmi_bands": [b.model_dump() for b in bmi_bands()],
        "disclaimer": L.DISCLAIMER,
    }
