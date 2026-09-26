from collections.abc import Sequence
from typing import Literal

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.core.pagination import DEFAULT_PAGE, Page
from app.features.auth.models import UserORM
from app.features.social.models import (
    FriendshipORM,
    FriendshipResponse,
    LeaderboardResponse,
    MuscleRankResponse,
)
from app.features.workouts.models import PersonalRecordORM

Collection = Literal["all", "accepted", "outpending", "inpending", "outblocks", "inblocks"]


class SocialRepository:
    def __init__(self, session: Session):
        self.session = session

    def users_exist(self, first: int, second: int) -> bool:
        return (
            self.session.scalar(
                select(func.count()).select_from(UserORM).where(UserORM.id.in_([first, second]))
            )
            == 2
        )

    def friendships(
        self, user_id: int, collection: Collection, page: Page = DEFAULT_PAGE
    ) -> Sequence[FriendshipORM]:
        query = select(FriendshipORM).where(
            or_(FriendshipORM.user1_id == user_id, FriendshipORM.user2_id == user_id)
        )
        if collection == "accepted":
            query = query.where(FriendshipORM.status == "accepted")
        elif collection != "all":
            query = query.where(
                FriendshipORM.status == ("pending" if collection.endswith("pending") else "blocked")
            )
            if collection.startswith("out"):
                query = query.where(FriendshipORM.action_user_id == user_id)
            else:
                query = query.where(FriendshipORM.action_user_id != user_id)
        return self.session.scalars(
            query.order_by(FriendshipORM.user1_id, FriendshipORM.user2_id)
            .limit(page.limit)
            .offset(page.offset)
        ).all()

    def friendship(self, first: int, second: int) -> FriendshipORM | None:
        return self.session.get(FriendshipORM, (first, second))

    def create(self, first: int, second: int, actor: int, status: str) -> FriendshipORM:
        friendship = FriendshipORM(
            user1_id=first, user2_id=second, action_user_id=actor, status=status
        )
        self.session.add(friendship)
        try:
            self.session.flush()
        except IntegrityError as error:
            if "UNIQUE constraint failed" in str(error.orig):
                raise Conflict("Friendship already exists") from error
            raise
        return friendship

    def update(self, previous: FriendshipResponse, actor: int, status: str) -> bool:
        return (
            self.session.connection()
            .execute(
                update(FriendshipORM)
                .where(
                    FriendshipORM.user1_id == previous.user1_id,
                    FriendshipORM.user2_id == previous.user2_id,
                    FriendshipORM.action_user_id == previous.action_user_id,
                    FriendshipORM.status == previous.status,
                )
                .values(action_user_id=actor, status=status)
            )
            .rowcount
            > 0
        )

    def delete(self, previous: FriendshipResponse) -> bool:
        return (
            self.session.connection()
            .execute(
                delete(FriendshipORM).where(
                    FriendshipORM.user1_id == previous.user1_id,
                    FriendshipORM.user2_id == previous.user2_id,
                    FriendshipORM.action_user_id == previous.action_user_id,
                    FriendshipORM.status == previous.status,
                )
            )
            .rowcount
            > 0
        )

    def leaderboard(self, key: str, page: Page) -> list[LeaderboardResponse]:
        record = PersonalRecordORM
        ranked = (
            select(
                record.user_id,
                UserORM.username,
                record.max_weight,
                func.dense_rank().over(order_by=record.max_weight.desc()).label("rank"),
                (100 * func.cume_dist().over(order_by=record.max_weight)).label("percentile"),
            )
            .join(UserORM)
            .where(record.exercise_key == key)
        ).subquery()
        query = (
            select(ranked)
            .order_by(ranked.c.max_weight.desc(), ranked.c.user_id)
            .limit(page.limit)
            .offset(page.offset)
        )
        return [
            LeaderboardResponse.model_validate(row)
            for row in self.session.execute(query).mappings()
        ]

    def muscle_ranks(self, user_id: int, page: Page) -> list[MuscleRankResponse]:
        record = PersonalRecordORM
        ranked = select(
            record.user_id,
            record.exercise_key,
            record.exercise_name,
            record.max_weight,
            record.source_workout_item_id,
            func.dense_rank()
            .over(partition_by=record.exercise_key, order_by=record.max_weight.desc())
            .label("rank"),
            (
                100
                * func.cume_dist().over(
                    partition_by=record.exercise_key, order_by=record.max_weight
                )
            ).label("percentile"),
        ).subquery()
        query = (
            select(ranked)
            .where(ranked.c.user_id == user_id)
            .order_by(ranked.c.exercise_key)
            .limit(page.limit)
            .offset(page.offset)
        )
        return [
            MuscleRankResponse.model_validate(row) for row in self.session.execute(query).mappings()
        ]
