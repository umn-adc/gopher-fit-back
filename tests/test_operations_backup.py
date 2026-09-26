import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.middleware import JsonFormatter
from app.features.auth.delivery import Delivery, RecoveryMailer
from app.main import create_app
from scripts.backup import backup, restore
from tests.conftest import PASSWORD, SECRET, migrate


def test_liveness_and_readiness_detect_revision_drift(client, engine):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num='outdated'")
    response = client.get("/health/ready")
    assert response.status_code == 503 and response.json() == {"error": "Not ready"}
    assert client.get("/health/live").status_code == 200
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")
    assert client.get("/health/ready").status_code == 503


def test_metrics_request_ids_cors_and_redacted_logs(engine, caplog):
    metrics_token = "private-metrics-token-at-least-32-characters"
    app = create_app(
        Settings(
            jwt_secret=SecretStr(SECRET),
            metrics_token=SecretStr(metrics_token),
            cors_origins=["https://front.example"],
        ),
        engine,
    )
    with TestClient(app) as client:
        response = client.get(
            "/health/live?secret=do-not-log",
            headers={"X-Request-ID": "test-request", "Origin": "https://front.example"},
        )
        assert response.headers["X-Request-ID"] == "test-request"
        assert response.headers["Access-Control-Allow-Origin"] == "https://front.example"
        assert (
            client.get("/health/live", headers={"X-Request-ID": "unsafe\nvalue"}).headers[
                "X-Request-ID"
            ]
            != "unsafe\nvalue"
        )
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get("/metrics", headers={"Authorization": f"Bearer {metrics_token}"})
        assert response.status_code == 200
        assert 'route="/health/live",status="200"' in response.text
        assert "do-not-log" not in response.text and metrics_token not in response.text
        result = client.options(
            "/auth/login",
            headers={
                "Origin": "https://front.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert result.status_code == 200
        result = client.get("/profile/", headers={"Origin": "https://front.example"})
        assert (
            result.status_code == 401
            and result.headers["Access-Control-Allow-Origin"] == "https://front.example"
        )
        assert (
            "Access-Control-Allow-Origin"
            not in client.get(
                "/health/live", headers={"Origin": "https://untrusted.example"}
            ).headers
        )
    logs = [record for record in caplog.records if record.name.startswith("gopher")]
    assert logs
    rendered = [json.loads(JsonFormatter().format(record)) for record in logs]
    assert any(record.get("request_id") == "test-request" for record in rendered)
    assert "do-not-log" not in json.dumps(rendered) and metrics_token not in json.dumps(rendered)


def test_metrics_disabled_by_default(client):
    assert client.get("/metrics").status_code == 404


def test_rate_limit_is_shared_across_workers_counts_failures_and_ignores_untrusted_forwarding(
    engine, monkeypatch
):
    monkeypatch.setattr("app.features.operations.service.time.time", lambda: 6000)
    settings = Settings(jwt_secret=SecretStr(SECRET), auth_rate_limit=2, recovery_rate_limit=1)
    other_engine = create_database_engine(str(engine.url))
    try:
        with (
            TestClient(create_app(settings, engine)) as first,
            TestClient(create_app(settings, other_engine)) as second,
        ):
            for client in [first, second]:
                assert (
                    client.post(
                        "/auth/login", json={"username": "missing", "password": "wrong"}
                    ).status_code
                    == 401
                )
            response = first.post(
                "/auth/login",
                headers={"X-Forwarded-For": "192.0.2.1"},
                json={"username": "user1", "password": PASSWORD},
            )
            assert response.status_code == 429 and response.headers["Retry-After"] == "60"
            # Recovery has an independent bucket; even a disabled request consumes its budget.
            assert (
                first.post("/auth/recovery/request", json={"username": "user1"}).status_code == 503
            )
            assert (
                second.post("/auth/recovery/request", json={"username": "user2"}).status_code == 429
            )
            monkeypatch.setattr("app.features.operations.service.time.time", lambda: 6060)
            assert (
                second.post(
                    "/auth/login", json={"username": "missing", "password": "wrong"}
                ).status_code
                == 401
            )
    finally:
        other_engine.dispose()


def test_rate_limit_is_atomic_under_concurrent_requests(engine):
    app = create_app(
        Settings(jwt_secret=SecretStr(SECRET), auth_rate_limit=2, rate_limit_window_seconds=3600),
        engine,
    )
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(
                lambda _: (
                    client.post(
                        "/auth/login", json={"username": "missing", "password": "wrong"}
                    ).status_code
                ),
                range(4),
            )
        )
    assert sorted(statuses) == [401, 401, 429, 429]


def test_smtp_requires_tls_and_failures_do_not_log_secrets(monkeypatch, caplog):
    settings = Settings(
        jwt_secret=SecretStr(SECRET),
        recovery_enabled=True,
        smtp_host="smtp.example",
        smtp_from="accounts@example.com",
        recovery_frontend_url="https://front.example/recover",
    )
    calls = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, **kwargs):
            calls.append("tls")

        def send_message(self, message):
            calls.append("send")
            assert "#purpose=reset&token=private-token" in message.get_content()
            raise OSError("do-not-log person@example.com private-token")

    monkeypatch.setattr("app.features.auth.delivery.smtplib.SMTP", FakeSMTP)
    assert (
        RecoveryMailer(settings).send(Delivery("person@example.com", "private-token", "reset"))
        is False
    )
    assert calls == ["tls", "send"]
    assert "private-token" not in caplog.text and "person@example.com" not in caplog.text
    assert "recovery_delivery_failed" in caplog.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"recovery_enabled": True},
        {"cors_origins": ["*"]},
        {"metrics_token": "short"},
        {
            "recovery_enabled": True,
            "smtp_host": "smtp.example",
            "smtp_from": "accounts@example.com",
            "recovery_frontend_url": "http://front.example/recover",
        },
    ],
)
def test_insecure_operational_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(jwt_secret=SecretStr(SECRET), **overrides)


