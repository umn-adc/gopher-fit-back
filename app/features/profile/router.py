from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID
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

router = APIRouter(prefix="/profile", tags=["profile"])


def get_service(session: DatabaseSession) -> ProfileService:
    return ProfileService(ProfileRepository(session), AuthRepository(session))


Service = Annotated[ProfileService, Depends(get_service)]


@router.get("/")
def get_profile(user: CurrentUser, service: Service) -> ProfileResponse:
    return service.get(user)


@router.put("/")
def update_profile(request: ProfileRequest, user: CurrentUser, service: Service) -> ProfileResponse:
    return service.update(user, request)


@router.put("/username")
def update_username(
    request: UsernameRequest, user: CurrentUser, service: Service
) -> UsernameResponse:
    return service.update_username(user, request.username)


@router.put("/password")
def update_password(
    request: PasswordRequest, user: CurrentUser, service: Service
) -> PasswordResponse:
    return service.update_password(user, request)


@router.get("/{id}")
def public_profile(
    id: PositiveResourceID, user: CurrentUser, service: Service
) -> PublicProfileResponse:
    return service.public(id)
