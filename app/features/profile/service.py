import json
import time

from app.core.errors import AuthenticationFailed, InvalidInput, NotFound, StorageFailure
from app.features.auth.repository import AuthRepository
from app.features.auth.security import hash_password, valid_password, verify_password
from app.features.profile.models import (
    PasswordRequest,
    PasswordResponse,
    ProfileRequest,
    ProfileResponse,
    PublicProfileResponse,
    UsernameResponse,
)
from app.features.profile.repository import ProfileRepository


def validate_profile(request: ProfileRequest) -> None:
    if request.gender not in {"Male", "Female", "Other"} or request.activity_level not in {
        "Sedentary",
        "Lightly Active",
        "Moderately Active",
        "Very Active",
        "Extra Active",
    }:
        raise InvalidInput("Invalid profile")


class ProfileService:
    def __init__(self, repository: ProfileRepository, auth: AuthRepository):
        self.repository = repository
        self.auth = auth

    def create(self, user_id: int, request: ProfileRequest) -> None:
        validate_profile(request)
        self.repository.create(user_id, request)

    def get(self, user_id: int) -> ProfileResponse:
        profile = self.repository.get(user_id)
        if profile is None:
            raise NotFound("Profile not found")
        try:
            return ProfileResponse(
                user_id=user_id,
                name=profile.name or "",
                age=profile.age or 0,
                height=profile.height or 0,
                weight=profile.weight or 0,
                gender=profile.gender or "",
                activity_level=profile.activity_level or "",
                goals=json.loads(profile.goals) if profile.goals else None,
                sports=json.loads(profile.sports) if profile.sports else None,
            )
        except ValueError as error:
            raise StorageFailure("Failed to decode profile") from error

    def public(self, user_id: int) -> PublicProfileResponse:
        user = self.repository.user(user_id)
        if user is None:
            raise NotFound("User not found")
        return PublicProfileResponse(user_id=user.id, username=user.username)

    def update(self, user_id: int, request: ProfileRequest) -> ProfileResponse:
        validate_profile(request)
        profile = self.repository.get(user_id)
        if profile is None:
            raise NotFound("Profile not found")
        self.repository.update(profile, request)
        return self.get(user_id)

    def update_username(self, user_id: int, username: str) -> UsernameResponse:
        if not username.strip():
            raise InvalidInput("Username cannot be empty")
        if not self.repository.update_username(user_id, username):
            raise NotFound("User not found")
        return UsernameResponse(username=username)

    def update_password(self, user_id: int, request: PasswordRequest) -> PasswordResponse:
        if not request.old_password or not request.new_password:
            raise InvalidInput("Password fields cannot be empty")
        user = self.repository.user(user_id)
        if user is None:
            raise NotFound("User not found")
        if not verify_password(request.old_password, user.password):
            raise AuthenticationFailed("Incorrect Password")
        if not valid_password(request.new_password):
            raise InvalidInput("New password is invalid")
        self.auth.change_password(user, hash_password(request.new_password), int(time.time()))
        return PasswordResponse()