def test_backup_wal_retention_and_verified_restore(engine, tmp_path):
    database = Path(engine.url.database)
    writer = sqlite3.connect(database)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO meals(user_id,date,meal_type) VALUES(1,'2026-01-01','Lunch')")
        writer.commit()
        assert Path(str(database) + "-wal").stat().st_size > 0
        directory = tmp_path / "backups"
        first = backup(str(engine.url), directory, keep=2)
        unrelated = directory / "unrelated.sqlite3"
        unrelated.write_text("keep this")
        second = backup(str(engine.url), directory, keep=2)
        third = backup(str(engine.url), directory, keep=2)
        assert not first.exists() and second.exists() and third.exists() and unrelated.exists()
        if os.name == "posix":
            assert third.stat().st_mode & 0o777 == 0o600
        restored = tmp_path / "restored.db"
        restore(third, restored)
        with pytest.raises(FileExistsError):
            restore(third, restored)
        with sqlite3.connect(restored) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("SELECT date FROM meals").fetchone() == ("2026-01-01",)
        migrate(restored)
        with TestClient(
            create_app(Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{restored}"))
        ) as client:
            auth = client.post(
                "/auth/login", json={"username": "user1", "password": PASSWORD}
            ).json()
            client.headers["Authorization"] = "Bearer " + auth["token"]
            assert client.get("/health/ready").status_code == 200
            assert client.get("/nutrition/meals").json()[0]["meal_type"] == "Lunch"
    finally:
        writer.close()


def test_failed_backup_keeps_last_snapshot_and_restore_rejects_bad_source(engine, tmp_path):
    directory = tmp_path / "snapshots"
    saved = backup(str(engine.url), directory, keep=1)
    with pytest.raises(ValueError, match="does not exist"):
        backup(f"sqlite:///{tmp_path / 'absent.db'}", directory, keep=1)
    assert saved.exists()
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_text("not SQLite")
    with pytest.raises(sqlite3.DatabaseError):
        restore(corrupt, tmp_path / "bad-restore.db")
    assert not (tmp_path / "bad-restore.db").exists()
    assert not list(tmp_path.glob(".snapshot-*"))


def test_restore_does_not_revive_access_refresh_or_recovery_tokens(engine, tmp_path):
    from tests.test_account_lifecycle import bearer, login

    with TestClient(create_app(Settings(jwt_secret=SecretStr(SECRET)), engine)) as client:
        auth = login(client)
        assert client.get("/profile/", headers=bearer(auth)).status_code == 200
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO recovery_tokens VALUES('hash',1,'reset',9999999999,NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO recovery_addresses VALUES(1,'verified@example.com','pending@example.com')"
        )
    saved = backup(str(engine.url), tmp_path / "snapshots")
    restored = tmp_path / "safe-restore.db"
    restore(saved, restored)
    with sqlite3.connect(saved) as connection:
        assert connection.execute("SELECT revoked_at FROM auth_sessions").fetchone() == (None,)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT revoked_at FROM auth_sessions").fetchone()[0] is not None
        assert connection.execute("SELECT used_at FROM recovery_tokens").fetchone()[0] is not None
        assert connection.execute(
            "SELECT email,pending_email FROM recovery_addresses"
        ).fetchone() == ("verified@example.com", None)
    with TestClient(
        create_app(Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{restored}"))
    ) as client:
        assert client.get("/profile/", headers=bearer(auth)).status_code == 401
        assert (
            client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]}).status_code
            == 401
        )
        login(client)
