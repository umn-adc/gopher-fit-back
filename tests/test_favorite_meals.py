"""Reusable favorite meal templates (D7)."""

import sqlite3

import pytest

from tests.conftest import PASSWORD, migrate
from tests.test_migrations import legacy_database, snapshot

RICE = {"name": "Rice", "calories": 200, "protein": 4, "carbs": 45, "fat": 1}
EGGS = {"name": "Eggs", "calories": 150, "protein": 12, "carbs": 1, "fat": 10}
FAVORITE = {"name": "Usual breakfast", "meal_type": "Breakfast", "items": [RICE, EGGS]}


def create(client, body=FAVORITE, headers=None):
    response = client.post("/nutrition/favorites", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_favorite_crud_round_trip(authed):
    favorite = create(authed)
    assert favorite["name"] == "Usual breakfast" and favorite["meal_type"] == "Breakfast"
    assert favorite["total_calories"] == 350
    assert [item["name"] for item in favorite["items"]] == ["Rice", "Eggs"]
    assert {item["favorite_id"] for item in favorite["items"]} == {favorite["id"]}
    path = f"/nutrition/favorites/{favorite['id']}"
    assert authed.get(path).json() == favorite
    empty = create(authed, {"name": "Empty", "meal_type": "Snack"})
    assert empty["items"] == [] and empty["total_calories"] == 0
    assert [row["id"] for row in authed.get("/nutrition/favorites").json()] == [
        favorite["id"],
        empty["id"],
    ]
    page = authed.get("/nutrition/favorites", params={"limit": 1, "offset": 1}).json()
    assert [row["id"] for row in page] == [empty["id"]]

    # Omitted items are kept; a list replaces them all.
    renamed = authed.put(path, json={"name": "Weekday", "meal_type": "Brunch"}).json()
    assert renamed["name"] == "Weekday" and renamed["items"] == favorite["items"]
    replaced = authed.put(path, json={"name": "Weekday", "meal_type": "Brunch", "items": [EGGS]})
    assert [item["name"] for item in replaced.json()["items"]] == ["Eggs"]
    assert replaced.json()["total_calories"] == 150
    cleared = authed.put(path, json={"name": "Weekday", "meal_type": "Brunch", "items": []})
    assert cleared.json()["items"] == []
    assert authed.delete(path).status_code == 204
    assert authed.get(path).status_code == 404
    assert authed.delete(path).status_code == 404


def test_logging_creates_an_independent_dated_meal(authed):
    favorite = create(authed)
    path = f"/nutrition/favorites/{favorite['id']}/log"
    meal = authed.post(path, json={"date": "2026-09-29", "time": "07:30"})
    assert meal.status_code == 201, meal.text
    logged = meal.json()
    assert logged["date"] == "2026-09-29" and logged["time"] == "07:30"
    assert logged["meal_type"] == "Breakfast" and logged["total_calories"] == 350
    assert [(item["name"], item["protein"]) for item in logged["items"]] == [
        ("Rice", 4),
        ("Eggs", 12),
    ]
    override = authed.post(path, json={"date": "2026-09-30", "meal_type": "Dinner"}).json()
    assert override["meal_type"] == "Dinner" and override["time"] == ""
    # Editing or deleting the template never changes meals already logged from it.
    authed.put(f"/nutrition/favorites/{favorite['id']}", json={**FAVORITE, "items": []})
    authed.delete(f"/nutrition/favorites/{favorite['id']}")
    assert authed.get(f"/nutrition/meals/{logged['id']}").json() == logged
    summary = authed.get("/nutrition/summary", params={"date": "2026-09-29"}).json()
    assert summary["calories"] == 350
    empty = create(authed, {"name": "Nothing", "meal_type": "Snack"})
    bare = authed.post(f"/nutrition/favorites/{empty['id']}/log", json={"date": "2026-09-29"})
    assert bare.status_code == 201 and "items" not in bare.json()


@pytest.mark.parametrize(
    "body",
    [
        {"name": " ", "meal_type": "Lunch"},
        {"name": "Lunch"},
        {"name": "Lunch", "meal_type": ""},
        {"name": "Lunch", "meal_type": "Lunch", "items": [{"name": "Bad", "calories": -1}]},
        {"name": "Lunch", "meal_type": "Lunch", "items": [{"calories": 1}]},
        {"name": "x" * 201, "meal_type": "Lunch"},
        {"name": "Lunch", "meal_type": "Lunch", "items": [RICE] * 501},
    ],
)
def test_favorite_validation(authed, body):
    assert authed.post("/nutrition/favorites", json=body).status_code == 400
    favorite = create(authed)
    assert authed.put(f"/nutrition/favorites/{favorite['id']}", json=body).status_code == 400
    assert authed.get(f"/nutrition/favorites/{favorite['id']}").json() == favorite


@pytest.mark.parametrize(
    "body", [{}, {"date": "2026-02-30"}, {"date": "2026-09-29", "time": "25:00"}]
)
def test_log_validation(authed, body):
    favorite = create(authed)
    response = authed.post(f"/nutrition/favorites/{favorite['id']}/log", json=body)
    assert response.status_code == 400
    assert authed.get("/nutrition/meals").json() == []


def test_favorites_are_private_to_their_owner(authed, headers):
    mine = create(authed)
    other = headers(2)
    path = f"/nutrition/favorites/{mine['id']}"
    assert authed.get("/nutrition/favorites", headers=other).json() == []
    assert authed.get(path, headers=other).status_code == 404
    assert authed.put(path, headers=other, json=FAVORITE).status_code == 404
    assert authed.delete(path, headers=other).status_code == 404
    logged = authed.post(path + "/log", headers=other, json={"date": "2026-09-29"})
    assert logged.status_code == 404
    assert authed.get("/nutrition/meals", headers=other).json() == []
    assert authed.get(path).json() == mine
    for invalid in ["0", "-1", "abc"]:
        assert authed.get(f"/nutrition/favorites/{invalid}").status_code == 400


def test_account_deletion_cascades_favorites(client, engine):
    body = {
        "name": "Deleted",
        "gender": "Other",
        "activity_level": "Sedentary",
        "username": "favorite-owner",
        "password": PASSWORD,
    }
    token = client.post("/auth/register", json=body).json()["token"]
    owner = {"Authorization": f"Bearer {token}"}
    create(client, headers=owner)
    survivor = client.post("/auth/login", json={"username": "user2", "password": PASSWORD})
    kept = create(client, headers={"Authorization": "Bearer " + survivor.json()["token"]})
    response = client.request("DELETE", "/auth/account", headers=owner, json={"password": PASSWORD})
    assert response.status_code == 204
    with engine.connect() as connection:
        favorites = connection.exec_driver_sql("SELECT id FROM favorite_meals").all()
        assert favorites == [(kept["id"],)]
        items = connection.exec_driver_sql("SELECT favorite_id FROM favorite_meal_items").all()
        assert set(items) == {(kept["id"],)}
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_upgrade_adds_empty_tables_and_keeps_existing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    before = legacy_database(path)
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert {table: after[table] for table in before} == before
        assert after["favorite_meals"] == [] and after["favorite_meal_items"] == []
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO favorite_meals VALUES (1, 7, 'Kept', 'Lunch')")
        connection.execute("INSERT INTO favorite_meal_items VALUES (1, 1, 'Rice', 1, 2, 3, 4)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO favorite_meals VALUES (2, 999, 'Orphan', 'Lunch')")
        connection.execute("DELETE FROM users WHERE id=7")
        assert connection.execute("SELECT count(*) FROM favorite_meal_items").fetchone() == (0,)
