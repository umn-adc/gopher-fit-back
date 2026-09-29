"""Revision 0003: weight units, overall workout minutes, and the display unit preference."""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.features.workouts.units import KG_PER_LB, kilograms
from app.main import create_app
from tests.conftest import HASH, PASSWORD, SECRET, migrate
from tests.test_migrations import legacy_database, snapshot, upgrade
from tests.test_workouts import records


def lift(weight, unit="kg", name="Bench Press"):
    return {"exercise_name": name, "weight": weight, "weight_unit": unit}


def log(client, *items, headers=None):
    response = client.post(
        "/workouts/", headers=headers, json={"workout_name": "Strength", "items": list(items)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_conversions():
    assert KG_PER_LB == 0.45359237
    assert kilograms(100, "kg") == 100
    assert kilograms(225, "lb") == pytest.approx(102.05828325)
    assert kilograms(0, "lb") == 0
    assert kilograms(100, None) is None
    assert kilograms(None, "kg") is None


def test_legacy_rows_stay_unknown_and_records_start_empty(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_database(path)
    with sqlite3.connect(path) as connection:
        # Workout 10 holds deliberately malformed Go rows; 11 is readable through the API.
        connection.execute("INSERT INTO workouts VALUES (11, 7, 'Readable', 45)")
        connection.execute("INSERT INTO workout_item VALUES (11, 11, 'Bench Press', 3, 5, 150, 0)")
        before = snapshot(connection)
    upgrade(path, "0002_backend_lifecycle")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM personal_records").fetchone() == (2,)
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {table: after[table] for table in before} == before
        assert after["personal_records"] == []
        assert set(connection.execute("SELECT weight_unit FROM workout_item")) == {(None,)}
        assert connection.execute("SELECT duration_minutes, duration FROM workouts").fetchall() == [
            (None, 30),
            (None, 45),
        ]
        assert connection.execute("SELECT unit_preference FROM profiles").fetchall() == [(None,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE workout_item SET weight_unit='stone' WHERE id=1")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE profiles SET unit_preference='nautical'")

    app = create_app(Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{path}"))
    with TestClient(app) as client:
        token = client.post("/auth/login", json={"username": "legacy", "password": PASSWORD})
        client.headers["Authorization"] = "Bearer " + token.json()["token"]
        assert client.get("/profile/").json()["unit_preference"] == "metric"
        workout = client.get("/workouts/11").json()
        assert workout["duration"] == 45 and workout["duration_minutes"] is None
        assert workout["items"][0]["weight"] == 150
        assert workout["items"][0]["weight_unit"] is None
        assert client.get("/social/leaderboard", params={"exercise": "bench press"}).json() == []
        # Fixing an old item by giving it a unit makes it rank again.
        response = client.put("/workouts/11/items/11", json=lift(150, "lb"))
        assert response.status_code == 204, response.text
        [row] = client.get("/social/leaderboard", params={"exercise": "bench press"}).json()
        assert row["max_weight"] == pytest.approx(150 * KG_PER_LB)


def test_populated_python_database_upgrade_rebuilds_only_records(tmp_path):
    path = tmp_path / "python.db"
    upgrade(path, "0002_backend_lifecycle")
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO users VALUES(1,'existing',?)", (HASH,))
        connection.execute(
            "INSERT INTO profiles(user_id,name,gender,activity_level) "
            "VALUES(1,'Existing','Male','Sedentary')"
        )
        connection.execute(
            "INSERT INTO workouts(id,user_id,workout_name,duration,occurred_at) "
            "VALUES(1,1,'Known',45,'2026-09-01T12:00:00.000000Z')"
        )
        connection.execute("INSERT INTO workout_item VALUES(1,1,'Bench',3,10,100,0)")
        connection.execute("INSERT INTO personal_records VALUES(1,'bench','Bench',100,1)")
        before = snapshot(connection)
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert after["personal_records"] == []
        assert {t: after[t] for t in before if t != "personal_records"} == {
            t: rows for t, rows in before.items() if t != "personal_records"
        }
        assert connection.execute(
            "SELECT occurred_at, duration_minutes FROM workouts"
        ).fetchall() == [("2026-09-01T12:00:00.000000Z", None)]
        assert connection.execute("SELECT weight_unit FROM workout_item").fetchall() == [(None,)]


def test_weight_unit_is_required_for_positive_weights(authed):
    workout = log(authed, lift(100))
    path = f"/workouts/{workout['id']}"
    item = f"{path}/items/{workout['items'][0]['id']}"
    unitless = {"exercise_name": "Bench", "weight": 100}
    for method, url, body in [
        ("post", "/workouts/", {"workout_name": "W", "items": [unitless]}),
        ("post", path + "/items", unitless),
        ("put", item, unitless),
        ("put", path, {"workout_name": "W", "items": [unitless]}),
    ]:
        response = getattr(authed, method)(url, json=body)
        assert response.status_code == 400, (method, url)
        assert response.json() == {
            "error": "weight_unit (kg or lb) is required when weight is positive"
        }
    for bad in ["stone", "KG", "", None, 1]:
        body = {**unitless, "weight_unit": bad}
        assert authed.post(path + "/items", json=body).status_code == 400, bad
    # Unweighted exercises need no unit; a unit on a zero weight is kept.
    cardio = authed.post(path + "/items", json={"exercise_name": "Run", "duration_minutes": 30})
    assert cardio.status_code == 201 and cardio.json()["weight_unit"] is None
    zero = authed.post(path + "/items", json={**lift(0, "lb"), "exercise_name": "Plank"})
    assert zero.json()["weight_unit"] == "lb"
    assert records(authed)[0]["max_weight"] == 100


def test_mixed_units_rank_by_kilograms_and_skip_unknown(authed, engine, headers):
    log(authed, lift(100, "kg"), headers=headers(1))
    log(authed, lift(225, "lb"), headers=headers(2))
    log(authed, lift(200, "lb"), headers=headers(3))
    unknown = log(authed, lift(100, "kg"), headers=headers(4))
    with engine.begin() as connection:
        # A historical lift with no unit, as every pre-0003 row has.
        connection.exec_driver_sql(
            "UPDATE workout_item SET weight=500, weight_unit=NULL WHERE workout_id=?",
            (unknown["id"],),
        )
        connection.exec_driver_sql("DELETE FROM personal_records WHERE user_id=4")
    log(authed, lift(1, "kg", name="Other"), headers=headers(4))
    rows = authed.get("/social/leaderboard", params={"exercise": "bench press"}).json()
    assert [row["user_id"] for row in rows] == [2, 1, 3]
    assert [row["max_weight"] for row in rows] == pytest.approx(
        [225 * KG_PER_LB, 100, 200 * KG_PER_LB]
    )
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert authed.get("/social/muscle-ranks", headers=headers(4)).json()[0]["exercise_key"] == (
        "other"
    )


def test_records_recalculate_when_an_item_unit_changes(authed):
    first = log(authed, lift(100, "kg"))
    second = log(authed, lift(50, "kg"))
    item = first["items"][0]["id"]
    assert records(authed)[0]["source_workout_item_id"] == item
    path = f"/workouts/{first['id']}/items/{item}"
    assert authed.put(path, json=lift(100, "lb")).status_code == 204
    # 100 lb is 45.36 kg, so the 50 kg lift from the other workout becomes the record.
    [record] = records(authed)
    assert record["source_workout_item_id"] == second["items"][0]["id"]
    assert record["max_weight"] == 50
    assert authed.put(path, json=lift(120, "lb")).status_code == 204
    [record] = records(authed)
    assert record["source_workout_item_id"] == item
    assert record["max_weight"] == pytest.approx(120 * KG_PER_LB)
    # Nested replacement follows the same rule.
    nested = {**lift(10, "kg"), "id": item}
    body = {"workout_name": "Strength", "items": [nested]}
    assert authed.put(f"/workouts/{first['id']}", json=body).status_code == 200
    assert records(authed)[0]["max_weight"] == 50


def test_overall_minutes_and_deprecated_duration(authed):
    created = authed.post(
        "/workouts/", json={"workout_name": "Run", "duration_minutes": 42.5}
    ).json()
    assert created["duration_minutes"] == 42.5 and created["duration"] == 0
    path = f"/workouts/{created['id']}"
    legacy = authed.post("/workouts/", json={"workout_name": "Old", "duration": 30}).json()
    assert legacy["duration"] == 30 and legacy["duration_minutes"] is None
    # Omitted fields keep stored values, so writing only new fields keeps legacy data.
    renamed = authed.put(f"/workouts/{legacy['id']}", json={"workout_name": "Renamed"}).json()
    assert renamed["duration"] == 30 and renamed["duration_minutes"] is None
    both = authed.put(
        f"/workouts/{legacy['id']}", json={"workout_name": "Both", "duration_minutes": 25}
    ).json()
    assert both["duration"] == 30 and both["duration_minutes"] == 25
    assert authed.put(path, json={"workout_name": "Run"}).json()["duration_minutes"] == 42.5
    cleared = authed.put(path, json={"workout_name": "Run", "duration_minutes": None}).json()
    assert cleared["duration_minutes"] is None
    replaced = authed.put(path, json={"workout_name": "Run", "duration": 5}).json()
    assert replaced["duration"] == 5
    for bad in [-1, "10"]:
        body = {"workout_name": "Bad", "duration_minutes": bad}
        assert authed.post("/workouts/", json=body).status_code == 400
    spec = authed.get("/swagger/doc.json").json()["components"]["schemas"]
    assert spec["WorkoutRequest"]["properties"]["duration"]["deprecated"] is True
    assert spec["WorkoutResponse"]["properties"]["duration"]["deprecated"] is True


def test_unit_preference_defaults_to_metric_and_is_replaced_with_the_profile(authed, client):
    assert authed.get("/profile/").json()["unit_preference"] == "metric"
    profile = {
        "name": "Units",
        "gender": "Other",
        "activity_level": "Sedentary",
        "unit_preference": "imperial",
    }
    assert authed.put("/profile/", json=profile).json()["unit_preference"] == "imperial"
    assert authed.get("/profile/").json()["unit_preference"] == "imperial"
    # Profile PUT is a full replacement: omitting the preference restores the default.
    del profile["unit_preference"]
    assert authed.put("/profile/", json=profile).json()["unit_preference"] == "metric"
    for bad in ["Imperial", "", None, 1]:
        assert authed.put("/profile/", json={**profile, "unit_preference": bad}).status_code == 400
    registration = {**profile, "username": "imperial", "password": PASSWORD}
    pair = client.post("/auth/register", json={**registration, "unit_preference": "imperial"})
    assert pair.status_code == 201
    token = pair.json()["token"]
    mine = client.get("/profile/", headers={"Authorization": f"Bearer {token}"}).json()
    assert mine["unit_preference"] == "imperial"
