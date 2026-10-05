"""Add health connections and the data imported from Apple Health / Health Connect.

New tables only; no existing row changes. Every table cascades from the owning
user, so account deletion removes imported health data with the rest.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_health_sync"
down_revision = "0006_favorite_meals"
branch_labels = None
depends_on = None


def user_id() -> sa.Column[int]:
    return sa.Column(
        "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "health_connections",
        user_id(),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("data_types", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "provider"),
    )
    op.create_table(
        "health_daily_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_id(),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("active_energy_kcal", sa.Float(), nullable=True),
        sa.Column("resting_heart_rate_bpm", sa.Float(), nullable=True),
        sa.Column("heart_rate_min_bpm", sa.Float(), nullable=True),
        sa.Column("heart_rate_avg_bpm", sa.Float(), nullable=True),
        sa.Column("heart_rate_max_bpm", sa.Float(), nullable=True),
        sa.UniqueConstraint("user_id", "provider", "date"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "health_workouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_id(),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("start_at", sa.Text(), nullable=False),
        sa.Column("end_at", sa.Text(), nullable=False),
        sa.Column("energy_kcal", sa.Float(), nullable=True),
        sa.Column("avg_heart_rate_bpm", sa.Float(), nullable=True),
        sa.Column("max_heart_rate_bpm", sa.Float(), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "provider", "external_id"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "health_weight_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_id(),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("measured_at", sa.Text(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "provider", "external_id"),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "health_workouts_user_provider_start",
        "health_workouts",
        ["user_id", "provider", "start_at"],
    )
    op.create_index(
        "health_weight_samples_user_measured", "health_weight_samples", ["user_id", "measured_at"]
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade discards imported health data; restore a verified backup instead")
