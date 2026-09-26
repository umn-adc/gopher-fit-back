"""Adopt Go SQLite data in place; initialize missing tables and derived records.

The frozen schema and backfill deliberately do not import application models.
Legacy TEXT password columns are retained; SQLite accepts new BLOB values and
the application reads both storage types. No table rebuild is necessary.
"""

import math
import re
from pathlib import Path

from alembic import op
from sqlalchemy import inspect, text

revision = "0001_adopt_sqlite"
down_revision = None
branch_labels = None
depends_on = None

WHITESPACE = re.compile(r"[\t\n\v\f\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    expected = {
        "users": "id username password",
        "profiles": "user_id name age height weight gender activity_level goals sports",
        "meals": "id user_id date meal_type time",
        "meal_items": "id meal_id name calories protein carbs fat",
        "macro_goals": "user_id calories_target protein_target carbs_target fat_target",
        "workouts": "id user_id workout_name duration",
        "workout_item": "id workout_id exercise_name sets reps weight duration_minutes",
        "friendships": "user1_id user2_id action_user_id status",
        "personal_records": "user_id exercise_key exercise_name max_weight source_workout_item_id",
    }
    for table, columns in expected.items():
        if table in tables:
            actual = {column["name"] for column in inspector.get_columns(table)}
            if missing := set(columns.split()) - actual:
                raise RuntimeError(
                    f"Unsupported legacy schema: {table} is missing {sorted(missing)}"
                )
    if "schema_migrations" in tables:
        versions = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        if versions - {1, 2, 3}:
            raise RuntimeError("Database has unknown Go migrations; review before adopting")
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
        raise RuntimeError("Existing foreign-key violations must be repaired before migration")

    schema = Path(__file__).with_name("initial_schema.sql").read_text()
    for statement in schema.split(";"):
        if statement.strip():
            connection.exec_driver_sql(statement)
    connection.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS personal_records (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            exercise_key TEXT NOT NULL CHECK (length(exercise_key) > 0),
            exercise_name TEXT NOT NULL,
            max_weight REAL NOT NULL CHECK (max_weight > 0),
            source_workout_item_id INTEGER NOT NULL REFERENCES workout_item(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, exercise_key)
        )
    """)
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS personal_records_exercise_weight "
        "ON personal_records (exercise_key, max_weight DESC, user_id)"
    )
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS workouts_user_id ON workouts (user_id)")
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS workout_item_workout_id ON workout_item (workout_id)"
    )
    if "personal_records" not in tables:
        best = {}
        rows = connection.exec_driver_sql("""
            SELECT w.user_id, i.id, i.exercise_name, i.weight
            FROM workout_item i JOIN workouts w ON w.id = i.workout_id WHERE i.weight > 0
        """).fetchall()
        for user_id, item_id, raw_name, weight in rows:
            name = WHITESPACE.sub(" ", raw_name or "").strip(" ")
            key = "".join(char.lower()[0] for char in name)
            if not key or not math.isfinite(weight):
                continue
            candidate = (weight, -item_id, name)
            if (user_id, key) not in best or candidate[:2] > best[user_id, key][:2]:
                best[user_id, key] = candidate
        for (user_id, key), (weight, negative_id, name) in sorted(best.items()):
            connection.exec_driver_sql(
                "INSERT INTO personal_records VALUES (?, ?, ?, ?, ?)",
                (user_id, key, name, weight, -negative_id),
            )
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
        raise RuntimeError("Migration failed foreign-key validation")


def downgrade() -> None:
    raise RuntimeError("Baseline downgrade would discard data; restore a verified backup instead")
