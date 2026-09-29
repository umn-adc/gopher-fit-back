from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID
from app.core.responses import errors
from app.features.auth.dependencies import CurrentUser
from app.features.auth.repository import AuthRepository
from app.features.profile.models import (
    PasswordRequest,
    PasswordResponse,
    ProfileRequest,
    ProfileResponse,
    PublicProfileResponse,
    UsernameRequest,
    UsernameResponse,
)
from app.features.profile.repository import ProfileRepository
from app.features.profile.service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"], responses=errors(401, 500))


def get_service(session: DatabaseSession) -> ProfileService:
    return ProfileService(ProfileRepository(session), AuthRepository(session))


Service = Annotated[ProfileService, Depends(get_service)]


@router.get("/", responses=errors((404, "Profile not found")))
def get_profile(user: CurrentUser, service: Service) -> ProfileResponse:
    return service.get(user)


@router.put("/", responses=errors(400, (404, "Profile not found")))
def update_profile(request: ProfileRequest, user: CurrentUser, service: Service) -> ProfileResponse:
    return service.update(user, request)


@router.put("/username", responses=errors(400, (409, "Username already exists")))
def update_username(
    request: UsernameRequest, user: CurrentUser, service: Service
) -> UsernameResponse:
    return service.update_username(user, request.username)


@router.put(
    "/password",
    responses=errors(
        400,
        (401, "Access token rejected or old password incorrect"),
        429,
    ),
)
def update_password(
    request: PasswordRequest, user: CurrentUser, service: Service
) -> PasswordResponse:
    return service.update_password(user, request)


@router.get("/{id}", responses=errors(400, (404, "User not found")))
def public_profile(
    id: PositiveResourceID, user: CurrentUser, service: Service
) -> PublicProfileResponse:
    return service.public(id)
