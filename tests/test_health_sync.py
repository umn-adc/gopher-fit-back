"""Uploading windows of Apple Health / Health Connect data (POST .../sync)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import StorageFailure
from app.features.health.repository import HealthRepository
from app.main import create_app
from tests.conftest import SECRET
from tests.test_health_connections import ALL_TYPES, by_provider

SYNC = "/health/connections/{}/sync"
SINCE, UNTIL = "2026-09-01T05:00:00Z", "2026-09-08T05:00:00Z"


def day(date, **values):
    return {"date": date, **values}


def workout(external_id, start="2026-09-02T12:00:00Z", minutes=30, **values):
    started = datetime.fromisoformat(start)
    return {
        "external_id": external_id,
        "activity_type": "running",
        "source_type": "HKWorkoutActivityTypeRunning",
        "start_at": start,
        "end_at": (started + timedelta(minutes=minutes)).isoformat(),
        **values,
    }


def weight(external_id, at="2026-09-02T06:00:00Z", kg=80.0):
    return {"external_id": external_id, "measured_at": at, "weight_kg": kg}


def body(**overrides):
    return {
        "since": SINCE,
        "until": UNTIL,
        "data_types": ALL_TYPES,
        "daily": [
            day(
                "2026-09-01",
                steps=8000,
                active_energy_kcal=420.5,
                resting_heart_rate_bpm=58,
                heart_rate_min_bpm=52,
                heart_rate_avg_bpm=71.5,
                heart_rate_max_bpm=160,
            ),
            day("2026-09-02", steps=0, active_energy_kcal=0),
        ],
        "workouts": [
            workout(
                "w1",
                energy_kcal=300,
                avg_heart_rate_bpm=140,
                max_heart_rate_bpm=171,
                source_name="Apple Watch",
            ),
            workout("w2", "2026-09-03T18:00:00-05:00", activity_type="yoga"),
        ],
        "weights": [weight("kg1"), weight("kg2", "2026-09-05T06:30:00+02:00", 79.6)],
        **overrides,
    }


def connect(client, provider="apple_health", types=ALL_TYPES, headers=None):
    response = client.put(
        f"/health/connections/{provider}", json={"data_types": types}, headers=headers
    )
    assert response.status_code == 200, response.text


def sync(client, provider="apple_health", headers=None, **overrides):
    return client.post(SYNC.format(provider), json=body(**overrides), headers=headers)


def rows(engine, table, columns, user_id=1):
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            f"SELECT {columns} FROM {table} WHERE user_id=? ORDER BY 1", (user_id,)
        ).all()


def test_sync_requires_a_connection(authed):
    assert sync(authed).status_code == 409
    assert sync(authed).json() == {"error": "Health source is not connected"}
    connect(authed)
    authed.delete("/health/connections/apple_health")
    assert sync(authed).status_code == 409
    assert by_provider(authed)["apple_health"]["synced_days"] == 0


def test_first_sync_stores_every_type(authed, engine):
    connect(authed)
    response = sync(authed)
    assert response.status_code == 200, response.text
    connection = response.json()
    assert connection["last_synced_at"] == "2026-09-08T05:00:00Z"
    assert [connection[f"synced_{kind}"] for kind in ("days", "workouts", "weights")] == [2, 2, 2]
    assert by_provider(authed)["apple_health"] == connection
    assert rows(
        engine,
        "health_daily_activity",
        "date, provider, steps, active_energy_kcal, resting_heart_rate_bpm, "
        "heart_rate_min_bpm, heart_rate_avg_bpm, heart_rate_max_bpm",
    ) == [
        ("2026-09-01", "apple_health", 8000, 420.5, 58.0, 52.0, 71.5, 160.0),
        ("2026-09-02", "apple_health", 0, 0.0, None, None, None, None),
    ]
    assert rows(
        engine,
        "health_workouts",
        "external_id, activity_type, source_type, start_at, end_at, energy_kcal, "
        "avg_heart_rate_bpm, max_heart_rate_bpm, source_name",
    ) == [
        (
            "w1",
            "running",
            "HKWorkoutActivityTypeRunning",
            "2026-09-02T12:00:00.000000Z",
            "2026-09-02T12:30:00.000000Z",
            300.0,
            140.0,
            171.0,
            "Apple Watch",
        ),
        (
            "w2",
            "yoga",
            "HKWorkoutActivityTypeRunning",
            "2026-09-03T23:00:00.000000Z",
            "2026-09-03T23:30:00.000000Z",
            None,
            None,
            None,
            None,
        ),
    ]
    assert rows(engine, "health_weight_samples", "external_id, measured_at, weight_kg") == [
        ("kg1", "2026-09-02T06:00:00.000000Z", 80.0),
        ("kg2", "2026-09-05T04:30:00.000000Z", 79.6),
    ]
    # Nothing leaks into logged workouts, records or the profile.
    assert authed.get("/workouts/").json() == []
    assert authed.get("/profile/").json()["weight"] == 70


def test_resending_a_window_is_idempotent(authed, engine):
    connect(authed)
    first = sync(authed).json()
    tables = {
        "health_daily_activity": "date, steps, heart_rate_avg_bpm",
        "health_workouts": "external_id, start_at, energy_kcal",
        "health_weight_samples": "external_id, measured_at, weight_kg",
    }
    before = {table: rows(engine, table, columns) for table, columns in tables.items()}
    assert sync(authed).json() == first
    assert {table: rows(engine, table, columns) for table, columns in tables.items()} == before


def test_window_replaces_edits_and_deletions_but_not_other_windows(authed, engine):
    connect(authed)
    earlier = {
        "since": "2026-08-20T00:00:00Z",
        "until": SINCE,
        "daily": [day("2026-08-25", steps=100)],
        "workouts": [workout("old", "2026-08-25T10:00:00Z")],
        "weights": [weight("old-kg", "2026-08-25T06:00:00Z", 82)],
    }
    assert sync(authed, **earlier).status_code == 200
    assert sync(authed).status_code == 200
    # w2 and kg2 were deleted at the source, w1 and kg1 edited, day 2 corrected.
    edited = sync(
        authed,
        daily=[day("2026-09-02", steps=1200, active_energy_kcal=55)],
        workouts=[workout("w1", energy_kcal=310)],
        weights=[weight("kg1", kg=79.9)],
    )
    assert edited.status_code == 200, edited.text
    assert [edited.json()[f"synced_{kind}"] for kind in ("days", "workouts", "weights")] == [
        3,
        2,
        2,
    ]
    assert rows(engine, "health_workouts", "external_id, energy_kcal") == [
        ("old", None),
        ("w1", 310.0),
    ]
    assert rows(engine, "health_weight_samples", "external_id, weight_kg") == [
        ("kg1", 79.9),
        ("old-kg", 82.0),
    ]
    assert rows(engine, "health_daily_activity", "date, steps, active_energy_kcal") == [
        ("2026-08-25", 100, None),
        ("2026-09-01", 8000, 420.5),
        ("2026-09-02", 1200, 55.0),
    ]


def test_a_session_moved_into_a_later_window_is_replaced_not_duplicated(authed, engine):
    connect(authed)
    sync(authed, workouts=[workout("w1")], weights=[weight("kg1")])
    later = {
        "since": UNTIL,
        "until": "2026-09-10T00:00:00Z",
        "daily": [],
        "workouts": [workout("w1", "2026-09-09T07:00:00Z")],
        "weights": [weight("kg1", "2026-09-09T06:00:00Z", 81)],
    }
    response = sync(authed, **later)
    assert response.status_code == 200, response.text
    assert rows(engine, "health_workouts", "external_id, start_at") == [
        ("w1", "2026-09-09T07:00:00.000000Z")
    ]
    assert rows(engine, "health_weight_samples", "external_id, weight_kg") == [("kg1", 81.0)]


def test_a_partial_sync_leaves_other_types_alone(authed, engine):
    connect(authed)
    sync(authed)
    partial = sync(
        authed,
        data_types=["steps"],
        daily=[day("2026-09-01", steps=9000, resting_heart_rate_bpm=99, heart_rate_avg_bpm=99)],
        workouts=[],
        weights=[],
    )
    assert partial.status_code == 200, partial.text
    assert rows(
        engine, "health_daily_activity", "date, steps, active_energy_kcal, resting_heart_rate_bpm"
    ) == [("2026-09-01", 9000, 420.5, 58.0), ("2026-09-02", 0, 0.0, None)]
    assert len(rows(engine, "health_workouts", "id")) == 2
    assert len(rows(engine, "health_weight_samples", "id")) == 2


def test_workout_heart_rate_needs_the_heart_rate_type(authed, engine):
    connect(authed, "health_connect", ["workouts"])
    response = sync(
        authed,
        "health_connect",
        data_types=["workouts"],
        workouts=[workout("hc-1", avg_heart_rate_bpm=120, max_heart_rate_bpm=150, energy_kcal=9)],
    )
    assert response.status_code == 200, response.text
    assert rows(
        engine, "health_workouts", "provider, energy_kcal, avg_heart_rate_bpm, max_heart_rate_bpm"
    ) == [("health_connect", 9.0, None, None)]
    assert rows(engine, "health_daily_activity", "id") == []
    assert rows(engine, "health_weight_samples", "id") == []


def test_only_connected_types_can_be_synced(authed):
    connect(authed, types=["steps"])
    response = sync(authed, data_types=["steps", "weight"])
    assert response.status_code == 400
    assert response.json() == {"error": "Data type is not connected"}
    assert by_provider(authed)["apple_health"]["last_synced_at"] is None


def test_last_synced_at_is_capped_at_server_time(authed):
    connect(authed)
    now = datetime.now(UTC)
    response = sync(
        authed,
        since=(now - timedelta(days=2)).isoformat(),
        until=(now + timedelta(hours=1)).isoformat(),
        daily=[],
        workouts=[],
        weights=[],
    )
    assert response.status_code == 200, response.text
    synced = datetime.fromisoformat(response.json()["last_synced_at"])
    assert now <= synced <= datetime.now(UTC)


INVALID = [
    ({"since": UNTIL, "until": SINCE}, "Sync window must end after it starts"),
    ({"since": SINCE, "until": SINCE}, "Sync window must end after it starts"),
    (
        {"since": "2026-08-01T00:00:00Z", "until": "2026-09-01T00:00:01Z"},
        "Sync window is longer than 31 days",
    ),
    (
        {"since": "2099-01-01T00:00:00Z", "until": "2099-01-02T00:00:00Z"},
        "Sync window ends in the future",
    ),
    ({"daily": [day("2026-08-30")]}, "Daily date is outside the sync window"),
    ({"daily": [day("2026-09-10")]}, "Daily date is outside the sync window"),
    ({"daily": [day("2026-09-01"), day("2026-09-01")]}, "Duplicate daily date"),
    ({"workouts": [workout("w"), workout("w", "2026-09-04T00:00:00Z")]}, None),
    ({"weights": [weight("k"), weight("k", "2026-09-04T00:00:00Z")]}, None),
    (
        {"workouts": [workout("early", "2026-09-01T04:59:59Z")]},
        "A workout is outside the sync window",
    ),
    ({"workouts": [workout("late", UNTIL)]}, "A workout is outside the sync window"),
    ({"weights": [weight("late", UNTIL)]}, "A weight is outside the sync window"),
    ({"since": "2026-09-01T05:00:00"}, "Invalid JSON"),
    ({"data_types": []}, "Invalid JSON"),
    ({"daily": [day("2026-09-31")]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", steps=200_001)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", steps=1.5)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", active_energy_kcal=-1)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", resting_heart_rate_bpm=19)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", heart_rate_max_bpm=251)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", heart_rate_min_bpm=90, heart_rate_avg_bpm=80)]}, "Invalid JSON"),
    ({"daily": [day("2026-09-01", heart_rate_avg_bpm=90, heart_rate_max_bpm=80)]}, "Invalid JSON"),
    ({"daily": [day(f"2026-09-{n:02}") for n in range(1, 31)] * 2}, "Invalid JSON"),
    ({"workouts": [workout("zero", minutes=0)]}, "Invalid JSON"),
    ({"workouts": [workout("long", minutes=24 * 60 + 1)]}, "Invalid JSON"),
    ({"workouts": [workout("hr", avg_heart_rate_bpm=150, max_heart_rate_bpm=140)]}, "Invalid JSON"),
    ({"workouts": [workout("x", activity_type="parkour")]}, "Invalid JSON"),
    ({"workouts": [workout(" ")]}, "Invalid JSON"),
    ({"workouts": [workout("w", "2026-09-02T12:00:00")]}, "Invalid JSON"),
    ({"workouts": [workout(str(n)) for n in range(501)]}, "Invalid JSON"),
    ({"weights": [weight("light", kg=19.9)]}, "Invalid JSON"),
    ({"weights": [weight("heavy", kg=400.1)]}, "Invalid JSON"),
    ({"weights": [weight("text", kg="80")]}, "Invalid JSON"),
]


@pytest.mark.parametrize("overrides, error", INVALID)
def test_invalid_sync_writes_nothing(authed, engine, overrides, error):
    connect(authed)
    response = sync(authed, **overrides)
    assert response.status_code == 400, response.text
    if error:
        assert response.json() == {"error": error}
    else:
        assert response.json()["error"].startswith("Duplicate ")
    row = by_provider(authed)["apple_health"]
    synced = [row[f"synced_{kind}"] for kind in ("days", "workouts", "weights")]
    assert row["last_synced_at"] is None and synced == [0, 0, 0]


def test_a_failed_write_rolls_back_the_whole_sync(authed, engine, monkeypatch):
    connect(authed)

    def fail(*_args):
        raise StorageFailure("Disk full")

    monkeypatch.setattr(HealthRepository, "replace_weights", fail)
    assert sync(authed).status_code == 500
    assert rows(engine, "health_daily_activity", "id") == []
    assert rows(engine, "health_workouts", "id") == []
    assert by_provider(authed)["apple_health"]["last_synced_at"] is None


def test_each_account_only_touches_its_own_data(authed, engine, headers):
    other = headers(2)
    connect(authed)
    connect(authed, headers=other)
    sync(authed)
    response = sync(authed, headers=other, workouts=[workout("w1")], weights=[], daily=[])
    assert response.status_code == 200
    assert [row[0] for row in rows(engine, "health_workouts", "external_id")] == ["w1", "w2"]
    assert rows(engine, "health_workouts", "external_id", user_id=2) == [("w1",)]
    assert by_provider(authed)["apple_health"]["synced_weights"] == 2
    assert by_provider(authed, headers=other)["apple_health"]["synced_weights"] == 0


def test_sync_has_its_own_rate_limit_bucket(engine, headers):
    settings = Settings(
        jwt_secret=SecretStr(SECRET),
        health_sync_rate_limit=2,
        rate_limit_window_seconds=3600,
    )
    with TestClient(create_app(settings, engine)) as client:
        auth = headers()
        connect(client, headers=auth)
        for _ in range(2):
            assert sync(client, headers=auth).status_code == 200
        limited = sync(client, headers=auth)
        assert limited.status_code == 429
        assert 0 < int(limited.headers["Retry-After"]) <= 3600
        # Unauthenticated attempts count too; the other health routes are unaffected.
        assert sync(client, "health_connect").status_code == 429
        assert client.get("/health/connections", headers=auth).status_code == 200
        assert client.delete("/health/connections/apple_health", headers=auth).status_code == 204
