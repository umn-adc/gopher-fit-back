import json

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.features.auth.models import UserORM
from app.features.profile.models import ProfileORM, ProfileRequest


class ProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: int) -> ProfileORM | None:
        return self.session.get(ProfileORM, user_id)

    def user(self, user_id: int) -> UserORM | None:
        return self.session.get(UserORM, user_id)

    def create(self, user_id: int, request: ProfileRequest) -> None:
        # Explicit fields prevent registration credentials from entering the profile.
        self.session.add(
            ProfileORM(
                user_id=user_id,
                name=request.name,
                age=request.age,
                height=request.height,
                weight=request.weight,
                gender=request.gender,
                activity_level=request.activity_level,
                goals=json.dumps(request.goals),
                sports=json.dumps(request.sports),
            )
        )
        self.session.flush()

    def update(self, profile: ProfileORM, request: ProfileRequest) -> None:
        profile.name = request.name
        profile.age = request.age
        profile.height = request.height
        profile.weight = request.weight
        profile.gender = request.gender
        profile.activity_level = request.activity_level
        profile.goals = json.dumps(request.goals)
        profile.sports = json.dumps(request.sports)
        self.session.flush()

    def update_username(self, user_id: int, username: str) -> bool:
        try:
            return (
                self.session.connection()
                .execute(update(UserORM).where(UserORM.id == user_id).values(username=username))
                .rowcount
                > 0
            )
        except IntegrityError as error:
            if "UNIQUE constraint failed" in str(error.orig):
                raise Conflict("Username already exists") from error
            raise

    def update_password(self, user: UserORM, password: bytes) -> None:
        user.password = password
        self.session.flush()
