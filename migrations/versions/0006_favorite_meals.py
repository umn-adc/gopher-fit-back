"""Add reusable favorite meal templates and their items.

New tables only; no existing row changes. Both cascade from the owning user, so
account deletion removes them with the rest of the user's data.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_favorite_meals"
down_revision = "0005_weekly_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorite_meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("meal_type", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "favorite_meal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "favorite_id",
            sa.Integer(),
            sa.ForeignKey("favorite_meals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.Column("protein", sa.Integer(), nullable=False),
        sa.Column("carbs", sa.Integer(), nullable=False),
        sa.Column("fat", sa.Integer(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("favorite_meals_user_id_id", "favorite_meals", ["user_id", "id"])
    op.create_index("favorite_meal_items_favorite_id", "favorite_meal_items", ["favorite_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade discards favorite meals; restore a verified backup instead")
