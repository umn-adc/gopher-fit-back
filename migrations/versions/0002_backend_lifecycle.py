"""Add revocable authentication, recovery, throttles, workout time, and query indexes.

No existing columns or rows are rewritten. Historical workout times remain NULL.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_backend_lifecycle"
down_revision = "0001_adopt_sqlite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workouts", sa.Column("occurred_at", sa.Text(), nullable=True))
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("used_at", sa.Integer(), nullable=True),
    )
    op.create_table(
        "recovery_addresses",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("pending_email", sa.Text(), nullable=True),
    )
    op.create_table(
        "recovery_tokens",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.Integer(), nullable=True),
    )
    op.create_table(
        "rate_buckets",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("window", sa.Integer(), primary_key=True),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    for name, table, columns in [
        ("auth_sessions_user", "auth_sessions", ["user_id"]),
        ("refresh_tokens_session", "refresh_tokens", ["session_id"]),
        ("recovery_tokens_user_purpose", "recovery_tokens", ["user_id", "purpose"]),
        ("rate_buckets_expires", "rate_buckets", ["expires_at"]),
        ("workouts_user_occurred_id", "workouts", ["user_id", "occurred_at", "id"]),
        ("meals_user_id_id", "meals", ["user_id", "id"]),
        ("meal_items_meal_id", "meal_items", ["meal_id"]),
        ("friendships_user1_status", "friendships", ["user1_id", "status", "user2_id"]),
        ("friendships_user2_status", "friendships", ["user2_id", "status", "user1_id"]),
        ("friendships_actor", "friendships", ["action_user_id"]),
    ]:
        op.create_index(name, table, columns)


def downgrade() -> None:
    raise RuntimeError("Downgrade discards security state; restore a verified backup instead")
