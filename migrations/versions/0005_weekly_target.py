"""Add an optional weekly workout target to profiles.

Existing profiles keep NULL, meaning no target. No value is inferred.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_weekly_target"
down_revision = "0004_meal_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "weekly_workout_target",
            sa.Integer(),
            sa.CheckConstraint(
                "weekly_workout_target BETWEEN 1 AND 14", name="profiles_weekly_workout_target"
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade discards weekly targets; restore a verified backup instead")
