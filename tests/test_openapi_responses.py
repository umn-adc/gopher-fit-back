"""Real responses must match the generated OpenAPI document, including their status codes."""

from datetime import datetime
from typing import Any

import pytest

from app.features.profile.models import ACTIVITY_LEVELS, GENDERS
from tests.conftest import PASSWORD

Spec = dict[str, Any]


def validate(instance: Any, schema: Spec, spec: Spec, where: str = "$") -> None:
    """Strict subset of JSON Schema used by the generated document.

    Undeclared object keys and schemas that accept anything fail, so a serializer that
    emits a field the contract does not describe is reported as drift.
    """
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        validate(instance, spec["components"]["schemas"][name], spec, where)
        return
    if "anyOf" in schema:
        failures = []
        for option in schema["anyOf"]:
            try:
                validate(instance, option, spec, where)
                return
            except AssertionError as error:
                failures.append(str(error))
        raise AssertionError(f"{where}: matches no anyOf option: {failures}")
    if "enum" in schema:
        assert instance in schema["enum"], f"{where}: {instance!r} not in {schema['enum']}"
    kind = schema.get("type")
    assert kind is not None, f"{where}: schema {schema} does not describe the value"
    if kind == "object":
        assert isinstance(instance, dict), f"{where}: expected object, got {instance!r}"
        properties = schema.get("properties")
        assert properties, f"{where}: permissive object schema {schema}"
        missing = set(schema.get("required", [])) - set(instance)
        assert not missing, f"{where}: missing required {sorted(missing)}"
        extra = set(instance) - set(properties)
        assert not extra, f"{where}: undocumented keys {sorted(extra)}"
        for key, value in instance.items():
            validate(value, properties[key], spec, f"{where}.{key}")
    elif kind == "array":
        assert isinstance(instance, list), f"{where}: expected array, got {instance!r}"
        for index, value in enumerate(instance):
            validate(value, schema["items"], spec, f"{where}[{index}]")
    elif kind == "string":
        assert isinstance(instance, str), f"{where}: expected string, got {instance!r}"
        if schema.get("format") == "date-time":
            assert datetime.fromisoformat(instance).tzinfo is not None, where
    elif kind == "integer":
        assert type(instance) is int, f"{where}: expected integer, got {instance!r}"
    elif kind == "number":
        assert type(instance) in (int, float), f"{where}: expected number, got {instance!r}"
    elif kind == "boolean":
        assert type(instance) is bool, f"{where}: expected boolean, got {instance!r}"
    elif kind == "null":
        assert instance is None, f"{where}: expected null, got {instance!r}"
    else:
        raise AssertionError(f"{where}: unsupported schema type {kind}")
    if isinstance(instance, int | float) and not isinstance(instance, bool):
        assert instance >= schema.get("minimum", instance), where
        assert instance <= schema.get("maximum", instance), where


