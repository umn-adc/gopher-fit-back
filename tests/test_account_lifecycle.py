import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.features.auth.delivery import Delivery
from app.features.auth.security import token_hash
from app.main import create_app
from tests.conftest import PASSWORD, SECRET


def login(client, username="user1", password=PASSWORD):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(auth):
    return {"Authorization": "Bearer " + auth["token"]}


@dataclass
class Mailbox:
    messages: list[Delivery] = field(default_factory=list)

    def send(self, delivery):
        self.messages.append(delivery)
        return True


@pytest.fixture
def recovery_client(engine):
    app = create_app(
        Settings(
            jwt_secret=SecretStr(SECRET),
            recovery_enabled=True,
            recovery_frontend_url="https://frontend.example/recover",
            smtp_host="smtp.example",
            smtp_from="accounts@example.com",
            recovery_rate_limit=100,
            auth_rate_limit=100,
        ),
        engine,
    )
    app.state.mailer = Mailbox()
    with TestClient(app) as client:
        yield client, app.state.mailer


def enroll(client, mailbox, auth):
    result = client.put(
        "/auth/recovery-address",
        headers=bearer(auth),
        json={
            "email": "person@example.com",
            "password": PASSWORD,
        },
    )
    assert result.status_code == 202
    token = mailbox.messages[-1].token
    assert client.post("/auth/recovery-address/confirm", json={"token": token}).status_code == 204
    return token


def request_reset(client, mailbox):
    result = client.post("/auth/recovery/request", json={"username": "user1"})
    assert result.status_code == 202
    return mailbox.messages[-1].token


def test_recovery_requires_verified_destination_and_never_exposes_tokens(
    recovery_client, engine, caplog
):
    client, mailbox = recovery_client
    auth = login(client)
    absent = client.post("/auth/recovery/request", json={"username": "absent"})
    unenrolled = client.post("/auth/recovery/request", json={"username": "user1"})
    assert absent.status_code == unenrolled.status_code == 202
    assert absent.json() == unenrolled.json() and mailbox.messages == []
    assert (
        client.put(
            "/auth/recovery-address",
            headers=bearer(auth),
            json={
                "email": "person@example.com",
                "password": "wrong",
            },
        ).status_code
        == 401
    )
    result = client.put(
        "/auth/recovery-address",
        headers=bearer(auth),
        json={
            "email": "person@example.com",
            "password": PASSWORD,
        },
    )
    token = mailbox.messages[-1].token
    assert token not in result.text
    client.post("/auth/recovery/request", json={"username": "user1"})
    assert len(mailbox.messages) == 1
    with engine.connect() as connection:
        digest, used = connection.exec_driver_sql(
            "SELECT token_hash,used_at FROM recovery_tokens"
        ).one()
        assert digest == token_hash(token) and used is None
        assert connection.exec_driver_sql("SELECT email FROM recovery_addresses").scalar() is None
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": token, "new_password": "NewPassword2!"}
        ).status_code
        == 400
    )
    assert client.post("/auth/recovery-address/confirm", json={"token": token}).status_code == 204
    assert client.post("/auth/recovery-address/confirm", json={"token": token}).status_code == 400
    reset = request_reset(client, mailbox)
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": reset, "new_password": "NewPassword2!"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": reset, "new_password": "OtherPassword3!"}
        ).status_code
        == 400
    )
    assert client.get("/profile/", headers=bearer(auth)).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post("/auth/login", json={"username": "user1", "password": PASSWORD}).status_code
        == 401
    )
    login(client, password="NewPassword2!")
    assert token not in caplog.text and reset not in caplog.text
    assert token not in repr(mailbox.messages[0])


def test_recovery_expiration_and_replacement(recovery_client, engine):
    client, mailbox = recovery_client
    auth = login(client)
    enroll(client, mailbox, auth)
    first = request_reset(client, mailbox)
    second = request_reset(client, mailbox)
    assert first != second
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": first, "new_password": "NewPassword2!"}
        ).status_code
        == 400
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE recovery_tokens SET expires_at=?", (int(time.time()) - 1,)
        )
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": second, "new_password": "NewPassword2!"}
        ).status_code
        == 400
    )
    login(client)


def test_recovery_disabled_is_uniform(client):
    for username in ["user1", "missing"]:
        response = client.post("/auth/recovery/request", json={"username": username})
        assert response.status_code == 503
        assert set(response.json()) == {"error"}


