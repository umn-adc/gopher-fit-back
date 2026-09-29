"""Index meals by owner and date for date-filtered lists and daily summaries.

Without it, GET /nutrition/summary scans every user's meals. No rows change.
"""

from alembic import op

revision = "0004_meal_dates"
down_revision = "0003_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("meals_user_date_id", "meals", ["user_id", "date", "id"])


def downgrade() -> None:
    op.drop_index("meals_user_date_id", table_name="meals")