class Contract:
    def __init__(self, client: Any):
        self.client = client
        self.spec: Spec = client.get("/swagger/doc.json").json()
        self.seen: set[tuple[str, str, int]] = set()

    def __call__(
        self,
        method: str,
        template: str,
        status: int,
        *,
        token: str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
        **path: Any,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = self.client.request(
            method, template.format(**path), json=json, params=params, headers=headers
        )
        assert response.status_code == status, (method, template, response.text)
        operation = self.spec["paths"][template][method.lower()]
        documented = operation["responses"].get(str(status))
        assert documented is not None, f"{method} {template} does not document {status}"
        self.seen.add((method, template, status))
        if status == 204:
            assert response.content == b""
            return None
        schema = documented["content"]["application/json"]["schema"]
        validate(response.json(), schema, self.spec, f"{method} {template} {status}")
        return response.json()


@pytest.fixture
def call(client):
    return Contract(client)


def profile(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "Contract Athlete",
        "age": 30,
        "height": 180,
        "weight": 80,
        "gender": "Other",
        "activity_level": "Very Active",
        "goals": ["Strength"],
        "sports": None,
        **overrides,
    }


def test_auth_and_profile_responses_match_contract(call):
    body = {**profile(), "username": "contract", "password": PASSWORD}
    pair = call("POST", "/auth/register", 201, json=body)
    call("POST", "/auth/register", 409, json=body)
    call("POST", "/auth/register", 400, json={**body, "username": "other", "gender": ""})
    call("POST", "/auth/login", 401, json={"username": "contract", "password": "Wrong1!pass"})
    login = call("POST", "/auth/login", 200, json={"username": "contract", "password": PASSWORD})
    call("POST", "/auth/refresh", 200, json={"refresh_token": login["refresh_token"]})
    # Reuse revokes that login's session family; the registration session is unaffected.
    call("POST", "/auth/refresh", 401, json={"refresh_token": login["refresh_token"]})
    second = call("POST", "/auth/login", 200, json={"username": "contract", "password": PASSWORD})
    token = pair["token"]

    call("GET", "/profile/", 200, token=token)
    call("PUT", "/profile/", 200, token=token, json=profile(goals=None, sports=["Rowing"]))
    call(
        "PUT",
        "/profile/",
        200,
        token=token,
        json=profile(unit_preference="imperial", weekly_workout_target=4),
    )
    call("PUT", "/profile/", 400, token=token, json=profile(activity_level="Idle"))
    call("PUT", "/profile/username", 200, token=token, json={"username": "renamed"})
    call("PUT", "/profile/username", 409, token=token, json={"username": "user2"})
    call("GET", "/profile/{id}", 200, token=token, id=2)
    call("GET", "/profile/{id}", 404, token=token, id=999)
    call(
        "PUT",
        "/profile/password",
        401,
        token=token,
        json={"old_password": "Wrong1!pass", "new_password": PASSWORD},
    )
    call("POST", "/auth/recovery/request", 503, json={"username": "renamed"})
    call("POST", "/auth/logout", 204, token=second["token"])
    call("POST", "/auth/logout", 401, token=second["token"])
    call("DELETE", "/auth/account", 401, token=token, json={"password": "Wrong1!pass"})
    call("DELETE", "/auth/account", 204, token=token, json={"password": PASSWORD})
    call("GET", "/profile/", 401, token=token)


def test_nutrition_responses_match_contract(call, headers):
    token = headers()["Authorization"].split()[1]
    call("GET", "/nutrition/meals", 401)
    call("GET", "/nutrition/macros", 404, token=token)
    call("GET", "/nutrition/summary", 200, token=token, params={"date": "2026-09-25"})
    targets = {"calories_target": 2000, "protein_target": 0, "carbs_target": 1, "fat_target": 2}
    call("PUT", "/nutrition/macros", 200, token=token, json=targets)
    call("GET", "/nutrition/macros", 200, token=token)

    item = {"name": "Rice", "calories": 200, "protein": 4, "carbs": 45, "fat": 1}
    meal = call(
        "POST",
        "/nutrition/meals",
        201,
        token=token,
        json={"date": "2026-09-25", "meal_type": "Lunch", "time": "12:30", "items": [item]},
    )
    empty = call(
        "POST",
        "/nutrition/meals",
        201,
        token=token,
        json={"date": "2026-09-26", "meal_type": "Snack"},
    )
    assert "items" not in empty
    call("POST", "/nutrition/meals", 400, token=token, json={"date": "2026-02-30"})
    call("GET", "/nutrition/meals", 200, token=token, params={"limit": 1, "offset": 1})
    call("GET", "/nutrition/meals", 400, token=token, params={"limit": 0})
    call("GET", "/nutrition/meals", 200, token=token, params={"date": "2026-09-25"})
    call("GET", "/nutrition/meals", 400, token=token, params={"date": "2026-09-31"})
    call("GET", "/nutrition/summary", 200, token=token, params={"date": "2026-09-25"})
    call("GET", "/nutrition/summary", 400, token=token)
    call("GET", "/nutrition/meals/{id}", 200, token=token, id=meal["id"])
    call("GET", "/nutrition/meals/{id}", 404, token=token, id=999)
    added = call("POST", "/nutrition/meals/{id}/items", 201, token=token, json=item, id=empty["id"])
    call(
        "PUT",
        "/nutrition/meals/{id}/items/{itemId}",
        200,
        token=token,
        json={**item, "calories": 1},
        id=empty["id"],
        itemId=added["id"],
    )
    call(
        "DELETE",
        "/nutrition/meals/{id}/items/{itemId}",
        204,
        token=token,
        id=empty["id"],
        itemId=added["id"],
    )
    call(
        "PUT",
        "/nutrition/meals/{id}",
        204,
        token=token,
        json={"date": "2026-09-27", "meal_type": "Dinner", "items": []},
        id=meal["id"],
    )
    call("DELETE", "/nutrition/meals/{id}", 204, token=token, id=meal["id"])
    call("DELETE", "/nutrition/meals/{id}", 404, token=token, id=meal["id"])


def test_workout_and_social_responses_match_contract(call, headers):
    token = headers(1)["Authorization"].split()[1]
    friend = headers(2)["Authorization"].split()[1]
    lift = {"exercise_name": "Bench", "sets": 3, "reps": 5, "weight": 100.5, "weight_unit": "lb"}
    workout = call(
        "POST",
        "/workouts/",
        201,
        token=token,
        json={
            "workout_name": "Push",
            "duration": 45,
            "occurred_at": "2026-09-25T08:30:00-05:00",
            "items": [lift],
        },
    )
    bare = call("POST", "/workouts/", 201, token=token, json={"workout_name": "Walk"})
    assert bare["occurred_at"] is None and "items" not in bare
    call("POST", "/workouts/", 400, token=token, json={"workout_name": "Bad", "duration": -1})
    call(
        "GET",
        "/workouts/",
        200,
        token=token,
        params={"start": "2026-09-25T00:00:00Z", "end": "2026-09-26T00:00:00Z"},
    )
    call(
        "GET",
        "/workouts/",
        400,
        token=token,
        params={"start": "2026-09-26T00:00:00Z", "end": "2026-09-25T00:00:00Z"},
    )
    call("GET", "/workouts/{id}", 200, token=token, id=workout["id"])
    call("GET", "/workouts/{id}", 404, token=friend, id=workout["id"])
    call(
        "PUT",
        "/workouts/{id}",
        200,
        token=token,
        json={"workout_name": "Push day", "duration": 50},
        id=workout["id"],
    )
    item = call("POST", "/workouts/{id}/items", 201, token=token, json=lift, id=bare["id"])
    call(
        "PUT",
        "/workouts/{id}/items/{itemId}",
        204,
        token=token,
        json={**lift, "weight": 90},
        id=bare["id"],
        itemId=item["id"],
    )
    call(
        "DELETE",
        "/workouts/{id}/items/{itemId}",
        204,
        token=token,
        id=bare["id"],
        itemId=item["id"],
    )
    call("DELETE", "/workouts/{id}", 204, token=token, id=bare["id"])

    call("GET", "/social/leaderboard", 200, token=token, params={"exercise": "bench"})
    call("GET", "/social/leaderboard", 400, token=token)
    call("GET", "/social/muscle-ranks", 200, token=token)
    request = {"user1_id": 1, "user2_id": 2, "status": "pending"}
    call("POST", "/social/friendships", 201, token=token, json=request)
    call("POST", "/social/friendships", 409, token=token, json=request)
    call("POST", "/social/friendships", 404, token=token, json={**request, "user2_id": 999})
    for collection in ("", "/accepted", "/outpending", "/inpending", "/outblocks", "/inblocks"):
        call("GET", "/social/friendships" + collection, 200, token=token)
    call("GET", "/social/friendships/{user2_id}", 200, token=token, user2_id=2)
    call("GET", "/social/friendships/{user2_id}", 404, token=token, user2_id=3)
    call(
        "PUT",
        "/social/friendships/{user2_id}",
        200,
        token=friend,
        json={**request, "status": "accepted"},
        user2_id=1,
    )
    call("DELETE", "/social/friendships/{user2_id}", 204, token=token, user2_id=2)
    call("GET", "/health/live", 200)
    call("GET", "/health/ready", 200)


def test_error_declarations_are_specific(client):
    spec = client.get("/swagger/doc.json").json()
    throttled = set()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            responses = operation["responses"]
            assert "422" not in responses, (method, path)
            for status, response in responses.items():
                if status.startswith(("4", "5")):
                    assert response["content"]["application/json"]["schema"] == {
                        "$ref": "#/components/schemas/ErrorResponse"
                    }
            if "429" in responses:
                assert "Retry-After" in responses["429"]["headers"]
                throttled.add(path)
    # Only the auth and recovery buckets throttle (OperationsService.throttle).
    assert throttled == {path for path in spec["paths"] if path.startswith("/auth/")} | {
        "/profile/password"
    }
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    for name in ("RegisterRequest", "ProfileRequest"):
        schema = spec["components"]["schemas"][name]
        assert {"gender", "activity_level"} <= set(schema["required"])
        assert schema["properties"]["gender"]["enum"] == list(GENDERS)
        assert schema["properties"]["activity_level"]["enum"] == list(ACTIVITY_LEVELS)


def test_validator_reports_undocumented_and_permissive_shapes(client):
    spec = client.get("/swagger/doc.json").json()
    meal = {"id": 1, "user_id": 1, "date": "2026-09-25", "meal_type": "Lunch", "time": ""}
    meal_schema = {"$ref": "#/components/schemas/MealResponse"}
    validate({**meal, "total_calories": 0}, meal_schema, spec)
    with pytest.raises(AssertionError, match="undocumented keys"):
        validate({**meal, "total_calories": 0, "extra": 1}, meal_schema, spec)
    with pytest.raises(AssertionError, match="missing required"):
        validate(meal, meal_schema, spec)
    with pytest.raises(AssertionError, match="permissive"):
        validate({}, {"type": "object", "additionalProperties": True}, spec)
