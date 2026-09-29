"""Username prefix search for friend discovery (D5)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from tests.conftest import HASH, SECRET


@pytest.fixture
def users(engine):
    def add(*names, profile=True):
        ids = []
        with engine.begin() as connection:
            for name in names:
                user_id = connection.exec_driver_sql(
                    "INSERT INTO users(username, password) VALUES (?, ?) RETURNING id", (name, HASH)
                ).scalar_one()
                if profile:
                    connection.exec_driver_sql(
                        "INSERT INTO profiles(user_id, name, age, height, weight, gender, "
                        "activity_level, goals, sports) "
                        "VALUES (?, ?, 44, 190, 99, 'Female', 'Very Active', '[\"Secret\"]', '[]')",
                        (user_id, f"Name of {name}"),
                    )
                ids.append(user_id)
        return ids

    return add


def search(client, q, headers=None):
    response = client.get("/social/users/search", params={"q": q}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_prefix_is_case_insensitive_and_literal(authed, users):
    alice, alfred, albert, _, underscore, percent = users(
        "Alice", "alfred", "ALBERT", "bob", "al_x", "al%y"
    )
    assert search(authed, "ali") == [{"id": alice, "username": "Alice", "name": "Name of Alice"}]
    assert [row["id"] for row in search(authed, "ALF")] == [alfred]
    assert [row["username"] for row in search(authed, "alb")] == ["ALBERT"]
    # LIKE wildcards in the query match literally.
    assert [row["id"] for row in search(authed, "al_")] == [underscore]
    assert [row["id"] for row in search(authed, "al%")] == [percent]
    assert search(authed, "lic") == []


@pytest.mark.parametrize("q", ["", "ab", "  ", "x" * 201])
def test_query_needs_three_to_two_hundred_characters(authed, q):
    response = authed.get("/social/users/search", params={"q": q})
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid q"}


def test_missing_query_and_authentication(authed):
    assert authed.get("/social/users/search").json() == {"error": "Invalid q"}
    anonymous = {"Authorization": ""}
    response = authed.get("/social/users/search", params={"q": "user"}, headers=anonymous)
    assert response.status_code == 401


def test_results_are_capped_at_twenty_in_name_order(authed, users):
    names = [f"match{index:02d}" for index in reversed(range(25))]
    users(*names)
    rows = search(authed, "MATCH")
    assert [row["username"] for row in rows] == [f"match{index:02d}" for index in range(20)]


def test_self_and_blocks_in_either_direction_are_excluded(authed, headers):
    assert [row["id"] for row in search(authed, "user")] == list(range(2, 10))
    for request in [
        {"user1_id": 1, "user2_id": 2, "status": "blocked"},
        {"user1_id": 1, "user2_id": 4, "status": "pending"},
    ]:
        assert authed.post("/social/friendships", json=request).status_code == 201
    incoming = {"user1_id": 1, "user2_id": 3, "status": "blocked"}
    assert authed.post("/social/friendships", headers=headers(3), json=incoming).status_code == 201
    accepted = {"user1_id": 1, "user2_id": 5, "status": "pending"}
    assert authed.post("/social/friendships", json=accepted).status_code == 201
    accept = {**accepted, "status": "accepted"}
    assert authed.put("/social/friendships/1", headers=headers(5), json=accept).status_code == 200
    # Pending and accepted relationships stay visible; blocks hide both users.
    assert [row["id"] for row in search(authed, "user")] == [4, 5, 6, 7, 8, 9]
    assert 1 not in [row["id"] for row in search(authed, "user", headers(2))]
    assert 1 not in [row["id"] for row in search(authed, "user", headers(3))]
    assert 1 in [row["id"] for row in search(authed, "user", headers(4))]


def test_results_expose_only_id_username_and_name(authed, users):
    [with_profile] = users("private-profile")
    [without] = users("private-bare", profile=False)
    rows = search(authed, "private")
    assert rows == [
        {"id": without, "username": "private-bare", "name": None},
        {"id": with_profile, "username": "private-profile", "name": "Name of private-profile"},
    ]
    for row in rows:
        assert set(row) == {"id", "username", "name"}
    serialized = str(rows)
    for private in ["Secret", "Female", "Very Active", "44", "190", "99", "password"]:
        assert private not in serialized


def test_search_has_its_own_rate_limit_bucket(engine, headers):
    settings = Settings(
        jwt_secret=SecretStr(SECRET),
        search_rate_limit=2,
        auth_rate_limit=100,
        rate_limit_window_seconds=3600,
    )
    with TestClient(create_app(settings, engine)) as client:
        auth = headers()
        for _ in range(2):
            assert client.get("/social/users/search?q=use", headers=auth).status_code == 200
        limited = client.get("/social/users/search?q=use", headers=auth)
        assert limited.status_code == 429
        assert limited.json() == {"error": "Too many requests"}
        assert 0 < int(limited.headers["Retry-After"]) <= 3600
        # Unauthenticated attempts count too, and other routes are unaffected.
        assert client.get("/social/users/search?q=use").status_code == 429
        assert client.get("/social/friendships", headers=auth).status_code == 200
        login = client.post("/auth/login", json={"username": "user1", "password": "Password1!"})
        assert login.status_code == 200
