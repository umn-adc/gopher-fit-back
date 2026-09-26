import time
from pathlib import Path

import bcrypt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.database import create_database_engine
from app.features.auth.security import TokenService
from app.main import create_app

SECRET = "test-secret-for-gopher-fit-with-at-least-64-characters-for-testing-only"
PASSWORD = "Password1!"
HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4))


def migrate(path: Path) -> None:
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{path}"
    command.upgrade(config, "head")


@pytest.fixture
def engine(tmp_path):
    path = tmp_path / "test.db"
    migrate(path)
    engine = create_database_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for user_id in range(1, 10):
            connection.exec_driver_sql(
                "INSERT INTO users VALUES (?, ?, ?)", (user_id, f"user{user_id}", HASH)
            )
            connection.exec_driver_sql(
                """
                INSERT INTO profiles VALUES (?, ?, 21, 170, 70, 'Other', 'Sedentary', 'null', '[]')
            """,
                (user_id, f"Private Name {user_id}"),
            )
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    app = create_app(Settings(jwt_secret=SecretStr(SECRET)), engine)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers(engine):
    def for_user(user_id=1):
        session_id = f"test-session-{user_id}"
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO auth_sessions(id,user_id,expires_at) VALUES(?,?,?) "
                "ON CONFLICT(id) DO NOTHING",
                (session_id, user_id, int(time.time()) + 3600),
            )
        token = TokenService(SECRET).create(user_id, f"user{user_id}", session_id)
        return {"Authorization": f"Bearer {token}"}

    return for_user


@pytest.fixture
def authed(client, headers):
    client.headers.update(headers())
    return client
