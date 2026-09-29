from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID
from app.core.pagination import Pagination
from app.core.responses import errors
from app.features.auth.dependencies import CurrentUser
from app.features.social.models import (
    FriendshipRequest,
    FriendshipResponse,
    LeaderboardResponse,
    MuscleRankResponse,
    UserSearchResponse,
)
from app.features.social.repository import SocialRepository
from app.features.social.service import SocialService

router = APIRouter(prefix="/social", tags=["social"], responses=errors(401, 500))


def get_service(session: DatabaseSession) -> SocialService:
    return SocialService(SocialRepository(session))


Service = Annotated[SocialService, Depends(get_service)]


@router.get("/users/search", responses=errors(400, 429))
def search_users(
    user: CurrentUser,
    service: Service,
    q: Annotated[
        str,
        Query(
            min_length=3,
            max_length=200,
            description="Username prefix; ASCII letters match case-insensitively",
        ),
    ],
) -> list[UserSearchResponse]:
    """Up to 20 users, excluding the caller and anyone with a block in either direction."""
    return service.search_users(user, q)


@router.get("/leaderboard", responses=errors(400))
def leaderboard(
    user: CurrentUser, service: Service, page: Pagination, exercise: str = ""
) -> list[LeaderboardResponse]:
    return service.leaderboard(exercise, page)


@router.get("/muscle-ranks", responses=errors(400))
def muscle_ranks(user: CurrentUser, service: Service, page: Pagination) -> list[MuscleRankResponse]:
    return service.muscle_ranks(user, page)


@router.get("/friendships", responses=errors(400))
def friendships(user: CurrentUser, service: Service, page: Pagination) -> list[FriendshipResponse]:
    return service.friendships(user, page=page)


@router.get("/friendships/accepted", responses=errors(400))
def accepted(user: CurrentUser, service: Service, page: Pagination) -> list[FriendshipResponse]:
    return service.friendships(user, "accepted", page)


@router.get("/friendships/outpending", responses=errors(400))
def outgoing_requests(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "outpending", page)


@router.get("/friendships/inpending", responses=errors(400))
def incoming_requests(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "inpending", page)


@router.get("/friendships/outblocks", responses=errors(400))
def outgoing_blocks(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "outblocks", page)


@router.get("/friendships/inblocks", responses=errors(400))
def incoming_blocks(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "inblocks", page)


@router.post(
    "/friendships",
    status_code=201,
    responses=errors(400, (404, "User not found"), (409, "Friendship already exists")),
)
def create_friendship(
    request: FriendshipRequest, user: CurrentUser, service: Service
) -> FriendshipResponse:
    return service.create(user, request)


@router.get("/friendships/{user2_id}", responses=errors(400, 404))
def friendship(
    user2_id: PositiveResourceID, user: CurrentUser, service: Service
) -> FriendshipResponse:
    return service.friendship(user, user2_id)


@router.put(
    "/friendships/{user2_id}",
    responses=errors(400, 404, (409, "Relationship changed; reload before retrying")),
)
def update_friendship(
    user2_id: PositiveResourceID,
    request: FriendshipRequest,
    user: CurrentUser,
    service: Service,
) -> FriendshipResponse:
    return service.update(user, user2_id, request)


@router.delete(
    "/friendships/{user2_id}",
    status_code=204,
    responses=errors(400, 404, (409, "Relationship changed; reload before retrying")),
)
def delete_friendship(
    user2_id: PositiveResourceID, user: CurrentUser, service: Service
) -> Response:
    service.delete(user, user2_id)
    return Response(status_code=204)
