import time

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.features.auth.security import valid_password
from tests.conftest import PASSWORD, SECRET


def registration(**overrides):
    return {
        "name": "New User",
        "username": "new-user",
        "password": PASSWORD,
        "gender": "Other",
        "activity_level": "Sedentary",
        "goals": ["Build Muscle"],
        **overrides,
    }


def test_registration_login_and_private_public_contracts(client, engine, headers):
    response = client.post("/auth/register", json=registration())
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "token",
        "user_id",
        "username",
        "refresh_token",
        "expires_in",
        "token_type",
    }
    claims = jwt.decode(data["token"], SECRET, algorithms=["HS256"])
    assert claims["ID"] == data["user_id"]
    assert claims["Username"] == "new-user"
    assert claims["exp"] - claims["iat"] == 900
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT typeof(password) FROM users WHERE id=?", (data["user_id"],)
            ).scalar()
            == "blob"
        )
    assert client.post("/auth/register", json=registration()).status_code == 409
    response = client.post("/auth/login", json={"username": "new-user", "password": PASSWORD})
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer " + response.json()["token"]
    private = client.get("/profile/").json()
    assert private["goals"] == ["Build Muscle"]
    assert private["sports"] is None
    assert "password" not in private
    assert client.get("/profile/1").json() == {"user_id": 1, "username": "user1"}
    assert client.put("/profile/username", json={"username": "renamed"}).json() == {
        "username": "renamed"
    }
    assert client.get(f"/profile/{data['user_id']}", headers=headers(2)).json() == {
        "user_id": data["user_id"],
        "username": "renamed",
    }
    assert client.put("/profile/username", json={"username": "user1"}).status_code == 409


def test_registration_rolls_back_user_on_invalid_profile(client, engine):
    response = client.post("/auth/register", json=registration(gender="invalid"))
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid profile"}
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT COUNT(*) FROM users WHERE username='new-user'"
            ).scalar()
            == 0
        )
    assert client.post("/auth/register", json=registration()).status_code == 201


def test_registration_rolls_back_on_database_failure(client, engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_profile BEFORE INSERT ON profiles
            BEGIN SELECT RAISE(ABORT, 'injected'); END
        """)
    response = client.post("/auth/register", json=registration())
    assert response.status_code == 500
    assert set(response.json()) == {"error"}
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT COUNT(*) FROM users WHERE username='new-user'"
            ).scalar()
            == 0
        )


@pytest.mark.parametrize(
    "username,password,status",
    [
        ("absent", PASSWORD, 401),
        ("user1", "wrong", 401),
        ("user1", PASSWORD, 200),
    ],
)
def test_login_errors(client, username, password, status):
    assert (
        client.post("/auth/login", json={"username": username, "password": password}).status_code
        == status
    )


def test_profile_update_and_password_change(authed):
    response = authed.put(
        "/profile/",
        json={
            "user_id": 2,
            "name": "Changed",
            "gender": "Male",
            "activity_level": "Very Active",
            "goals": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == 1
    assert authed.get("/profile/").json()["name"] == "Changed"
    assert authed.put("/profile/", json={"gender": "bad"}).status_code == 400
    assert (
        authed.put(
            "/profile/password", json={"old_password": "wrong", "new_password": "NewPassword2!"}
        ).status_code
        == 401
    )
    assert (
        authed.put(
            "/profile/password", json={"old_password": PASSWORD, "new_password": "weak"}
        ).status_code
        == 400
    )
    response = authed.put(
        "/profile/password", json={"old_password": PASSWORD, "new_password": "NewPassword2!"}
    )
    assert response.json() == {"message": "Password updated successfully"}
    assert (
        authed.post("/auth/login", json={"username": "user1", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        authed.post(
            "/auth/login", json={"username": "user1", "password": "NewPassword2!"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "authorization", ["", "x", "Basic abc", "Bearer", "Bearer a b", "Bearer invalid"]
)
def test_malformed_authentication(client, authorization):
    response = client.get("/profile/", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert set(response.json()) == {"error"}


@pytest.mark.parametrize(
    "claims,secret,algorithm",
    [
        ({"ID": 1, "exp": 1}, SECRET, "HS256"),
        ({"ID": 1}, "other-secret-at-least-thirty-two-characters", "HS256"),
        ({"ID": 1}, SECRET, "HS384"),
        ({"ID": 0}, SECRET, "HS256"),
        ({"ID": True}, SECRET, "HS256"),
        ({"ID": "1"}, SECRET, "HS256"),
        ({"ID": 2**64}, SECRET, "HS256"),
        ({"ID": 1, "nbf": 9999999999}, SECRET, "HS256"),
    ],
)
def test_invalid_tokens(client, claims, secret, algorithm):
    token = jwt.encode(claims, secret, algorithm=algorithm)
    assert client.get("/profile/", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_go_stateless_tokens_require_new_login(client):
    # Stateless legacy tokens cannot support revocation and are deliberately rejected.
    token = jwt.encode(
        {"ID": 1, "Username": "user1", "iat": int(time.time()) + 1000}, SECRET, algorithm="HS256"
    )
    response = client.get("/profile/", headers={"Authorization": f"bEaReR   {token}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "value,status",
    [
        ("0", 400),
        ("-1", 400),
        ("abc", 400),
        ("1.0", 400),
        ("999999999999999999999", 400),
        ("99", 404),
    ],
)
def test_public_profile_ids(authed, value, status):
    assert authed.get(f"/profile/{value}").status_code == status


@pytest.mark.parametrize(
    "password,valid",
    [
        ("Password1!", True),
        ("Abcdef 1!", True),
        ("Abcdef1!", False),
        ("password1!", False),
        ("Password!", False),
        ("Password1", False),
        ("Password1!\t", False),
    ],
)
def test_legacy_password_rules(password, valid):
    assert valid_password(password) is valid


def test_secret_is_required(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings()
