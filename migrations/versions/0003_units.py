"""Add weight units, overall workout minutes, and a display unit preference.

Existing rows keep NULL in every new column: a NULL weight unit is unknown, a NULL
workout duration_minutes is unknown, and a NULL unit preference reads as metric. No
unit is inferred from other data. personal_records is a derived projection that now
holds kilograms from items with a known unit; right after this revision no item has
one, so the projection is rebuilt empty.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_units"
down_revision = "0002_backend_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workout_item",
        sa.Column(
            "weight_unit",
            sa.Text(),
            sa.CheckConstraint("weight_unit IN ('kg', 'lb')", name="workout_item_weight_unit"),
            nullable=True,
        ),
    )
    op.add_column("workouts", sa.Column("duration_minutes", sa.REAL(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "unit_preference",
            sa.Text(),
            sa.CheckConstraint(
                "unit_preference IN ('metric', 'imperial')", name="profiles_unit_preference"
            ),
            nullable=True,
        ),
    )
    # Every workout_item.weight_unit is NULL at this point, so no record qualifies.
    op.execute("DELETE FROM personal_records")


def downgrade() -> None:
    raise RuntimeError("Downgrade discards recorded units; restore a verified backup instead")
