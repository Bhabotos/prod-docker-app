"""SQLAlchemy models for the `bmi` schema.

Own MetaData/Base, so the existing app's Base.metadata.create_all() (items) can
never create or touch these tables, and vice versa.
"""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, MetaData, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "bmi"

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("age_years BETWEEN 18 AND 100", name="ck_profiles_age_range"),
        CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_profiles_height_range"),
        CheckConstraint("sex IN ('male','female')", name="ck_profiles_sex"),
        CheckConstraint(
            "activity_level IN ('sedentary','lightly_active','moderately_active','very_active','extra_active')",
            name="ck_profiles_activity_level",
        ),
        UniqueConstraint("subject", name="uq_profiles_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), nullable=False, default="owner")
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)
    height_cm: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(20), nullable=False, default="sedentary")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    weight_entries: Mapped[list["WeightEntry"]] = relationship(back_populates="profile", passive_deletes=True)
    goal: Mapped["Goal | None"] = relationship(back_populates="profile", uselist=False, passive_deletes=True)


class WeightEntry(Base):
    __tablename__ = "weight_entries"
    __table_args__ = (
        CheckConstraint("weight_kg BETWEEN 20 AND 400", name="ck_weight_entries_weight_range"),
        CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_weight_entries_height_range"),
        UniqueConstraint("profile_id", "recorded_on", name="uq_weight_entries_profile_id_recorded_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.profiles.id", ondelete="CASCADE", name="fk_weight_entries_profile_id_profiles"), nullable=False
    )
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False)
    # Height at the time of recording, so BMI history stays correct if the profile height is edited later.
    height_cm: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="weight_entries")


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_weight_kg BETWEEN 20 AND 400", name="ck_goals_target_range"),
        CheckConstraint("starting_weight_kg BETWEEN 20 AND 400", name="ck_goals_start_range"),
        CheckConstraint(
            "daily_calorie_target IS NULL OR daily_calorie_target BETWEEN 800 AND 6000", name="ck_goals_calorie_range"
        ),
        UniqueConstraint("profile_id", name="uq_goals_profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.profiles.id", ondelete="CASCADE", name="fk_goals_profile_id_profiles"), nullable=False
    )
    target_weight_kg: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False)
    starting_weight_kg: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Entered by the user; the dashboard never generates or recommends one.
    daily_calorie_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="goal")
