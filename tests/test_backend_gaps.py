import pytest
from sqlalchemy import event

from tests.test_auth_profile import registration
from tests.test_workouts import create_workout, records

MEAL = {"date": "2026-01-01", "meal_type": "Lunch"}
WORKOUT = {"workout_name": "Strength"}


def test_meal_nested_creation_total_and_late_child_rollback(authed, engine):
    response = authed.post(
        "/nutrition/meals",
        json={
            **MEAL,
            "total_calories": 999,
            "items": [{"name": "Rice", "calories": 100}, {"name": "Egg", "calories": 80}],
        },
    )
    assert response.status_code == 201
    assert response.json()["total_calories"] == 180
    assert len(response.json()["items"]) == 2
    before = authed.get("/nutrition/meals").json()
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER fail_child BEFORE INSERT ON meal_items
            WHEN NEW.name='fail' BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    result = authed.post(
        "/nutrition/meals",
        json={
            **MEAL,
            "items": [{"name": "first"}, {"name": "fail"}],
        },
    )
    assert result.status_code == 500
    assert authed.get("/nutrition/meals").json() == before


@pytest.mark.parametrize(
    "path,parent,child,foreign_key",
    [
        ("/nutrition/meals", MEAL, {"name": "Rice"}, "meal_id"),
        ("/workouts/", WORKOUT, {"exercise_name": "Bench", "weight": 100}, "workout_id"),
    ],
)
def test_nested_replacement_omission_empty_and_child_ownership(
    authed, headers, path, parent, child, foreign_key
):
    first = authed.post(path, json={**parent, "items": [child]}).json()
    own_other = authed.post(path, json={**parent, "items": [child]}).json()
    foreign = authed.post(path, headers=headers(2), json={**parent, "items": [child]}).json()
    target = path.rstrip("/") + f"/{first['id']}"
    for other in [own_other, foreign]:
        assert authed.put(target, json={**parent, "items": [other["items"][0]]}).status_code == 404
        # Supplying a local parent ID cannot launder an unrelated item ID.
        assert (
            authed.put(
                target, json={**parent, "items": [{**other["items"][0], foreign_key: first["id"]}]}
            ).status_code
            == 404
        )
    saved = first["items"][0]
    assert authed.put(target, json={**parent, "items": [saved, saved]}).status_code == 400
    assert authed.put(target, json=parent).status_code in [200, 204]
    assert authed.get(target).json()["items"] == first["items"]
    assert authed.put(target, json={**parent, "items": None}).status_code in [200, 204]
    assert authed.get(target).json()["items"] == first["items"]
    assert authed.put(target, json={**parent, "items": [saved, child]}).status_code in [200, 204]
    assert len(authed.get(target).json()["items"]) == 2
    assert authed.put(target, json={**parent, "items": []}).status_code in [200, 204]
    assert "items" not in authed.get(target).json()


def test_nested_workout_updates_recalculate_records_and_rollback(authed, engine):
    first = create_workout(authed, [100, 150, 150])
    fallback = create_workout(authed, [125])
    target = f"/workouts/{first['id']}"
    replacement = [{**first["items"][0], "exercise_name": "Squat", "weight": 200}]
    assert authed.put(target, json={**WORKOUT, "items": replacement}).status_code == 200
    assert [(r["exercise_key"], r["max_weight"]) for r in records(authed)] == [
        ("bench press", 125),
        ("squat", 200),
    ]
    assert records(authed)[0]["source_workout_item_id"] == fallback["items"][0]["id"]
    before, before_records = authed.get(target).json(), records(authed)
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER fail_record BEFORE INSERT ON personal_records
            BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    assert (
        authed.put(
            target,
            json={
                "workout_name": "Changed",
                "items": [{"exercise_name": "Deadlift", "weight": 250}],
            },
        ).status_code
        == 500
    )
    assert authed.get(target).json() == before
    assert records(authed) == before_records


@pytest.mark.parametrize("field", ["calories", "protein", "carbs", "fat"])
def test_nutrition_creation_and_update_share_validation(authed, field):
    meal = authed.post("/nutrition/meals", json=MEAL).json()["id"]
    path = f"/nutrition/meals/{meal}/items"
    item = authed.post(path, json={"name": "Valid"}).json()["id"]
    body = {"name": "Negative", field: -1}
    assert authed.post(path, json=body).status_code == 400
    assert authed.put(path + f"/{item}", json=body).status_code == 400
    assert authed.post("/nutrition/meals", json={**MEAL, "items": [body]}).status_code == 400
    assert authed.put("/nutrition/macros", json={field + "_target": -1}).status_code == 400


