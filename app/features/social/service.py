from app.core.errors import Conflict, InvalidInput, NotFound
from app.core.pagination import DEFAULT_PAGE, Page
from app.features.social.models import (
    FriendshipRequest,
    FriendshipResponse,
    LeaderboardResponse,
    MuscleRankResponse,
)
from app.features.social.repository import Collection, SocialRepository
from app.features.workouts.exercises import exercise_key


def friendship_pair(user_id: int, other_id: int) -> tuple[int, int]:
    if user_id == other_id:
        raise InvalidInput("A relationship requires two distinct users")
    return min(user_id, other_id), max(user_id, other_id)


class SocialService:
    def __init__(self, repository: SocialRepository):
        self.repository = repository

    def friendships(
        self, user_id: int, collection: Collection = "all", page: Page = DEFAULT_PAGE
    ) -> list[FriendshipResponse]:
        return [
            FriendshipResponse.model_validate(item)
            for item in self.repository.friendships(user_id, collection, page)
        ]

    def friendship(self, user_id: int, other_id: int) -> FriendshipResponse:
        first, second = friendship_pair(user_id, other_id)
        friendship = self.repository.friendship(first, second)
        if friendship is None:
            raise NotFound("Friendship not found")
        return FriendshipResponse.model_validate(friendship)

    def create(self, user_id: int, request: FriendshipRequest) -> FriendshipResponse:
        first, second = sorted((request.user1_id, request.user2_id))
        if first <= 0 or first == second or user_id not in (first, second):
            raise InvalidInput("IDs must be distinct, positive, and include the caller")
        if request.status not in {"pending", "blocked"}:
            raise InvalidInput("New relationships must be pending or blocked")
        if not self.repository.users_exist(first, second):
            raise NotFound("User not found")
        return FriendshipResponse.model_validate(
            self.repository.create(first, second, user_id, request.status)
        )

    def update(self, user_id: int, other_id: int, request: FriendshipRequest) -> FriendshipResponse:
        first, second = friendship_pair(user_id, other_id)
        if request.status not in {"pending", "accepted", "blocked"}:
            raise InvalidInput("Invalid friendship status")
        if sorted((request.user1_id, request.user2_id)) != [first, second]:
            raise InvalidInput("Cannot change friend ids")
        previous = self.friendship(user_id, other_id)
        if request.status == previous.status:
            raise InvalidInput("Status must be changed on update")
        if previous.status == "blocked" and previous.action_user_id != user_id:
            raise InvalidInput("Cannot change users incoming block")
        if request.status == "accepted":
            if previous.status != "pending":
                raise InvalidInput("Cannot accept a non-pending request")
            if previous.action_user_id == user_id:
                raise InvalidInput("Cannot accept an outgoing pending request")
        if not self.repository.update(previous, user_id, request.status):
            raise Conflict("Relationship changed; reload before retrying")
        return FriendshipResponse(
            user1_id=first, user2_id=second, action_user_id=user_id, status=request.status
        )

    def delete(self, user_id: int, other_id: int) -> None:
        previous = self.friendship(user_id, other_id)
        if previous.status == "blocked" and previous.action_user_id != user_id:
            raise InvalidInput("Cannot delete another user's block")
        if not self.repository.delete(previous):
            raise Conflict("Relationship changed; reload before retrying")

    def leaderboard(self, exercise: str, page: Page) -> list[LeaderboardResponse]:
        key = exercise_key(exercise)
        if not key:
            raise InvalidInput("Exercise is required")
        return self.repository.leaderboard(key, page)

    def muscle_ranks(self, user_id: int, page: Page) -> list[MuscleRankResponse]:
        return self.repository.muscle_ranks(user_id, page)
