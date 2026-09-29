"""Date-filtered meal lists and daily nutrition summaries (D6)."""

import pytest

DAY, OTHER_DAY = "2026-09-25", "2026-09-26"


def meal(client, date, *items, headers=None):
    response = client.post(
        "/nutrition/meals",
        headers=headers,
        json={"date": date, "meal_type": "Meal", "items": list(items)},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def food(calories, protein=0, carbs=0, fat=0):
    return {"name": "Food", "calories": calories, "protein": protein, "carbs": carbs, "fat": fat}


def test_summary_totals_one_day_and_reports_targets(authed):
    empty = authed.get("/nutrition/summary", params={"date": DAY})
    assert empty.status_code == 200
    assert empty.json() == {
        "date": DAY,
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "targets": None,
    }
    meal(authed, DAY, food(300, 20, 30, 10), food(200, 5, 40, 2))
    meal(authed, DAY)
    meal(authed, DAY, food(100, 1, 2, 3))
    meal(authed, OTHER_DAY, food(999, 99, 99, 99))
    targets = {"calories_target": 2000, "protein_target": 0, "carbs_target": 250, "fat_target": 70}
    assert authed.put("/nutrition/macros", json=targets).status_code == 200
    summary = authed.get("/nutrition/summary", params={"date": DAY}).json()
    assert summary == {
        "date": DAY,
        "calories": 600,
        "protein": 26,
        "carbs": 72,
        "fat": 15,
        "targets": {"user_id": 1, **targets},
    }
    assert authed.get("/nutrition/summary", params={"date": "2026-01-01"}).json()["calories"] == 0


@pytest.mark.parametrize("value", ["2026-02-30", "today", "2026-9-25", "25/09/2026", ""])
def test_invalid_dates_are_rejected(authed, value):
    for path in ["/nutrition/meals", "/nutrition/summary"]:
        response = authed.get(path, params={"date": value})
        assert response.status_code == 400, (path, value)
        assert response.json() == {"error": "Invalid date"}


def test_summary_requires_a_date(authed):
    response = authed.get("/nutrition/summary")
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid date"}
    assert authed.get("/nutrition/summary", headers={"Authorization": ""}).status_code == 401


def test_date_filter_and_summary_are_owner_scoped(authed, headers):
    mine = meal(authed, DAY, food(100))
    meal(authed, DAY, food(500), headers=headers(2))
    listed = authed.get("/nutrition/meals", params={"date": DAY}).json()
    assert [row["id"] for row in listed] == [mine]
    assert authed.get("/nutrition/summary", params={"date": DAY}).json()["calories"] == 100
    other = authed.get("/nutrition/summary", params={"date": DAY}, headers=headers(2)).json()
    assert other["calories"] == 500 and other["targets"] is None


def test_date_filter_keeps_id_order_and_pagination(authed):
    wanted = []
    for index in range(5):
        wanted.append(meal(authed, DAY, food(index)))
        meal(authed, OTHER_DAY)
    pages = [
        authed.get("/nutrition/meals", params={"date": DAY, "limit": 2, "offset": offset}).json()
        for offset in (0, 2, 4, 6)
    ]
    assert [[row["id"] for row in page] for page in pages] == [
        wanted[0:2],
        wanted[2:4],
        wanted[4:5],
        [],
    ]
    assert all(row["date"] == DAY for page in pages for row in page)
    exact = authed.get("/nutrition/meals", params={"date": DAY, "limit": 5}).json()
    assert len(exact) == 5
    after = authed.get("/nutrition/meals", params={"date": DAY, "limit": 5, "offset": 5})
    assert after.json() == []
    # Without the filter every meal is still returned in ID order.
    assert len(authed.get("/nutrition/meals").json()) == 10
    assert authed.get("/nutrition/meals", params={"date": DAY, "limit": 0}).json() == {
        "error": "Invalid limit"
    }


def test_date_queries_use_the_owner_date_index(engine):
    with engine.connect() as connection:
        for query in [
            "SELECT id FROM meals WHERE user_id=1 AND date='2026-09-25' ORDER BY id LIMIT 50",
            "SELECT sum(meal_items.calories) FROM meal_items JOIN meals "
            "ON meals.id=meal_items.meal_id WHERE meals.user_id=1 AND meals.date='2026-09-25'",
        ]:
            plan = " ".join(
                str(row[3]) for row in connection.exec_driver_sql("EXPLAIN QUERY PLAN " + query)
            )
            assert "meals_user_date_id" in plan and "SCAN meals" not in plan, plan
