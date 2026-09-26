from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema


class FriendshipORM(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user1_id < user2_id"),
        Index("friendships_user2_status", "user2_id", "status", "user1_id"),
        Index("friendships_user1_status", "user1_id", "status", "user2_id"),
        Index("friendships_actor", "action_user_id"),
        CheckConstraint("status IN ('pending', 'accepted', 'blocked')"),
    )

    user1_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user2_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    action_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str | None] = mapped_column(Text)


class FriendshipRequest(RequestSchema):
    user1_id: int = 0
    user2_id: int = 0
    status: str = ""


class FriendshipResponse(FriendshipRequest):
    action_user_id: int


class LeaderboardResponse(Schema):
    user_id: int
    username: str
    max_weight: float
    rank: int
    percentile: float


class MuscleRankResponse(Schema):
    user_id: int
    exercise_key: str
    exercise_name: str
    max_weight: float
    source_workout_item_id: int
    rank: int
    percentile: float
