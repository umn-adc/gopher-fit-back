from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.core.pagination import Page
from app.core.validation import timestamp_text
from app.features.workouts.models import (
    PersonalRecordORM,
    WorkoutItemORM,
    WorkoutItemRequest,
    WorkoutORM,
    WorkoutRequest,
)


class WorkoutRepository:
    def __init__(self, session: Session):
        self.session = session

    def workouts(
        self, user_id: int, page: Page, start: str | None, end: str | None
    ) -> Sequence[WorkoutORM]:
        query = select(WorkoutORM).where(WorkoutORM.user_id == user_id)
        if start is not None:
            query = query.where(WorkoutORM.occurred_at >= start)
        if end is not None:
            query = query.where(WorkoutORM.occurred_at < end)
        return self.session.scalars(
            query.order_by(WorkoutORM.occurred_at.desc(), WorkoutORM.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        ).all()

    def workout(self, user_id: int, workout_id: int) -> WorkoutORM | None:
        return self.session.scalar(
            select(WorkoutORM).where(WorkoutORM.id == workout_id, WorkoutORM.user_id == user_id)
        )

    def items(self, workout_id: int) -> Sequence[WorkoutItemORM]:
        return self.session.scalars(
            select(WorkoutItemORM)
            .where(WorkoutItemORM.workout_id == workout_id)
            .order_by(WorkoutItemORM.id)
        ).all()

    def items_for(self, parent_ids: list[int]) -> dict[int, list[WorkoutItemORM]]:
        grouped: dict[int, list[WorkoutItemORM]] = {parent_id: [] for parent_id in parent_ids}
        if parent_ids:
            rows = self.session.scalars(
                select(WorkoutItemORM)
                .where(WorkoutItemORM.workout_id.in_(parent_ids))
                .order_by(WorkoutItemORM.id)
            )
            for row in rows:
                grouped[row.workout_id].append(row)
        return grouped

    def item(self, user_id: int, workout_id: int, item_id: int) -> WorkoutItemORM | None:
        return self.session.scalar(
            select(WorkoutItemORM)
            .join(WorkoutORM)
            .where(
                WorkoutItemORM.id == item_id,
                WorkoutItemORM.workout_id == workout_id,
                WorkoutORM.user_id == user_id,
            )
        )

    def create_workout(self, user_id: int, request: WorkoutRequest) -> WorkoutORM:
        workout = WorkoutORM(
            user_id=user_id,
            workout_name=request.workout_name,
            duration=request.duration,
            occurred_at=timestamp_text(request.occurred_at) if request.occurred_at else None,
        )
        self.session.add(workout)
        self.session.flush()
        return workout

    def update_workout(self, workout: WorkoutORM, request: WorkoutRequest) -> None:
        workout.workout_name, workout.duration = request.workout_name, request.duration
        if "occurred_at" in request.model_fields_set:
            workout.occurred_at = (
                timestamp_text(request.occurred_at) if request.occurred_at else None
            )
        self.session.flush()

    def delete_workout(self, workout: WorkoutORM) -> None:
        self.session.execute(delete(WorkoutORM).where(WorkoutORM.id == workout.id))

    def create_item(self, workout_id: int, request: WorkoutItemRequest) -> WorkoutItemORM:
        item = WorkoutItemORM(
            workout_id=workout_id,
            exercise_name=request.exercise_name,
            sets=request.sets,
            reps=request.reps,
            weight=request.weight,
            duration_minutes=request.duration_minutes,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def update_item(self, item: WorkoutItemORM, request: WorkoutItemRequest) -> None:
        item.exercise_name = request.exercise_name
        item.sets, item.reps, item.weight = request.sets, request.reps, request.weight
        item.duration_minutes = request.duration_minutes
        self.session.flush()

    def delete_item(self, item: WorkoutItemORM) -> None:
        self.session.delete(item)
        self.session.flush()

    def record_candidates(self, user_id: int) -> Sequence[WorkoutItemORM]:
        return self.session.scalars(
            select(WorkoutItemORM)
            .join(WorkoutORM)
            .where(WorkoutORM.user_id == user_id, WorkoutItemORM.weight > 0)
        ).all()

    def save_record(self, user_id: int, key: str, name: str, weight: float, source_id: int) -> None:
        statement = insert(PersonalRecordORM).values(
            user_id=user_id,
            exercise_key=key,
            exercise_name=name,
            max_weight=weight,
            source_workout_item_id=source_id,
        )
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[PersonalRecordORM.user_id, PersonalRecordORM.exercise_key],
                set_={
                    "exercise_name": name,
                    "max_weight": weight,
                    "source_workout_item_id": source_id,
                },
            )
        )

    def delete_record(self, user_id: int, key: str) -> None:
        self.session.execute(
            delete(PersonalRecordORM).where(
                PersonalRecordORM.user_id == user_id, PersonalRecordORM.exercise_key == key
            )
        )
