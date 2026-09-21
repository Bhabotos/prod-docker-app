"""Single source of truth for input ranges and lookup values.

The API exposes these through GET /health/limits so the browser never has to
hard-code them. The database CHECK constraints in the migration repeat the
numbers on purpose (a migration is a frozen historical record).
"""
from datetime import date

AGE_MIN, AGE_MAX = 18, 100
HEIGHT_MIN_CM, HEIGHT_MAX_CM = 100.0, 250.0
WEIGHT_MIN_KG, WEIGHT_MAX_KG = 20.0, 400.0
CALORIE_TARGET_MIN, CALORIE_TARGET_MAX = 800, 6000
NOTE_MAX_LENGTH = 200
EARLIEST_ENTRY_DATE = date(1990, 1, 1)
FUTURE_TOLERANCE_DAYS = 1  # users east of UTC can legitimately be a day ahead

SEXES = {"male": "Male", "female": "Female"}

# level -> (label, PAL multiplier)
ACTIVITY_LEVELS = {
    "sedentary": ("Sedentary (little or no exercise)", 1.2),
    "lightly_active": ("Lightly active (light exercise 1-3 days/week)", 1.375),
    "moderately_active": ("Moderately active (moderate exercise 3-5 days/week)", 1.55),
    "very_active": ("Very active (hard exercise 6-7 days/week)", 1.725),
    "extra_active": ("Extra active (very hard exercise, physical job)", 1.9),
}

DISCLAIMER = (
    "General wellness and educational information only. BMI, BMR and calorie "
    "figures are estimates from standard formulas; they are not a medical "
    "diagnosis and not medical advice. Talk to a qualified healthcare "
    "professional before changing your diet or exercise."
)
