"""create bmi.profiles, bmi.weight_entries, bmi.goals

ADDITIVE ONLY. Every object is created inside schema "bmi"; nothing in "public"
(items, n8n/invoice tables) is read, altered or dropped.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

S = "bmi"


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("age_years", sa.Integer(), nullable=False),
        sa.Column("sex", sa.String(10), nullable=False),
        sa.Column("height_cm", sa.Numeric(5, 1, asdecimal=False), nullable=False),
        sa.Column("activity_level", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
        sa.UniqueConstraint("subject", name=op.f("uq_profiles_subject")),
        sa.CheckConstraint("age_years BETWEEN 18 AND 100", name=op.f("ck_profiles_age_range")),
        sa.CheckConstraint("height_cm BETWEEN 100 AND 250", name=op.f("ck_profiles_height_range")),
        sa.CheckConstraint("sex IN ('male','female')", name=op.f("ck_profiles_sex")),
        sa.CheckConstraint(
            "activity_level IN ('sedentary','lightly_active','moderately_active','very_active','extra_active')",
            name=op.f("ck_profiles_activity_level"),
        ),
        schema=S,
    )
    op.create_table(
        "weight_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("recorded_on", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2, asdecimal=False), nullable=False),
        sa.Column("height_cm", sa.Numeric(5, 1, asdecimal=False), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weight_entries")),
        sa.ForeignKeyConstraint(
            ["profile_id"], [f"{S}.profiles.id"], name=op.f("fk_weight_entries_profile_id_profiles"), ondelete="CASCADE"
        ),
        sa.UniqueConstraint("profile_id", "recorded_on", name=op.f("uq_weight_entries_profile_id_recorded_on")),
        sa.CheckConstraint("weight_kg BETWEEN 20 AND 400", name=op.f("ck_weight_entries_weight_range")),
        sa.CheckConstraint("height_cm BETWEEN 100 AND 250", name=op.f("ck_weight_entries_height_range")),
        schema=S,
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("target_weight_kg", sa.Numeric(5, 2, asdecimal=False), nullable=False),
        sa.Column("starting_weight_kg", sa.Numeric(5, 2, asdecimal=False), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("daily_calorie_target", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
        sa.ForeignKeyConstraint(
            ["profile_id"], [f"{S}.profiles.id"], name=op.f("fk_goals_profile_id_profiles"), ondelete="CASCADE"
        ),
        sa.UniqueConstraint("profile_id", name=op.f("uq_goals_profile_id")),
        sa.CheckConstraint("target_weight_kg BETWEEN 20 AND 400", name=op.f("ck_goals_target_range")),
        sa.CheckConstraint("starting_weight_kg BETWEEN 20 AND 400", name=op.f("ck_goals_start_range")),
        sa.CheckConstraint(
            "daily_calorie_target IS NULL OR daily_calorie_target BETWEEN 800 AND 6000", name=op.f("ck_goals_calorie_range")
        ),
        schema=S,
    )


def downgrade() -> None:
    # Only ever drops the tables THIS revision created, inside schema "bmi".
    op.drop_table("goals", schema=S)
    op.drop_table("weight_entries", schema=S)
    op.drop_table("profiles", schema=S)
