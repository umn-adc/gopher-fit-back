import pytest


@pytest.mark.parametrize(
    "path", ["/profile/", "/nutrition/meals", "/workouts/", "/social/friendships"]
)
def test_authentication_precedes_json_parsing(client, path):
    assert client.put(path, content="{").status_code == 401


def test_unknown_protected_route_still_requires_authentication(client, headers):
    assert client.get("/social/unknown").status_code == 401
    assert client.get("/social/unknown", headers=headers()).status_code == 404


@pytest.mark.parametrize(
    "path", ["/profile/", "/nutrition/meals", "/workouts/", "/social/friendships"]
)
def test_head_on_get_routes(authed, path):
    response = authed.head(path)
    assert response.status_code == 200
    assert response.content == b""


def test_go_root_redirects_and_noncanonical_slashes(client, headers):
    for root in ["auth", "profile", "nutrition", "workouts", "social", "swagger"]:
        response = client.get(f"/{root}?x=1", follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["location"].endswith(f"/{root}/?x=1")
    assert (
        client.get("/nutrition/meals/", headers=headers(), follow_redirects=False).status_code
        == 404
    )
