import sqlite3
from pathlib import Path

import bcrypt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from tests.conftest import HASH, PASSWORD, SECRET, migrate

SCHEMA = Path("migrations/versions/initial_schema.sql").read_text()


def snapshot(connection):
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name != 'alembic_version' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(
            f"SELECT {'id,user_id,workout_name,duration' if table == 'workouts' else '*'} "
            f'FROM "{table}" ORDER BY rowid'
        ).fetchall()
        for table in tables
    }


def legacy_database(path, text_password=True, ledger=True):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            SCHEMA.replace("password BLOB", "password TEXT") if text_password else SCHEMA
        )
        connection.execute(
            "INSERT INTO users VALUES (7, 'legacy', ?)", (HASH.decode() if text_password else HASH,)
        )
        connection.execute("INSERT INTO users VALUES (8, 'friend', ?)", (HASH,))
        connection.execute("""INSERT INTO profiles VALUES
            (7, 'Preserved', 25, 180, 75, 'Other', 'Sedentary', '["Gain"]', '[]')""")
        connection.execute("INSERT INTO meals VALUES (4, 7, '2024-01-01', 'Lunch', '12:00')")
        connection.execute("INSERT INTO meal_items VALUES (3, 4, 'Rice', 100, 1, 2, 3)")
        connection.execute("INSERT INTO macro_goals VALUES (7, 2000, 100, 200, 50)")
        connection.execute("INSERT INTO friendships VALUES (7, 8, 7, 'pending')")
        connection.execute("INSERT INTO workouts VALUES (10, 7, 'Historical', 30)")
        lifts = [
            (1, "Bench Press", 100),
            (2, " \tBENCH\u00a0PRESS \n", 125.5),
            (3, "bench press", 125.5),
            (4, "Squat", 200),
            (5, "Cardio", 0),
            (6, "Negative", -10),
            (7, "   ", 200),
            (8, None, 300),
            (9, "Unknown", None),
            (10, "Infinite", float("inf")),
        ]
        for item_id, name, weight in lifts:
            connection.execute(
                "INSERT INTO workout_item VALUES (?, 10, ?, 0, 0, ?, 0)", (item_id, name, weight)
            )
        if ledger:
            connection.executescript("""
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO schema_migrations(version, name) VALUES (1, 'initial schema');
            """)
        return snapshot(connection)


@pytest.mark.parametrize("text_password,ledger", [(True, False), (True, True), (False, True)])
def test_adoption_preserves_all_rows_hashes_relations_and_sequences(
    tmp_path, text_password, ledger
):
    path = tmp_path / "legacy.db"
    before = legacy_database(path, text_password, ledger)
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {table: after[table] for table in before} == before
        assert after["personal_records"] == [
            (7, "bench press", "BENCH PRESS", 125.5, 2),
            (7, "squat", "Squat", 200.0, 4),
        ]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        stored = connection.execute("SELECT password FROM users WHERE id=7").fetchone()[0]
        assert bcrypt.checkpw(
            PASSWORD.encode(), stored.encode() if isinstance(stored, str) else stored
        )
        connection.execute("INSERT INTO users(username, password) VALUES ('next', ?)", (HASH,))
        assert connection.execute("SELECT id FROM users WHERE username='next'").fetchone()[0] > 8
    with sqlite3.connect(str(path) + ".pre-python.bak") as backup:
        assert snapshot(backup) == before
    migrate(path)
    with sqlite3.connect(str(path) + ".pre-python.bak") as backup:
        assert snapshot(backup) == before
    app = create_app(Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{path}"))
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "legacy", "password": PASSWORD})
        assert response.status_code == 200
        client.headers["Authorization"] = "Bearer " + response.json()["token"]
        assert client.get("/profile/").json()["name"] == "Preserved"
        assert client.get("/nutrition/meals").json()[0]["items"][0]["name"] == "Rice"
        assert client.get("/social/muscle-ranks").json()[0]["max_weight"] == 125.5


