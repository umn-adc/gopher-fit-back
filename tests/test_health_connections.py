"""Apple Health / Health Connect connections, disconnect and imported-data deletion."""

import sqlite3

import pytest

from tests.conftest import PASSWORD, migrate
from tests.test_migrations import legacy_database, snapshot

ALL_TYPES = ["steps", "active_energy", "heart_rate", "resting_heart_rate", "workouts", "weight"]
EMPTY = {
    "connected": False,
    "data_types": [],
    "connected_at": None,
    "last_synced_at": None,
    "synced_days": 0,
    "synced_workouts": 0,
    "synced_weights": 0,
}


def by_provider(client, headers=None):
    response = client.get("/health/connections", headers=headers)
    assert response.status_code == 200, response.text
    return {row["provider"]: row for row in response.json()}


def seed(engine, user_id, provider, last_synced_at="2026-10-01T00:00:00.000000Z"):
    """Imported rows written directly, as a sync would leave them."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO health_daily_activity(user_id, provider, date, steps) VALUES (?, ?, ?, ?)",
            (user_id, provider, "2026-10-01", 5000),
        )
        connection.exec_driver_sql(
            "INSERT INTO health_workouts(user_id, provider, external_id, activity_type, "
            "source_type, start_at, end_at) VALUES (?, ?, 'w1', 'running', 'Running', "
            "'2026-10-01T07:00:00.000000Z', '2026-10-01T07:30:00.000000Z')",
            (user_id, provider),
        )
        connection.exec_driver_sql(
            "INSERT INTO health_weight_samples(user_id, provider, external_id, measured_at, "
            "weight_kg) VALUES (?, ?, 'kg1', '2026-10-01T06:00:00.000000Z', 80.5)",
            (user_id, provider),
        )
        connection.exec_driver_sql(
            "UPDATE health_connections SET last_synced_at=? WHERE user_id=? AND provider=?",
            (last_synced_at, user_id, provider),
        )


def test_both_providers_are_always_listed(authed):
    assert by_provider(authed) == {
        "apple_health": {"provider": "apple_health", **EMPTY},
        "health_connect": {"provider": "health_connect", **EMPTY},
    }


def test_connect_is_idempotent_and_updates_granted_types(authed):
    first = authed.put("/health/connections/apple_health", json={"data_types": ["steps"]})
    assert first.status_code == 200, first.text
    connected = first.json()
    assert connected["connected"] is True and connected["data_types"] == ["steps"]
    assert connected["connected_at"].endswith("Z") and connected["last_synced_at"] is None
    again = authed.put("/health/connections/apple_health", json={"data_types": ALL_TYPES}).json()
    assert again["data_types"] == ALL_TYPES
    assert again["connected_at"] == connected["connected_at"]
    rows = by_provider(authed)
    assert rows["apple_health"] == again
    assert rows["health_connect"] == {"provider": "health_connect", **EMPTY}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data_types": []},
        {"data_types": ["steps", "steps"]},
        {"data_types": ["sleep"]},
        {"data_types": "steps"},
        {"data_types": None},
    ],
)
def test_connect_validation(authed, body):
    assert authed.put("/health/connections/health_connect", json=body).status_code == 400
    assert by_provider(authed)["health_connect"]["connected"] is False


@pytest.mark.parametrize(
    "method, path",
    [
        ("PUT", "/health/connections/google_fit"),
        ("DELETE", "/health/connections/fitbit"),
        ("DELETE", "/health/connections/APPLE_HEALTH/data"),
    ],
)
def test_unknown_provider_is_invalid(authed, method, path):
    response = authed.request(method, path, json={"data_types": ["steps"]})
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid provider"}


def test_routes_require_auth_but_probes_stay_public(client):
    for method, path in [
        ("GET", "/health/connections"),
        ("PUT", "/health/connections/apple_health"),
        ("DELETE", "/health/connections/apple_health/data"),
    ]:
        response = client.request(method, path, json={})
        assert response.status_code == 401, path
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_responses_are_not_cached(authed):
    assert authed.get("/health/connections").headers["Cache-Control"] == "no-store"
    assert "Cache-Control" not in authed.get("/health/live").headers


def test_disconnect_keeps_imported_data_and_stops_syncing(authed, engine):
    authed.put("/health/connections/health_connect", json={"data_types": ALL_TYPES})
    seed(engine, 1, "health_connect")
    assert by_provider(authed)["health_connect"]["last_synced_at"] is not None
    assert authed.delete("/health/connections/health_connect").status_code == 204
    row = by_provider(authed)["health_connect"]
    assert row == {
        "provider": "health_connect",
        **EMPTY,
        "synced_days": 1,
        "synced_workouts": 1,
        "synced_weights": 1,
    }
    # Idempotent, including for a provider that was never connected.
    assert authed.delete("/health/connections/health_connect").status_code == 204
    assert authed.delete("/health/connections/apple_health").status_code == 204
    assert by_provider(authed)["apple_health"] == {"provider": "apple_health", **EMPTY}


def test_reconnect_starts_a_fresh_backfill(authed, engine):
    authed.put("/health/connections/apple_health", json={"data_types": ["steps"]})
    seed(engine, 1, "apple_health")
    authed.delete("/health/connections/apple_health")
    reconnected = authed.put("/health/connections/apple_health", json={"data_types": ["weight"]})
    body = reconnected.json()
    assert body["connected"] is True and body["data_types"] == ["weight"]
    assert body["last_synced_at"] is None and body["synced_weights"] == 1


def test_delete_data_only_touches_that_provider_and_user(authed, engine, headers):
    other = headers(2)
    for provider in ("apple_health", "health_connect"):
        authed.put(f"/health/connections/{provider}", json={"data_types": ALL_TYPES})
        seed(engine, 1, provider)
    authed.put("/health/connections/apple_health", json={"data_types": ALL_TYPES}, headers=other)
    seed(engine, 2, "apple_health")

    assert authed.delete("/health/connections/apple_health/data").status_code == 204
    mine = by_provider(authed)
    assert mine["apple_health"]["connected"] is True
    assert mine["apple_health"]["last_synced_at"] is None
    assert [mine["apple_health"][f"synced_{kind}"] for kind in ("days", "workouts", "weights")] == [
        0,
        0,
        0,
    ]
    assert mine["health_connect"]["synced_days"] == 1
    assert mine["health_connect"]["last_synced_at"] is not None
    theirs = by_provider(authed, headers=other)["apple_health"]
    assert theirs["synced_workouts"] == 1 and theirs["last_synced_at"] is not None
    # Idempotent, and allowed while disconnected.
    authed.delete("/health/connections/health_connect")
    assert authed.delete("/health/connections/health_connect/data").status_code == 204
    assert authed.delete("/health/connections/health_connect/data").status_code == 204
    assert by_provider(authed)["health_connect"]["synced_weights"] == 0


def test_account_deletion_cascades_health_data(client, engine):
    body = {
        "name": "Deleted",
        "gender": "Other",
        "activity_level": "Sedentary",
        "username": "health-owner",
        "password": PASSWORD,
    }
    registered = client.post("/auth/register", json=body).json()
    owner = {"Authorization": f"Bearer {registered['token']}"}
    client.put("/health/connections/apple_health", json={"data_types": ALL_TYPES}, headers=owner)
    seed(engine, registered["user_id"], "apple_health")
    survivor = client.post("/auth/login", json={"username": "user2", "password": PASSWORD})
    kept = {"Authorization": "Bearer " + survivor.json()["token"]}
    client.put("/health/connections/apple_health", json={"data_types": ALL_TYPES}, headers=kept)
    seed(engine, 2, "apple_health")
    response = client.request("DELETE", "/auth/account", headers=owner, json={"password": PASSWORD})
    assert response.status_code == 204
    with engine.connect() as connection:
        for table in (
            "health_connections",
            "health_daily_activity",
            "health_workouts",
            "health_weight_samples",
        ):
            owners = connection.exec_driver_sql(f"SELECT DISTINCT user_id FROM {table}").all()
            assert owners == [(2,)], table
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_upgrade_adds_empty_health_tables_and_keeps_existing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    before = legacy_database(path)
    migrate(path)
    tables = ["health_connections", "health_daily_activity", "health_workouts"]
    tables.append("health_weight_samples")
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {table: after[table] for table in before} == before
        assert all(after[table] == [] for table in tables)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO health_connections VALUES (7, 'apple_health', 1, '[]', NULL, NULL)"
        )
        connection.execute(
            "INSERT INTO health_weight_samples(user_id, provider, external_id, measured_at, "
            "weight_kg) VALUES (7, 'apple_health', 'a', '2026-10-01T00:00:00.000000Z', 80)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO health_connections VALUES (999, 'apple_health', 1, '[]', NULL, NULL)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO health_weight_samples(user_id, provider, external_id, measured_at, "
                "weight_kg) VALUES (7, 'apple_health', 'a', '2026-10-02T00:00:00.000000Z', 81)"
            )
        connection.execute("DELETE FROM users WHERE id=7")
        assert all(
            connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
            for table in tables
        )
