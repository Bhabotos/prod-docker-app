"""Pydantic request/response models. All input validation lives here."""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bmi_dashboard import limits as L

SexT = Literal["male", "female"]
ActivityT = Literal["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _reject_bool(value):  # noqa: ANN001, ANN202
    # JSON true/false must not be accepted as 1/0 for numeric fields.
    if isinstance(value, bool):
        raise ValueError("must be a number")
    return value


def _in_range(value: float, low: float, high: float, label: str, unit: str = "") -> float:
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}{unit}.")
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- validated field mixins -------------------------------------------------
class _AgeMixin(BaseModel):
    age_years: int

    @field_validator("age_years", mode="before")
    @classmethod
    def _age(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("age_years")
    @classmethod
    def _age_range(cls, v: int) -> int:
        if not L.AGE_MIN <= v <= L.AGE_MAX:
            raise ValueError(
                f"Age must be between {L.AGE_MIN} and {L.AGE_MAX}. "
                "The BMI categories and BMR formula used here apply to adults."
            )
        return v


class _HeightMixin(BaseModel):
    height_cm: float = Field(allow_inf_nan=False)

    @field_validator("height_cm", mode="before")
    @classmethod
    def _h(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("height_cm")
    @classmethod
    def _h_range(cls, v: float) -> float:
        return _in_range(v, L.HEIGHT_MIN_CM, L.HEIGHT_MAX_CM, "Height", " cm")


def _weight_ok(v: float, label: str = "Weight") -> float:
    return _in_range(v, L.WEIGHT_MIN_KG, L.WEIGHT_MAX_KG, label, " kg")


def _entry_date_ok(v: date | None) -> date | None:
    if v is None:
        return v
    if v < L.EARLIEST_ENTRY_DATE:
        raise ValueError(f"Date cannot be before {L.EARLIEST_ENTRY_DATE.isoformat()}.")
    if v > _utc_today() + timedelta(days=L.FUTURE_TOLERANCE_DAYS):
        raise ValueError("Date cannot be in the future.")
    return v


# ---- profile ------------------------------------------------------------------
class ProfileUpdate(Strict, _AgeMixin, _HeightMixin):
    sex: SexT
    activity_level: ActivityT = "sedentary"


class ProfileCreate(ProfileUpdate):
    """Creating a profile also records the first weight entry."""

    weight_kg: float = Field(allow_inf_nan=False)
    recorded_on: date | None = None

    @field_validator("weight_kg", mode="before")
    @classmethod
    def _w(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("weight_kg")
    @classmethod
    def _w_range(cls, v: float) -> float:
        return _weight_ok(v)

    @field_validator("recorded_on")
    @classmethod
    def _d(cls, v):  # noqa: ANN001, ANN206
        return _entry_date_ok(v)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    age_years: int
    sex: SexT
    height_cm: float
    activity_level: ActivityT
    created_at: datetime
    updated_at: datetime


# ---- weight ---------------------------------------------------------------------
class WeightIn(Strict):
    weight_kg: float = Field(allow_inf_nan=False)
    recorded_on: date | None = None
    note: Annotated[str | None, Field(max_length=L.NOTE_MAX_LENGTH)] = None

    @field_validator("weight_kg", mode="before")
    @classmethod
    def _w(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("weight_kg")
    @classmethod
    def _w_range(cls, v: float) -> float:
        return _weight_ok(v)

    @field_validator("recorded_on")
    @classmethod
    def _d(cls, v):  # noqa: ANN001, ANN206
        return _entry_date_ok(v)

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return v or None


class WeightEntryOut(BaseModel):
    id: int
    recorded_on: date
    weight_kg: float
    height_cm: float
    bmi: float
    bmi_category: str
    bmi_category_label: str
    note: str | None = None


class BmiBandOut(BaseModel):
    category: str
    label: str
    min: float | None
    max: float | None


class HistoryOut(BaseModel):
    entries: list[WeightEntryOut]
    bmi_bands: list[BmiBandOut]
    count: int


class MonthOut(BaseModel):
    month: str
    entries: int
    first_weight_kg: float
    last_weight_kg: float
    change_kg: float
    average_weight_kg: float
    min_weight_kg: float
    max_weight_kg: float


class MonthlyOut(BaseModel):
    months: list[MonthOut]


# ---- goals ------------------------------------------------------------------------
class _GoalFields(Strict):
    target_weight_kg: float = Field(allow_inf_nan=False)
    daily_calorie_target: int | None = None

    @field_validator("target_weight_kg", mode="before")
    @classmethod
    def _t(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("target_weight_kg")
    @classmethod
    def _t_range(cls, v: float) -> float:
        return _weight_ok(v, "Target weight")

    @field_validator("daily_calorie_target", mode="before")
    @classmethod
    def _c(cls, v):  # noqa: ANN001, ANN206
        return _reject_bool(v)

    @field_validator("daily_calorie_target")
    @classmethod
    def _c_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return int(_in_range(v, L.CALORIE_TARGET_MIN, L.CALORIE_TARGET_MAX, "Daily calorie target", " kcal"))


class GoalCreate(_GoalFields):
    """starting weight defaults to the latest recorded weight."""

    starting_weight_kg: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("starting_weight_kg")
    @classmethod
    def _s(cls, v: float | None) -> float | None:
        return v if v is None else _weight_ok(v, "Starting weight")


class GoalUpdate(_GoalFields):
    restart_progress: bool = False  # true: starting weight = latest weight, started today


class ProgressOut(BaseModel):
    status: str
    direction: str
    progress_percent: float | None
    raw_progress_percent: float | None
    remaining_kg: float | None


class GoalOut(BaseModel):
    target_weight_kg: float
    starting_weight_kg: float
    started_on: date
    daily_calorie_target: int | None
    daily_calorie_requirement: int | None  # estimated maintenance calories, if computable
    current_weight_kg: float | None
    progress: ProgressOut
    warnings: list[str]
    created_at: datetime
    updated_at: datetime


# ---- summary / limits -----------------------------------------------------------------
class MetricsOut(BaseModel):
    weight_kg: float
    height_cm: float
    bmi: float
    bmi_category: str
    bmi_category_label: str
    bmr_kcal: int
    activity_level: str
    activity_factor: float
    daily_calories_kcal: int


class LatestWeightOut(BaseModel):
    id: int
    recorded_on: date
    weight_kg: float


class SummaryOut(BaseModel):
    profile: ProfileOut
    latest_weight: LatestWeightOut | None
    metrics: MetricsOut | None
    goal: GoalOut | None
    disclaimer: str
    formulas: dict[str, str]


class LoginIn(Strict):
    password: Annotated[str, Field(min_length=1, max_length=256)]