def test_existing_version_three_records_and_schema_are_untouched(tmp_path):
    path = tmp_path / "current-go.db"
    legacy_database(path, text_password=False)
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE personal_records (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                exercise_key TEXT NOT NULL CHECK (length(exercise_key)>0),
                exercise_name TEXT NOT NULL,
                max_weight REAL NOT NULL CHECK(max_weight>0),
                source_workout_item_id INTEGER NOT NULL
                    REFERENCES workout_item(id) ON DELETE CASCADE,
                PRIMARY KEY(user_id,exercise_key));
            INSERT INTO personal_records VALUES (7, 'bench press', 'Original display', 125.5, 2);
            INSERT INTO schema_migrations(version,name) VALUES (2,'blob'),(3,'records');
        """)
        before = snapshot(connection)
        ddl = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name != 'workouts'"
        ).fetchall()
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {table: after[table] for table in before} == before
        assert connection.execute("SELECT occurred_at FROM workouts").fetchall() == [(None,)]
        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN "
                "('users','profiles','meals','meal_items','macro_goals','workout_item',"
                "'friendships','personal_records','schema_migrations','sqlite_sequence')"
            ).fetchall()
            == ddl
        )


def test_invalid_history_rolls_back_and_can_retry(tmp_path):
    path = tmp_path / "orphan.db"
    legacy_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO workouts VALUES (99, 99, 'Orphan', 1)")
        before = snapshot(connection)
    with pytest.raises(RuntimeError, match="foreign-key violations"):
        migrate(path)
    with sqlite3.connect(path) as connection:
        assert snapshot(connection) == before
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='personal_records'"
        ).fetchall()
        connection.execute("INSERT INTO users VALUES (99, 'Recovered', ?)", (HASH,))
    migrate(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_unsupported_partial_schema_is_rejected_without_changes(tmp_path):
    path = tmp_path / "partial.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (1)")
        before = snapshot(connection)
    with pytest.raises(RuntimeError, match="Unsupported legacy schema"):
        migrate(path)
    with sqlite3.connect(path) as connection:
        assert snapshot(connection) == before


def test_foreign_keys_enforced_on_replacement_connections(engine):
    for _ in range(2):
        with engine.begin() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        engine.dispose()
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM users WHERE id=1")
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM profiles WHERE user_id=1").scalar()
            == 0
        )


def test_startup_requires_explicit_migration(tmp_path):
    app = create_app(
        Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{tmp_path / 'empty.db'}")
    )
    with pytest.raises(RuntimeError, match="alembic upgrade head"), TestClient(app):
        pass


def test_migration_backup_includes_committed_wal_data(tmp_path):
    path = tmp_path / "wal.db"
    legacy_database(path)
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO users VALUES (99, 'wal-user', ?)", (HASH,))
        writer.commit()
        assert Path(str(path) + "-wal").stat().st_size > 0
        migrate(path)
        with sqlite3.connect(str(path) + ".pre-python.bak") as backup:
            assert backup.execute("SELECT username FROM users WHERE id=99").fetchone() == (
                "wal-user",
            )
    finally:
        writer.close()


def test_ddl_failure_leaves_no_partial_schema_and_can_retry(tmp_path):
    from sqlalchemy.exc import OperationalError

    path = tmp_path / "ddl-failure.db"
    before = legacy_database(path)
    with sqlite3.connect(path) as connection:
        # Existing object collides with the index created after the new records table.
        connection.execute("CREATE TABLE personal_records_exercise_weight (id INTEGER)")
    with pytest.raises(OperationalError):
        migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert "personal_records" not in after
        assert {table: after[table] for table in before} == before
        connection.execute("DROP TABLE personal_records_exercise_weight")
    migrate(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM personal_records").fetchone() == (2,)


@pytest.mark.parametrize("legacy", [False, True])
def test_alembic_comparison_does_not_propose_destructive_baseline_changes(tmp_path, legacy):
    path = tmp_path / "compare.db"
    if legacy:
        legacy_database(path)
    migrate(path)
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{path}"
    command.check(config)


def test_additive_revision_preserves_0001_data_and_rolls_back_ddl_failure(tmp_path):
    path = tmp_path / "python-baseline.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{path}"
    command.upgrade(config, "0001_adopt_sqlite")
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO users VALUES(1,'existing',?)", (HASH,))
        connection.execute("INSERT INTO workouts VALUES(1,1,'Unknown date',60)")
        connection.execute("INSERT INTO workout_item VALUES(1,1,'Bench',3,10,100,0)")
        connection.execute("INSERT INTO personal_records VALUES(1,'bench','Bench',100,1)")
        before = snapshot(connection)
        connection.execute("CREATE TABLE auth_sessions_user(id INTEGER)")
    from sqlalchemy.exc import OperationalError

    with pytest.raises(OperationalError):
        command.upgrade(config, "head")
    with sqlite3.connect(path) as connection:
        assert "occurred_at" not in [
            row[1] for row in connection.execute("PRAGMA table_info(workouts)")
        ]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_adopt_sqlite",
        )
        assert not connection.execute(
            "SELECT name FROM sqlite_master WHERE name='auth_sessions'"
        ).fetchall()
        connection.execute("DROP TABLE auth_sessions_user")
    command.upgrade(config, "head")
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {name: after[name] for name in before} == before
        assert connection.execute("SELECT occurred_at FROM workouts").fetchall() == [(None,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
