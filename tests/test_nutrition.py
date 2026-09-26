import pytest


def test_meal_lifecycle_macros_and_response_shapes(authed, headers):
    assert authed.get("/nutrition/meals").json() == []
    assert authed.get("/nutrition/macros").status_code == 404
    assert authed.put("/nutrition/macros", json={"user_id": 2, "calories_target": 2000}).json() == {
        "user_id": 1,
        "calories_target": 2000,
        "protein_target": 0,
        "carbs_target": 0,
        "fat_target": 0,
    }
    assert authed.get("/nutrition/macros").json()["calories_target"] == 2000
    response = authed.post(
        "/nutrition/meals",
        json={"date": "2026-01-01", "meal_type": "Lunch", "items": []},
    )
    assert response.status_code == 201
    meal = response.json()
    assert "items" not in meal
    assert meal["user_id"] == 1
    path = f"/nutrition/meals/{meal['id']}"
    response = authed.post(path + "/items", json={"name": "Rice", "calories": 100})
    assert response.status_code == 201
    item = response.json()
    item_path = path + f"/items/{item['id']}"
    assert authed.get(path).json()["total_calories"] == 100
    assert authed.get("/nutrition/meals").json()[0]["items"] == [item]
    response = authed.put(
        item_path,
        json={"id": 999, "meal_id": 999, "name": "Chicken", "calories": 200, "protein": 35},
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": item["id"],
        "meal_id": meal["id"],
        "name": "Chicken",
        "calories": 200,
        "protein": 35,
        "carbs": 0,
        "fat": 0,
    }
    assert authed.get(path).json()["total_calories"] == 200
    assert authed.put(path, json={"date": "2026-01-02", "meal_type": "Dinner"}).status_code == 204
    assert authed.get(path).json()["date"] == "2026-01-02"
    assert authed.get(path, headers=headers(2)).status_code == 404
    assert authed.get("/nutrition/meals", headers=headers(2)).json() == []
    assert authed.delete(item_path).status_code == 204
    assert "items" not in authed.get(path).json()
    assert authed.delete(path).status_code == 204
    assert authed.get(path).status_code == 404


@pytest.fixture
def meal_item(authed):
    meal = authed.post("/nutrition/meals", json={"date": "2026-01-01", "meal_type": "Lunch"}).json()
    item = authed.post(f"/nutrition/meals/{meal['id']}/items", json={"name": "Original"}).json()
    return meal["id"], item["id"]


@pytest.mark.parametrize(
    "body",
    [
        {"name": " "},
        {"name": "\u00a0"},
        {"name": "x", "calories": -1},
        {"name": "x", "protein": -1},
        {"name": "x", "carbs": -1},
        {"name": "x", "fat": -1},
        {"name": "x", "calories": 1.2},
        {"name": "x", "protein": "1"},
        {"name": "x", "calories": True},
    ],
)
def test_item_validation_is_atomic(authed, meal_item, body):
    meal, item = meal_item
    assert authed.put(f"/nutrition/meals/{meal}/items/{item}", json=body).status_code == 400
    assert authed.get(f"/nutrition/meals/{meal}").json()["items"][0]["name"] == "Original"


@pytest.mark.parametrize("method", ["put", "delete"])
def test_item_owner_and_parent_required(authed, headers, meal_item, method):
    meal, item = meal_item
    other = authed.post(
        "/nutrition/meals", json={"date": "2026-01-01", "meal_type": "Lunch"}
    ).json()["id"]
    body = {"json": {"name": "Changed"}} if method == "put" else {}
    assert (
        getattr(authed, method)(
            f"/nutrition/meals/{meal}/items/{item}", headers=headers(2), **body
        ).status_code
        == 404
    )
    assert (
        getattr(authed, method)(f"/nutrition/meals/{other}/items/{item}", **body).status_code == 404
    )
    assert authed.get(f"/nutrition/meals/{meal}").json()["items"][0]["name"] == "Original"


def test_meal_delete_cascades(authed, engine, meal_item):
    meal, item = meal_item
    assert authed.delete(f"/nutrition/meals/{meal}").status_code == 204
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM meal_items WHERE id=?", (item,)
            ).scalar()
            == 0
        )
