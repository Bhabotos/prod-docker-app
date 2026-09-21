"""Database access for the BMI schema. No business rules here."""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bmi_dashboard.models import Goal, Profile, WeightEntry

SUBJECT = "owner"  # single-user for now; `subject` keeps the schema multi-user ready


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- profile ---------------------------------------------------------------------
def get_profile(session: Session) -> Profile | None:
    return session.scalar(select(Profile).where(Profile.subject == SUBJECT))


def create_profile(session: Session, *, age_years: int, sex: str, height_cm: float, activity_level: str) -> Profile:
    profile = Profile(subject=SUBJECT, age_years=age_years, sex=sex, height_cm=height_cm, activity_level=activity_level)
    session.add(profile)
    session.flush()
    return profile


def update_profile(session: Session, profile: Profile, *, age_years: int, sex: str, height_cm: float, activity_level: str) -> Profile:
    profile.age_years, profile.sex, profile.height_cm, profile.activity_level = age_years, sex, height_cm, activity_level
    profile.updated_at = _now()
    session.flush()
    return profile


# ---- weight entries ------------------------------------------------------------------
def upsert_weight(session: Session, profile: Profile, *, recorded_on: date, weight_kg: float, note: str | None) -> tuple[WeightEntry, bool]:
    """One entry per day: update the existing row for that date, else insert. Returns (entry, created)."""

    def _existing() -> WeightEntry | None:
        return session.scalar(
            select(WeightEntry).where(WeightEntry.profile_id == profile.id, WeightEntry.recorded_on == recorded_on)
        )

    entry = _existing()
    if entry is None:
        try:
            with session.begin_nested():
                entry = WeightEntry(
                    profile_id=profile.id, recorded_on=recorded_on, weight_kg=weight_kg, height_cm=profile.height_cm, note=note
                )
                session.add(entry)
                session.flush()
            return entry, True
        except IntegrityError:  # lost a race with a concurrent request for the same date
            entry = _existing()
            if entry is None:
                raise
    entry.weight_kg, entry.height_cm, entry.note = weight_kg, profile.height_cm, note
    session.flush()
    return entry, False


def get_entry(session: Session, profile: Profile, entry_id: int) -> WeightEntry | None:
    return session.scalar(select(WeightEntry).where(WeightEntry.id == entry_id, WeightEntry.profile_id == profile.id))


def delete_entry(session: Session, entry: WeightEntry) -> None:
    session.delete(entry)
    session.flush()


def latest_entry(session: Session, profile: Profile) -> WeightEntry | None:
    return session.scalar(
        select(WeightEntry).where(WeightEntry.profile_id == profile.id).order_by(WeightEntry.recorded_on.desc()).limit(1)
    )


def list_entries(session: Session, profile: Profile, *, start: date | None = None, end: date | None = None, limit: int = 365) -> list[WeightEntry]:
    """Oldest-first; when `limit` truncates, the most recent entries are kept."""
    query = select(WeightEntry).where(WeightEntry.profile_id == profile.id)
    if start:
        query = query.where(WeightEntry.recorded_on >= start)
    if end:
        query = query.where(WeightEntry.recorded_on <= end)
    rows = session.scalars(query.order_by(WeightEntry.recorded_on.desc()).limit(limit)).all()
    return list(reversed(rows))


# ---- goals ----------------------------------------------------------------------------
def get_goal(session: Session, profile: Profile) -> Goal | None:
    return session.scalar(select(Goal).where(Goal.profile_id == profile.id))


def create_goal(session: Session, profile: Profile, **values) -> Goal:  # noqa: ANN003
    goal = Goal(profile_id=profile.id, **values)
    session.add(goal)
    session.flush()
    return goal


def update_goal(session: Session, goal: Goal, **values) -> Goal:  # noqa: ANN003
    for key, value in values.items():
        setattr(goal, key, value)
    goal.updated_at = _now()
    session.flush()
    return goal
