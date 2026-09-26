from itertools import product

import pytest
from sqlalchemy.orm import Session

from app.features.social.repository import SocialRepository
from app.features.social.service import SocialService


def seed(engine, status, actor=1):
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO friendships VALUES (1, 2, ?, ?)", (actor, status))


def test_create_friendship_contract(authed, headers):
    response = authed.post(
        "/social/friendships",
        json={"user1_id": 2, "user2_id": 1, "status": "pending", "action_user_id": 3},
    )
    assert response.status_code == 201
    assert response.json() == {
        "user1_id": 1,
        "user2_id": 2,
        "status": "pending",
        "action_user_id": 1,
    }
    assert authed.get("/social/friendships/2").json() == response.json()
    assert authed.get("/social/friendships/1", headers=headers(2)).json() == response.json()
    assert (
        authed.post(
            "/social/friendships", json={"user1_id": 1, "user2_id": 2, "status": "blocked"}
        ).status_code
        == 409
    )
    assert authed.get("/social/friendships/2", headers=headers(3)).status_code == 404


@pytest.mark.parametrize(
    "first,second,status,expected",
    [
        (1, 2, "accepted", 400),
        (1, 2, "bad", 400),
        (1, 1, "pending", 400),
        (0, 1, "pending", 400),
        (2, 3, "pending", 400),
        (1, 99, "pending", 404),
    ],
)
def test_friendship_creation_validation(authed, first, second, status, expected):
    assert (
        authed.post(
            "/social/friendships", json={"user1_id": first, "user2_id": second, "status": status}
        ).status_code
        == expected
    )
    assert authed.get("/social/friendships").json() == []


# Explicit accepted transitions from the pre-migration API contract, acting as user 1.
ALLOWED = {
    ("pending", 1): {"blocked"},
    ("pending", 2): {"accepted", "blocked"},
    ("accepted", 1): {"pending", "blocked"},
    ("accepted", 2): {"pending", "blocked"},
    ("blocked", 1): {"pending"},
    ("blocked", 2): set(),
}


@pytest.mark.parametrize(
    "current,actor,desired",
    list(product(["pending", "accepted", "blocked"], [1, 2], ["pending", "accepted", "blocked"])),
)
def test_friendship_transition_matrix(authed, engine, current, actor, desired):
    seed(engine, current, actor)
    before = authed.get("/social/friendships/2").json()
    response = authed.put(
        "/social/friendships/2",
        json={"user1_id": 2, "user2_id": 1, "status": desired, "action_user_id": 3},
    )
    allowed = desired in ALLOWED[current, actor]
    assert response.status_code == (200 if allowed else 400)
    after = authed.get("/social/friendships/2").json()
    assert after == (
        {"user1_id": 1, "user2_id": 2, "action_user_id": 1, "status": desired}
        if allowed
        else before
    )


@pytest.mark.parametrize("status,actor", list(product(["pending", "accepted", "blocked"], [1, 2])))
def test_delete_friendship_authorization(authed, engine, status, actor):
    seed(engine, status, actor)
    response = authed.delete("/social/friendships/2")
    forbidden = status == "blocked" and actor == 2
    assert response.status_code == (400 if forbidden else 204)
    assert authed.get("/social/friendships/2").status_code == (200 if forbidden else 404)


def test_collections_are_scoped_even_for_legacy_nonparticipant_actor(authed, engine, headers):
    rows = [
        (1, 5, 1, "accepted"),
        (5, 6, 5, "accepted"),
        (2, 5, 5, "pending"),
        (5, 7, 7, "pending"),
        (3, 5, 3, "blocked"),
        (5, 8, 5, "blocked"),
        (1, 2, 1, "accepted"),
        (2, 3, 2, "pending"),
        (3, 4, 3, "blocked"),
        (1, 3, 5, "pending"),
        (1, 4, 5, "blocked"),
    ]
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO friendships VALUES (?, ?, ?, ?)", rows)
    expected = {
        "": [1, 2, 3, 6, 7, 8],
        "/accepted": [1, 6],
        "/outpending": [2],
        "/inpending": [7],
        "/outblocks": [8],
        "/inblocks": [3],
    }
    for suffix, peers in expected.items():
        response = authed.get("/social/friendships" + suffix, headers=headers(5))
        assert response.status_code == 200
        assert (
            sorted(r["user1_id"] if r["user1_id"] != 5 else r["user2_id"] for r in response.json())
            == peers
        )
        assert authed.get("/social/friendships" + suffix, headers=headers(9)).json() == []


def test_stale_update_and_delete_cannot_overwrite_block(engine):
    seed(engine, "pending")
    with Session(engine) as first:
        previous = SocialService(SocialRepository(first)).friendship(1, 2)
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE friendships SET status='blocked', action_user_id=2")
    with Session(engine) as session, session.begin():
        repository = SocialRepository(session)
        assert repository.update(previous, 1, "accepted") is False
        assert repository.delete(previous) is False
    with Session(engine) as session:
        assert SocialService(SocialRepository(session)).friendship(1, 2).status == "blocked"


def test_conflict_response_when_state_changes_during_mutation(authed, engine):
    seed(engine, "pending", actor=2)
    # A database trigger can suppress a write even while SQLite writers are serialized.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER suppress_update BEFORE UPDATE ON friendships
            BEGIN SELECT RAISE(IGNORE); END
        """)
    response = authed.put(
        "/social/friendships/2", json={"user1_id": 1, "user2_id": 2, "status": "accepted"}
    )
    assert response.status_code == 409
    assert response.json() == {"error": "Relationship changed; reload before retrying"}


@pytest.mark.parametrize("id", ["0", "-1", "1", "no", "999999999999999999999"])
def test_friendship_invalid_path(authed, id):
    for method in ["GET", "PUT", "DELETE"]:
        response = authed.request(
            method,
            f"/social/friendships/{id}",
            json={"user1_id": 1, "user2_id": 2, "status": "blocked"},
        )
        assert response.status_code == 400
