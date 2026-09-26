import pytest


def create_workout(client, weights, name=" Bench\u00a0 Press ", headers=None):
    response = client.post(
        "/workouts/",
        headers=headers,
        json={
            "workout_name": "Strength",
            "duration": 60,
            "items": [{"exercise_name": name, "weight": weight} for weight in weights],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def records(client):
    response = client.get("/social/muscle-ranks")
    assert response.status_code == 200, response.text
    return response.json()


def test_records_follow_full_lifecycle(authed):
    first = create_workout(authed, [100, 150, 150])
    second = create_workout(authed, [125], "BENCH PRESS")
    rank = records(authed)[0]
    assert rank == {
        "user_id": 1,
        "exercise_key": "bench press",
        "exercise_name": "Bench Press",
        "max_weight": 150,
        "source_workout_item_id": first["items"][1]["id"],
        "rank": 1,
        "percentile": 100,
    }
    prefix = f"/workouts/{first['id']}/items/"
    # Removing a tied winning lift promotes the other stable source.
    assert authed.delete(prefix + str(first["items"][1]["id"])).status_code == 204
    assert records(authed)[0]["source_workout_item_id"] == first["items"][2]["id"]
    # Rename must recompute both exercise keys.
    response = authed.put(
        prefix + str(first["items"][2]["id"]), json={"exercise_name": "Squat", "weight": 200}
    )
    assert response.status_code == 204 and response.content == b""
    assert [(r["exercise_key"], r["max_weight"]) for r in records(authed)] == [
        ("bench press", 125),
        ("squat", 200),
    ]
    assert authed.delete(f"/workouts/{second['id']}").status_code == 204
    assert records(authed)[0]["max_weight"] == 100
    added = authed.post(
        f"/workouts/{first['id']}/items", json={"exercise_name": "Bench Press", "weight": 175}
    ).json()
    assert records(authed)[0]["source_workout_item_id"] == added["id"]
    assert authed.delete(f"/workouts/{first['id']}").status_code == 204
    assert records(authed) == []


def test_rank_ties_and_global_population(authed, headers):
    for user, weight in enumerate([300, 200, 200, 100], start=1):
        create_workout(authed, [weight], headers=headers(user))
    create_workout(authed, [0], headers=headers(5))
    response = authed.get("/social/leaderboard", params={"exercise": "  BENCH   PRESS "})
    assert response.status_code == 200
    rows = response.json()
    assert [row["user_id"] for row in rows] == [1, 2, 3, 4]
    assert [row["rank"] for row in rows] == [1, 2, 2, 3]
    assert [row["percentile"] for row in rows] == [100, 75, 75, 25]
    assert set(rows[0]) == {"user_id", "username", "max_weight", "rank", "percentile"}
    mine = authed.get("/social/muscle-ranks", headers=headers(3)).json()
    assert len(mine) == 1 and mine[0]["user_id"] == 3
    assert mine[0]["rank"] == 2 and mine[0]["percentile"] == 75
    assert authed.get("/social/muscle-ranks", headers=headers(5)).json() == []


def test_workout_response_and_parent_update_contract(authed):
    assert authed.get("/workouts/").json() == []
    empty = create_workout(authed, [])
    assert "items" not in empty
    response = authed.put(
        f"/workouts/{empty['id']}",
        json={"workout_name": "Changed", "duration": 5, "items": [{"exercise_name": "Persisted"}]},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] > 0
    persisted = authed.get(f"/workouts/{empty['id']}").json()
    assert persisted == response.json()


@pytest.mark.parametrize("operation", ["create", "add", "edit", "delete_item", "delete_workout"])
def test_record_failure_rolls_back_workout_mutation(authed, engine, operation):
    workout = create_workout(authed, [100, 150])
    before = authed.get("/workouts/").json()
    before_records = records(authed)
    with engine.begin() as connection:
        for event in ["INSERT", "UPDATE", "DELETE"]:
            connection.exec_driver_sql(f"""
                CREATE TRIGGER fail_record_{event} BEFORE {event} ON personal_records
                BEGIN SELECT RAISE(ABORT, 'injected record failure'); END
            """)
    path = f"/workouts/{workout['id']}"
    item_path = path + f"/items/{workout['items'][1]['id']}"
    if operation == "create":
        response = authed.post(
            "/workouts/",
            json={"workout_name": "Strength", "items": [{"exercise_name": "Squat", "weight": 200}]},
        )
    elif operation == "add":
        response = authed.post(
            path + "/items", json={"exercise_name": "Bench Press", "weight": 200}
        )
    elif operation == "edit":
        response = authed.put(item_path, json={"exercise_name": "Squat", "weight": 200})
    elif operation == "delete_item":
        response = authed.delete(item_path)
    else:
        response = authed.delete(path)
    assert response.status_code == 500
    assert set(response.json()) == {"error"}
    assert authed.get("/workouts/").json() == before
    assert records(authed) == before_records


def test_child_failure_rolls_back_entire_creation(authed, engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_item BEFORE INSERT ON workout_item WHEN NEW.exercise_name='fail'
            BEGIN SELECT RAISE(ABORT, 'injected'); END
        """)
    response = authed.post(
        "/workouts/",
        json={
            "workout_name": "Strength",
            "items": [
                {"exercise_name": "Bench", "weight": 100},
                {"exercise_name": "fail", "weight": 20},
            ],
        },
    )
    assert response.status_code == 500
    assert authed.get("/workouts/").json() == []
    assert records(authed) == []


@pytest.mark.parametrize("method", ["put", "delete"])
def test_workout_item_parent_and_owner(authed, headers, method):
    first = create_workout(authed, [100])
    second = create_workout(authed, [])
    item = first["items"][0]["id"]
    kwargs = {"json": {"exercise_name": "Squat", "weight": 200}} if method == "put" else {}
    assert (
        getattr(authed, method)(
            f"/workouts/{first['id']}/items/{item}", headers=headers(2), **kwargs
        ).status_code
        == 404
    )
    assert (
        getattr(authed, method)(f"/workouts/{second['id']}/items/{item}", **kwargs).status_code
        == 404
    )
    assert records(authed)[0]["max_weight"] == 100
    assert authed.delete(f"/workouts/{first['id']}", headers=headers(2)).status_code == 404


@pytest.mark.parametrize(
    "item",
    [
        {"exercise_name": " "},
        {"exercise_name": "\u00a0"},
        {"exercise_name": "Bench", "weight": -1},
        {"exercise_name": "Bench", "weight": "100"},
    ],
)
def test_workout_item_validation(authed, item):
    assert (
        authed.post("/workouts/", json={"workout_name": "Strength", "items": [item]}).status_code
        == 400
    )
    assert authed.get("/workouts/").json() == []


@pytest.mark.parametrize("weight", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_nonfinite_weights_rejected(authed, weight):
    response = authed.post(
        "/workouts/",
        content='{"workout_name":"Strength","items":[{"exercise_name":"Bench","weight":'
        + weight
        + "}]}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_leaderboard_validation_and_empty(authed):
    assert authed.get("/social/leaderboard").status_code == 400
    assert authed.get("/social/leaderboard", params={"exercise": " "}).status_code == 400
    assert authed.get("/social/leaderboard", params={"exercise": "Unknown"}).json() == []