@pytest.mark.parametrize("field", ["sets", "reps", "weight", "duration_minutes"])
def test_workout_creation_and_update_share_validation(authed, field):
    workout = create_workout(authed, [100])
    path = f"/workouts/{workout['id']}"
    body = {"exercise_name": "Bench", field: -1}
    assert authed.post(path + "/items", json=body).status_code == 400
    assert authed.put(path + f"/items/{workout['items'][0]['id']}", json=body).status_code == 400
    assert authed.post("/workouts/", json={**WORKOUT, "items": [body]}).status_code == 400
    assert authed.put(path, json={**WORKOUT, "items": [body]}).status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"date": "today"},
        {"date": "2026-02-29"},
        {"date": "2026-1-1"},
        {"time": "25:00"},
        {"time": "10:61"},
        {"time": "12:00Z"},
        {"meal_type": " \u00a0"},
        {"date": None},
    ],
)
def test_meal_dates_and_times_on_create_and_update(authed, body):
    meal = authed.post("/nutrition/meals", json=MEAL).json()
    assert authed.post("/nutrition/meals", json={**MEAL, **body}).status_code == 400
    assert authed.put(f"/nutrition/meals/{meal['id']}", json={**MEAL, **body}).status_code == 400


@pytest.mark.parametrize(
    "field,value",
    [
        ("age", -1),
        ("age", 131),
        ("height", -1),
        ("height", 301),
        ("weight", -1),
        ("weight", 701),
        ("name", "  "),
    ],
)
def test_profile_limits_at_registration_and_update(client, headers, field, value):
    body = registration(**{field: value})
    assert client.post("/auth/register", json=body).status_code == 400
    assert client.put("/profile/", headers=headers(), json=body).status_code == 400


@pytest.mark.parametrize("password", ["Password1!" + "a" * 63, "Password1!" + "é" * 32])
def test_bcrypt_byte_limit_is_a_client_error(client, headers, password):
    assert client.post("/auth/register", json=registration(password=password)).status_code == 400
    assert (
        client.post("/auth/login", json={"username": "user1", "password": password}).status_code
        == 400
    )
    assert (
        client.put(
            "/profile/password",
            headers=headers(),
            json={"old_password": "Password1!", "new_password": password},
        ).status_code
        == 400
    )
    assert (
        client.request(
            "DELETE", "/auth/account", headers=headers(), json={"password": password}
        ).status_code
        == 400
    )


def test_required_names_and_parent_duration(authed):
    assert authed.put("/profile/username", json={"username": " \u00a0"}).status_code == 400
    for body in [{"workout_name": " "}, {**WORKOUT, "duration": -1}]:
        assert authed.post("/workouts/", json=body).status_code == 400
    assert (
        authed.post("/nutrition/meals", json={**MEAL, "items": [{"name": " "}]}).status_code == 400
    )


def test_workout_timezone_filter_order_and_unknown_dates(authed):
    times = [None, "2026-01-02T10:00:00-06:00", "2026-01-02T16:00:00Z", "2026-01-01T23:00:00Z"]
    workouts = [authed.post("/workouts/", json={**WORKOUT, "occurred_at": t}).json() for t in times]
    assert [w["id"] for w in authed.get("/workouts/").json()] == [
        workouts[i]["id"] for i in [2, 1, 3, 0]
    ]
    assert workouts[0]["occurred_at"] is None
    assert workouts[1]["occurred_at"] == "2026-01-02T16:00:00Z"
    selected = authed.get(
        "/workouts/",
        params={
            "start": "2026-01-02T00:00:00Z",
            "end": "2026-01-03T00:00:00Z",
            "limit": 1,
            "offset": 1,
        },
    )
    assert selected.status_code == 200 and selected.json()[0]["id"] == workouts[1]["id"]
    assert authed.get("/workouts/", params={"end": "2026-01-02T16:00:00Z"}).json() == [workouts[3]]
    path = f"/workouts/{workouts[1]['id']}"
    assert authed.put(path, json=WORKOUT).json()["occurred_at"] == workouts[1]["occurred_at"]
    assert authed.put(path, json={**WORKOUT, "occurred_at": None}).json()["occurred_at"] is None
    for timestamp in ["2026-01-01", "2026-01-01T10:00:00", "invalid", 123]:
        assert (
            authed.post("/workouts/", json={**WORKOUT, "occurred_at": timestamp}).status_code == 400
        )
        assert authed.get("/workouts/", params={"start": timestamp}).status_code == 400
    assert authed.get("/workouts/", params={"start": times[1], "end": times[3]}).status_code == 400


