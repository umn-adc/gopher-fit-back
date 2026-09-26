import json
from pathlib import Path

import pytest
from sqlalchemy import event

LEGACY_ROUTES = json.loads(Path("tests/fixtures/legacy_routes.json").read_text())


def test_all_legacy_routes_in_openapi(client):
    response = client.get("/swagger/doc.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    actual = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    assert {tuple(route) for route in LEGACY_ROUTES} <= actual
    assert ("POST", "/auth/refresh") in actual
    assert ("DELETE", "/auth/account") in actual
    assert ("GET", "/health/ready") in actual
    assert client.get("/swagger/index.html").status_code == 200
    assert "HTTPBearer" in response.json()["components"]["securitySchemes"]


@pytest.mark.parametrize(
    "method,path", [route for route in LEGACY_ROUTES if not route[1].startswith("/auth")]
)
def test_every_feature_route_requires_authentication(client, method, path):
    path = path.replace("{id}", "1").replace("{itemId}", "1").replace("{user2_id}", "2")
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json() == {"error": "Requires Bearer JWT token"}


@pytest.mark.parametrize("body", ["{", "{}{}", "[]", "null", '{"age":"21"}', '{"age":1.0}'])
def test_invalid_json_and_types_use_error_envelope(authed, body):
    response = authed.put("/profile/", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert set(response.json()) == {"error"}


def test_integer_overflow_and_bad_numeric_path_are_client_errors(authed):
    for path in ["/workouts/1.0", "/nutrition/meals/999999999999999999999", "/workouts/1_0"]:
        assert authed.get(path).status_code == 400
    assert authed.post("/workouts/", json={"duration": 2**64}).status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/profile/",
        "/profile/1",
        "/nutrition/meals",
        "/nutrition/macros",
        "/workouts/",
        "/social/friendships",
        "/social/leaderboard?exercise=bench",
        "/social/muscle-ranks",
    ],
)
def test_database_errors_use_json(authed, engine, path):
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE users RENAME TO unavailable_users")
        connection.exec_driver_sql("ALTER TABLE profiles RENAME TO unavailable_profiles")
        connection.exec_driver_sql("ALTER TABLE meals RENAME TO unavailable_meals")
        connection.exec_driver_sql("ALTER TABLE macro_goals RENAME TO unavailable_macros")
        connection.exec_driver_sql("ALTER TABLE workouts RENAME TO unavailable_workouts")
        connection.exec_driver_sql("ALTER TABLE friendships RENAME TO unavailable_friendships")
        connection.exec_driver_sql("ALTER TABLE personal_records RENAME TO unavailable_records")
    response = authed.get(path)
    assert response.status_code == 500
    assert response.json() == {"error": "Database operation failed"}


def test_commit_failure_is_reported_before_success_is_sent(authed, engine):
    import sqlite3

    def reject_commit(connection):
        # Raise the real driver's failure type, as a failed COMMIT would.
        from sqlalchemy.exc import OperationalError

        raise OperationalError("COMMIT", {}, sqlite3.OperationalError("injected commit failure"))

    event.listen(engine, "commit", reject_commit)
    try:
        response = authed.post(
            "/nutrition/meals", json={"date": "2026-01-01", "meal_type": "Lunch"}
        )
    finally:
        event.remove(engine, "commit", reject_commit)
    assert response.status_code == 500
    assert authed.get("/nutrition/meals").json() == []