def test_recovery_delivery_happens_only_after_successful_commit(recovery_client, engine):
    client, mailbox = recovery_client
    auth = login(client)
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER fail_recovery BEFORE INSERT ON recovery_tokens
            BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    response = client.put(
        "/auth/recovery-address",
        headers=bearer(auth),
        json={
            "email": "person@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 500 and mailbox.messages == []
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM recovery_addresses").scalar() == 0


def test_refresh_rotation_reuse_revokes_family_and_commits(client, engine):
    first = login(client)
    independent = login(client)
    rotated = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    second = rotated.json()
    assert first["refresh_token"] != second["refresh_token"]
    with engine.connect() as connection:
        rows = connection.exec_driver_sql("SELECT token_hash,used_at FROM refresh_tokens").all()
        assert (token_hash(first["refresh_token"]), None) not in rows
        assert token_hash(second["refresh_token"]) in [row[0] for row in rows]
        assert first["refresh_token"] not in repr(rows)
    assert client.get("/profile/", headers=bearer(second)).status_code == 200
    assert (
        client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    for auth in [first, second]:
        assert client.get("/profile/", headers=bearer(auth)).status_code == 401
        assert (
            client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
            == 401
        )
    assert client.get("/profile/", headers=bearer(independent)).status_code == 200


def test_simultaneous_refresh_is_single_use(client):
    auth = login(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/auth/refresh",
                    json={
                        "refresh_token": auth["refresh_token"],
                    },
                ),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert client.get("/profile/", headers=bearer(winner)).status_code == 401


def test_logout_and_logout_all(client):
    first, second = login(client), login(client)
    assert client.post("/auth/logout", headers=bearer(first)).status_code == 204
    assert client.get("/profile/", headers=bearer(first)).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    assert client.get("/profile/", headers=bearer(second)).status_code == 200
    third = login(client)
    assert client.post("/auth/logout-all", headers=bearer(third)).status_code == 204
    for auth in [second, third]:
        assert client.get("/profile/", headers=bearer(auth)).status_code == 401


def test_password_change_revokes_sessions_and_pending_recovery(recovery_client):
    client, mailbox = recovery_client
    first, second = login(client), login(client)
    enroll(client, mailbox, first)
    token = request_reset(client, mailbox)
    assert (
        client.put(
            "/profile/password",
            headers=bearer(first),
            json={
                "old_password": PASSWORD,
                "new_password": "NewPassword2!",
            },
        ).status_code
        == 200
    )
    for auth in [first, second]:
        assert client.get("/profile/", headers=bearer(auth)).status_code == 401
        assert (
            client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/recovery/reset", json={"token": token, "new_password": "AnotherPassword3!"}
        ).status_code
        == 400
    )


def test_expired_session_invalidates_access_and_refresh(client, engine):
    auth = login(client)
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE auth_sessions SET expires_at=1")
    assert client.get("/profile/", headers=bearer(auth)).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
        == 401
    )


def test_account_deletion_cleans_owned_data_and_rolls_back_on_failure(recovery_client, engine):
    client, mailbox = recovery_client
    auth = login(client)
    client.headers.update(bearer(auth))
    enroll(client, mailbox, auth)
    client.post(
        "/nutrition/meals",
        json={"date": "2026-01-01", "meal_type": "Lunch", "items": [{"name": "Rice"}]},
    )
    client.put("/nutrition/macros", json={"protein_target": 100})
    client.post(
        "/workouts/",
        json={"workout_name": "Strength", "items": [{"exercise_name": "Bench", "weight": 100}]},
    )
    client.post("/social/friendships", json={"user1_id": 1, "user2_id": 2, "status": "pending"})
    assert client.request("DELETE", "/auth/account", json={"password": "wrong"}).status_code == 401
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER fail_delete BEFORE DELETE ON meal_items
            BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    assert client.request("DELETE", "/auth/account", json={"password": PASSWORD}).status_code == 500
    assert client.get("/profile/").status_code == 200
    assert len(client.get("/nutrition/meals").json()) == 1
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER fail_delete")
    assert client.request("DELETE", "/auth/account", json={"password": PASSWORD}).status_code == 204
    assert client.get("/profile/").status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
        == 401
    )
    with engine.connect() as connection:
        for table in [
            "meals",
            "meal_items",
            "macro_goals",
            "workouts",
            "workout_item",
            "personal_records",
            "friendships",
            "auth_sessions",
            "refresh_tokens",
            "recovery_addresses",
            "recovery_tokens",
        ]:
            assert connection.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM users").scalar() == 8
        assert connection.exec_driver_sql("SELECT count(*) FROM profiles").scalar() == 8
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_recovery_message_sees_committed_hash(recovery_client, engine, monkeypatch):
    client, mailbox = recovery_client
    auth = login(client)
    delivered = []

    def verify_commit(delivery):
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT count(*) FROM recovery_tokens WHERE token_hash=?",
                    (token_hash(delivery.token),),
                ).scalar()
                == 1
            )
        delivered.append(delivery)
        return True

    monkeypatch.setattr(mailbox, "send", verify_commit)
    assert (
        client.put(
            "/auth/recovery-address",
            headers=bearer(auth),
            json={
                "email": "person@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 202
    )
    assert len(delivered) == 1


def test_recovery_commit_failure_does_not_send(recovery_client, engine):
    import sqlite3

    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    client, mailbox = recovery_client
    auth = login(client)

    def reject_recovery_commit(connection):
        if connection.exec_driver_sql("SELECT count(*) FROM recovery_tokens").scalar():
            raise OperationalError("COMMIT", {}, sqlite3.OperationalError("injected"))

    event.listen(engine, "commit", reject_recovery_commit)
    try:
        result = client.put(
            "/auth/recovery-address",
            headers=bearer(auth),
            json={
                "email": "person@example.com",
                "password": PASSWORD,
            },
        )
    finally:
        event.remove(engine, "commit", reject_recovery_commit)
    assert result.status_code == 500 and mailbox.messages == []
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM recovery_tokens").scalar() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM recovery_addresses").scalar() == 0
