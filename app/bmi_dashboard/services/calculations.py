"""Pure health calculations. No database, no FastAPI, no I/O.

General wellness estimates only - see limits.DISCLAIMER.
"""
from decimal import ROUND_HALF_UP, Decimal

from bmi_dashboard.limits import ACTIVITY_LEVELS

# (code, label, lower bound inclusive, upper bound exclusive)
BMI_BANDS = (
    ("underweight", "Underweight", None, 18.5),
    ("normal", "Normal weight", 18.5, 25.0),
    ("overweight", "Overweight", 25.0, 30.0),
    ("obesity", "Obesity", 30.0, None),
)


def round_half_up(value: float, digits: int = 0) -> float:
    """Predictable rounding (Python's round() is banker's rounding)."""
    quantum = Decimal(1).scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _positive(name: str, value: float) -> None:
    if not value > 0:
        raise ValueError(f"{name} must be greater than zero")


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """BMI rounded to one decimal, the value shown to the user."""
    _positive("weight_kg", weight_kg)
    _positive("height_cm", height_cm)
    height_m = height_cm / 100
    return round_half_up(weight_kg / (height_m**2), 1)


def bmi_category(bmi: float) -> tuple[str, str]:
    """(code, label) for a BMI. Uses the *displayed* 1-decimal value so the
    number and its label can never disagree (24.9 is normal, 25.0 overweight).
    """
    shown = round_half_up(bmi, 1)
    for code, label, _low, high in BMI_BANDS:
        if high is None or shown < high:
            return code, label
    raise AssertionError("unreachable: last band is open-ended")


def calculate_bmr(weight_kg: float, height_cm: float, age_years: int, sex: str) -> int:
    """Mifflin-St Jeor equation, rounded to whole kcal/day."""
    _positive("weight_kg", weight_kg)
    _positive("height_cm", height_cm)
    _positive("age_years", age_years)
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years
    if sex == "male":
        return int(round_half_up(base + 5))
    if sex == "female":
        return int(round_half_up(base - 161))
    raise ValueError(f"unsupported sex: {sex!r}")


def activity_factor(level: str) -> float:
    try:
        return ACTIVITY_LEVELS[level][1]
    except KeyError:
        raise ValueError(f"unknown activity level: {level!r}") from None


def daily_calorie_requirement(bmr: float, level: str) -> int:
    """Estimated maintenance calories = BMR x activity factor."""
    return int(round_half_up(bmr * activity_factor(level)))


def target_weight_warnings(target_weight_kg: float, height_cm: float) -> list[str]:
    """Neutral notes about a user-chosen target. Never a recommendation."""
    warnings = []
    if calculate_bmi(target_weight_kg, height_cm) < BMI_BANDS[0][3]:
        warnings.append(
            "This target weight corresponds to a BMI in the underweight range (below 18.5). "
            "This dashboard does not recommend targets; consider discussing it with a healthcare professional."
        )
    return warnings
