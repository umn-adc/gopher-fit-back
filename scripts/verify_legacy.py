"""Optional end-to-end differential check against the archived Go server.

Build legacy/go into /tmp/gopher-fit-legacy and run:
    uv run python -m scripts.verify_legacy /tmp/gopher-fit-legacy
Uses disposable databases and requires localhost:3000 to be available.
"""

import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

SECRET = "differential-check-secret-at-least-thirty-two-characters"


def compare(binary: Path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 3000))
    with tempfile.TemporaryDirectory(prefix="gopher-differential-") as directory:
        path = Path(directory)
        database = path / "python.db"
        config = Config("alembic.ini")
        config.attributes["database_url"] = f"sqlite:///{database}"
        command.upgrade(config, "head")
        with (path / "go.log").open("w") as log:
            process = subprocess.Popen(
                [str(binary)],
                cwd=path,
                env={**os.environ, "JWT_SECRET": SECRET},
                stdout=log,
                stderr=log,
            )
            try:
                with httpx.Client(base_url="http://localhost:3000") as old:
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError((path / "go.log").read_text())
                        try:
                            old.get("/swagger/doc.json")
                            break
                        except httpx.ConnectError:
                            time.sleep(0.05)
                    else:
                        raise RuntimeError("Go server did not start")
                    app = create_app(
                        Settings(jwt_secret=SecretStr(SECRET), database_url=f"sqlite:///{database}")
                    )
                    with TestClient(app) as new:
                        scenarios(old, new)
                # Compare persisted user data except password salts and migration metadata.
                with (
                    sqlite3.connect(path / "gopherfit.db") as old_db,
                    sqlite3.connect(database) as new_db,
                ):
                    for table in [
                        "profiles",
                        "meals",
                        "meal_items",
                        "macro_goals",
                        "workouts",
                        "workout_item",
                        "personal_records",
                        "friendships",
                    ]:
                        query = f'SELECT * FROM "{table}" ORDER BY rowid'
                        assert (
                            old_db.execute(query).fetchall() == new_db.execute(query).fetchall()
                        ), table
                print(
                    "Legacy differential check passed: response contracts, "
                    "JWT interoperability, persisted data"
                )
            finally:
                process.terminate()
                process.wait(timeout=10)


def scenarios(old: httpx.Client, new: TestClient) -> None:
    count = 0

    def request(method, path, body=None, expected=None):
        nonlocal count
        responses = [client.request(method, path, json=body) for client in (old, new)]
        assert responses[0].status_code == responses[1].status_code, (
            method,
            path,
            [(response.status_code, response.text) for response in responses],
        )
        if expected is not None:
            assert responses[0].status_code == expected, (method, path, responses[0].text)
        payloads = [response.json() if response.content else None for response in responses]
        for payload in payloads:
            if isinstance(payload, dict) and "token" in payload:
                payload["token"] = "<signed token>"
        assert payloads[0] == payloads[1], (method, path, payloads)
        count += 1
        return responses

    for username in ["one", "two"]:
        request(
            "POST",
            "/auth/register",
            {
                "username": username,
                "password": "Password1!",
                "gender": "Other",
                "activity_level": "Sedentary",
            },
            201,
        )
    responses = request("POST", "/auth/login", {"username": "one", "password": "Password1!"}, 200)
    # Deliberately exchange tokens between implementations.
    old.headers["Authorization"] = "Bearer " + responses[1].json()["token"]
    new.headers["Authorization"] = "Bearer " + responses[0].json()["token"]
    for path in [
        "/profile/",
        "/profile/2",
        "/nutrition/meals",
        "/workouts/",
        "/social/friendships",
    ]:
        request("GET", path, expected=200)
    request("GET", "/profile/999", expected=404)
    request("GET", "/profile/0", expected=400)
    request("PUT", "/profile/username", {"username": "renamed"}, 200)
    request(
        "PUT",
        "/profile/password",
        {"old_password": "Password1!", "new_password": "NewPassword2!"},
        200,
    )
    request(
        "PUT",
        "/profile/",
        {
            "name": "Changed",
            "gender": "Male",
            "activity_level": "Very Active",
            "goals": ["Strength"],
        },
        200,
    )
    request("PUT", "/nutrition/macros", {"calories_target": 2000}, 200)
    request("GET", "/nutrition/macros", expected=200)
    request(
        "POST",
        "/nutrition/meals",
        {"date": "today", "meal_type": "Lunch", "total_calories": 42},
        201,
    )
    request("POST", "/nutrition/meals/1/items", {"name": "Rice", "calories": 100}, 201)
    request(
        "PUT",
        "/nutrition/meals/1/items/1",
        {"id": 99, "meal_id": 99, "name": "Beans", "protein": 5},
        200,
    )
    request("GET", "/nutrition/meals/1", expected=200)
    request("GET", "/nutrition/meals", expected=200)
    request("PUT", "/nutrition/meals/1", {"date": "tomorrow"}, 204)
    request(
        "POST",
        "/workouts/",
        {
            "workout_name": "Strength",
            "items": [
                {"exercise_name": "Bench Press", "weight": 100},
                {"exercise_name": " BENCH\u00a0PRESS ", "weight": 125},
            ],
        },
        201,
    )
    request("GET", "/workouts/1", expected=200)
    request(
        "PUT", "/workouts/1", {"workout_name": "Renamed", "items": [{"exercise_name": "Echo"}]}, 200
    )
    request("GET", "/workouts/", expected=200)
    request("POST", "/workouts/1/items", {"exercise_name": "Squat", "weight": 200}, 201)
    request("GET", "/social/leaderboard?exercise=Bench%20Press", expected=200)
    request("GET", "/social/muscle-ranks", expected=200)
    request("PUT", "/workouts/1/items/2", {"exercise_name": "Squat", "weight": 225}, 204)
    request("DELETE", "/workouts/1/items/1", expected=204)
    request("GET", "/social/muscle-ranks", expected=200)
    request(
        "POST",
        "/social/friendships",
        {"user1_id": 2, "user2_id": 1, "status": "pending", "action_user_id": 2},
        201,
    )
    request(
        "PUT", "/social/friendships/2", {"user1_id": 1, "user2_id": 2, "status": "accepted"}, 400
    )
    request(
        "PUT", "/social/friendships/2", {"user1_id": 1, "user2_id": 2, "status": "blocked"}, 200
    )
    for suffix in ["", "/accepted", "/outpending", "/inpending", "/outblocks", "/inblocks"]:
        request("GET", "/social/friendships" + suffix, expected=200)
    request("DELETE", "/social/friendships/2", expected=204)
    request("DELETE", "/nutrition/meals/1/items/1", expected=204)
    request("DELETE", "/nutrition/meals/1", expected=204)
    request("DELETE", "/workouts/1", expected=204)
    request("GET", "/social/muscle-ranks", expected=200)
    print(f"Compared {count} requests")


if __name__ == "__main__":
    compare(Path(sys.argv[1]).resolve())