@pytest.mark.parametrize(
    "path,parent,child,table",
    [
        ("/nutrition/meals", MEAL, {"name": "Rice"}, "meal_items"),
        ("/workouts/", WORKOUT, {"exercise_name": "Bench"}, "workout_item"),
    ],
)
def test_list_pagination_and_one_batched_child_query(
    authed, headers, engine, path, parent, child, table
):
    for _ in range(4):
        authed.post(path, json={**parent, "items": [child]})
    authed.post(path, headers=headers(2), json={**parent, "items": [child]})
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        all_rows = authed.get(path).json()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(all_rows) == 4
    assert sum(f"FROM {table}" in statement for statement in statements) == 1
    assert authed.get(path, params={"limit": 2, "offset": 1}).json() == all_rows[1:3]
    assert authed.get(path, params={"offset": 100}).json() == []


@pytest.mark.parametrize(
    "path",
    [
        "/nutrition/meals",
        "/workouts/",
        "/social/friendships",
        "/social/leaderboard?exercise=Bench",
        "/social/muscle-ranks",
    ],
)
@pytest.mark.parametrize(
    "query", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 1000001}]
)
def test_page_bounds_use_json_envelope(authed, path, query):
    response = authed.get(path, params=query)
    assert response.status_code == 400 and set(response.json()) == {"error"}


def test_pagination_keeps_global_rank_and_percentile(authed, headers):
    for user, weight in enumerate([300, 200, 200, 100], 1):
        create_workout(authed, [weight], headers=headers(user))
    rows = authed.get(
        "/social/leaderboard", params={"exercise": "bench press", "limit": 2, "offset": 1}
    ).json()
    assert [(r["user_id"], r["rank"], r["percentile"]) for r in rows] == [(2, 2, 75), (3, 2, 75)]
    mine = authed.get("/social/muscle-ranks", headers=headers(4), params={"limit": 1}).json()[0]
    assert mine["rank"] == 3 and mine["percentile"] == 25


def test_friendship_pagination_and_collection_scoping(authed, headers):
    for other in [2, 3, 4]:
        assert (
            authed.post(
                "/social/friendships", json={"user1_id": 1, "user2_id": other, "status": "pending"}
            ).status_code
            == 201
        )
    for suffix in ["", "/outpending"]:
        rows = authed.get("/social/friendships" + suffix, params={"limit": 1, "offset": 1}).json()
        assert len(rows) == 1 and rows[0]["user2_id"] == 3
    assert authed.get("/social/friendships", headers=headers(5)).json() == []


def test_large_collections_are_bounded_by_default(authed, engine):
    from tests.conftest import HASH

    with engine.begin() as connection:
        for i in range(10, 120):
            connection.exec_driver_sql("INSERT INTO users VALUES(?,?,?)", (i, f"large-{i}", HASH))
            connection.exec_driver_sql("INSERT INTO friendships VALUES(1,?,1,'pending')", (i,))
            connection.exec_driver_sql(
                "INSERT INTO meals(user_id,date,meal_type) VALUES(1,'2026-01-01','Lunch')"
            )
            connection.exec_driver_sql(
                "INSERT INTO workouts(id,user_id,workout_name,duration) VALUES(?,?,'Strength',0)",
                (i, i),
            )
            connection.exec_driver_sql(
                "INSERT INTO workout_item VALUES(?,?,'Bench',1,1,100,0)", (i, i)
            )
            connection.exec_driver_sql(
                "INSERT INTO personal_records VALUES(?,'bench','Bench',100,?)", (i, i)
            )
            connection.exec_driver_sql(
                "INSERT INTO workouts(id,user_id,workout_name,duration) VALUES(?,1,'My workout',0)",
                (i + 1000,),
            )
    for path in [
        "/nutrition/meals",
        "/workouts/",
        "/social/friendships",
        "/social/friendships/outpending",
        "/social/leaderboard?exercise=bench",
    ]:
        assert len(authed.get(path).json()) == 50
        separator = "&" if "?" in path else "?"
        assert len(authed.get(path + separator + "limit=100").json()) == 100
        assert len(authed.get(path + separator + "limit=100&offset=100").json()) == 10
