"""Optional weekly workout target on the profile (D4)."""

import sqlite3

import pytest

from tests.conftest import PASSWORD, migrate
from tests.test_migrations import legacy_database, snapshot

PROFILE = {"name": "Target", "gender": "Female", "activity_level": "Very Active"}


def test_target_is_optional_and_replaced_with_the_profile(authed):
    assert authed.get("/profile/").json()["weekly_workout_target"] is None
    for target in [1, 4, 14]:
        saved = authed.put("/profile/", json={**PROFILE, "weekly_workout_target": target})
        assert saved.status_code == 200
        assert saved.json()["weekly_workout_target"] == target
        assert authed.get("/profile/").json()["weekly_workout_target"] == target
    # Profile PUT is a full replacement: null or omission removes the target.
    cleared = authed.put("/profile/", json={**PROFILE, "weekly_workout_target": None})
    assert cleared.json()["weekly_workout_target"] is None
    authed.put("/profile/", json={**PROFILE, "weekly_workout_target": 3})
    assert authed.put("/profile/", json=PROFILE).json()["weekly_workout_target"] is None


@pytest.mark.parametrize("target", [0, 15, -1, 3.0, 2.5, "3", True, 2**63])
def test_target_outside_one_to_fourteen_is_rejected(authed, target):
    authed.put("/profile/", json={**PROFILE, "weekly_workout_target": 5})
    response = authed.put("/profile/", json={**PROFILE, "weekly_workout_target": target})
    assert response.status_code == 400
    assert set(response.json()) == {"error"}
    assert authed.get("/profile/").json()["weekly_workout_target"] == 5


def test_registration_accepts_a_target(client):
    body = {**PROFILE, "username": "weekly", "password": PASSWORD, "weekly_workout_target": 6}
    token = client.post("/auth/register", json=body).json()["token"]
    profile = client.get("/profile/", headers={"Authorization": f"Bearer {token}"}).json()
    assert profile["weekly_workout_target"] == 6
    invalid = {**body, "username": "weekly-invalid", "weekly_workout_target": 20}
    assert client.post("/auth/register", json=invalid).status_code == 400


def test_existing_profiles_have_no_target_after_upgrade(tmp_path):
    path = tmp_path / "legacy.db"
    before = legacy_database(path)
    migrate(path)
    with sqlite3.connect(path) as connection:
        after = snapshot(connection)
        assert after["profiles"] == before["profiles"]
        assert connection.execute("SELECT weekly_workout_target FROM profiles").fetchall() == [
            (None,)
        ]
        for invalid in (0, 15):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("UPDATE profiles SET weekly_workout_target=?", (invalid,))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
