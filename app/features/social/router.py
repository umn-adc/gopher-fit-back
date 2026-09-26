from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID
from app.core.pagination import Pagination
from app.features.auth.dependencies import CurrentUser
from app.features.social.models import (
    FriendshipRequest,
    FriendshipResponse,
    LeaderboardResponse,
    MuscleRankResponse,
)
from app.features.social.repository import SocialRepository
from app.features.social.service import SocialService

router = APIRouter(prefix="/social", tags=["social"])


def get_service(session: DatabaseSession) -> SocialService:
    return SocialService(SocialRepository(session))


Service = Annotated[SocialService, Depends(get_service)]


@router.get("/leaderboard")
def leaderboard(
    user: CurrentUser, service: Service, page: Pagination, exercise: str = ""
) -> list[LeaderboardResponse]:
    return service.leaderboard(exercise, page)


@router.get("/muscle-ranks")
def muscle_ranks(user: CurrentUser, service: Service, page: Pagination) -> list[MuscleRankResponse]:
    return service.muscle_ranks(user, page)


@router.get("/friendships")
def friendships(user: CurrentUser, service: Service, page: Pagination) -> list[FriendshipResponse]:
    return service.friendships(user, page=page)


@router.get("/friendships/accepted")
def accepted(user: CurrentUser, service: Service, page: Pagination) -> list[FriendshipResponse]:
    return service.friendships(user, "accepted", page)


@router.get("/friendships/outpending")
def outgoing_requests(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "outpending", page)


@router.get("/friendships/inpending")
def incoming_requests(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "inpending", page)


@router.get("/friendships/outblocks")
def outgoing_blocks(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "outblocks", page)


@router.get("/friendships/inblocks")
def incoming_blocks(
    user: CurrentUser, service: Service, page: Pagination
) -> list[FriendshipResponse]:
    return service.friendships(user, "inblocks", page)


@router.post("/friendships", status_code=201)
def create_friendship(
    request: FriendshipRequest, user: CurrentUser, service: Service
) -> FriendshipResponse:
    return service.create(user, request)


@router.get("/friendships/{user2_id}")
def friendship(
    user2_id: PositiveResourceID, user: CurrentUser, service: Service
) -> FriendshipResponse:
    return service.friendship(user, user2_id)


@router.put("/friendships/{user2_id}")
def update_friendship(
    user2_id: PositiveResourceID,
    request: FriendshipRequest,
    user: CurrentUser,
    service: Service,
) -> FriendshipResponse:
    return service.update(user, user2_id, request)


@router.delete("/friendships/{user2_id}", status_code=204)
def delete_friendship(
    user2_id: PositiveResourceID, user: CurrentUser, service: Service
) -> Response:
    service.delete(user, user2_id)
    return Response(status_code=204)
