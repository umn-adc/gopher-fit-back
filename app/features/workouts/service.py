import math
from collections.abc import Sequence
from datetime import datetime

from app.core.errors import InvalidInput, NotFound
from app.core.pagination import Page
from app.core.validation import timestamp_text
from app.features.workouts.exercises import display_name, exercise_key
from app.features.workouts.models import (
    WorkoutItemORM,
    WorkoutItemRequest,
    WorkoutItemResponse,
    WorkoutORM,
    WorkoutRequest,
    WorkoutResponse,
)
from app.features.workouts.repository import WorkoutRepository


def validate_item(item: WorkoutItemRequest) -> None:
    if not exercise_key(item.exercise_name) or item.weight < 0 or not math.isfinite(item.weight):
        raise InvalidInput("Exercise name is required and weight must be finite and nonnegative")


class WorkoutService:
    def __init__(self, repository: WorkoutRepository):
        self.repository = repository

    def _owned_workout(self, user_id: int, workout_id: int) -> WorkoutORM:
        workout = self.repository.workout(user_id, workout_id)
        if workout is None:
            raise NotFound("Workout not found")
        return workout

    def _owned_item(self, user_id: int, workout_id: int, item_id: int) -> WorkoutItemORM:
        item = self.repository.item(user_id, workout_id, item_id)
        if item is None:
            raise NotFound("Workout item not found")
        return item

    def _response(
        self, workout: WorkoutORM, children: Sequence[WorkoutItemORM] | None = None
    ) -> WorkoutResponse:
        children = self.repository.items(workout.id) if children is None else children
        return WorkoutResponse(
            id=workout.id,
            user_id=workout.user_id,
            workout_name=workout.workout_name or "",
            duration=workout.duration or 0,
            occurred_at=datetime.fromisoformat(workout.occurred_at)
            if workout.occurred_at
            else None,
            items=[WorkoutItemResponse.model_validate(item) for item in children],
        )

    def refresh_records(self, user_id: int, names: list[str]) -> None:
        keys = {exercise_key(name) for name in names} - {""}
        if not keys:
            return
        best: dict[str, tuple[float, int, str]] = {}
        for item in self.repository.record_candidates(user_id):
            name = display_name(item.exercise_name or "")
            key = exercise_key(name)
            weight = item.weight
            if key not in keys or weight is None or weight <= 0 or not math.isfinite(weight):
                continue
            candidate = (weight, -item.id, name)
            if key not in best or candidate[:2] > best[key][:2]:
                best[key] = candidate
        for key in sorted(keys):
            if key in best:
                weight, negative_id, name = best[key]
                self.repository.save_record(user_id, key, name, weight, -negative_id)
            else:
                self.repository.delete_record(user_id, key)

    def workouts(
        self, user_id: int, page: Page, start: datetime | None, end: datetime | None
    ) -> list[WorkoutResponse]:
        if start is not None and end is not None and start >= end:
            raise InvalidInput("start must be before end")
        workouts = self.repository.workouts(
            user_id,
            page,
            timestamp_text(start) if start else None,
            timestamp_text(end) if end else None,
        )
        children = self.repository.items_for([workout.id for workout in workouts])
        return [self._response(workout, children[workout.id]) for workout in workouts]

    def workout(self, user_id: int, workout_id: int) -> WorkoutResponse:
        return self._response(self._owned_workout(user_id, workout_id))

    def create_workout(self, user_id: int, request: WorkoutRequest) -> WorkoutResponse:
        for item in request.items or []:
            if item.id or item.workout_id:
                raise InvalidInput("New nested items cannot specify existing IDs")
            validate_item(item)
        workout = self.repository.create_workout(user_id, request)
        for item in request.items or []:
            self.repository.create_item(workout.id, item)
        self.refresh_records(user_id, [item.exercise_name for item in request.items or []])
        return self._response(workout)

    def update_workout(
        self, user_id: int, workout_id: int, request: WorkoutRequest
    ) -> WorkoutResponse:
        workout = self._owned_workout(user_id, workout_id)
        if request.items is not None:
            existing = {item.id: item for item in self.repository.items(workout_id)}
            seen: set[int] = set()
            names = [item.exercise_name or "" for item in existing.values()]
            for item in request.items:
                validate_item(item)
                if item.workout_id not in (0, workout_id) or (item.id and item.id not in existing):
                    raise NotFound("Workout item not found")
                if item.id and item.id in seen:
                    raise InvalidInput("Duplicate nested item ID")
                seen.add(item.id)
                names.append(item.exercise_name)
            for item in request.items:
                if item.id:
                    self.repository.update_item(existing[item.id], item)
                else:
                    self.repository.create_item(workout_id, item)
            for item_id, stored in existing.items():
                if item_id not in seen:
                    self.repository.delete_item(stored)
            self.refresh_records(user_id, names)
        self.repository.update_workout(workout, request)
        return self._response(workout)

    def delete_workout(self, user_id: int, workout_id: int) -> None:
        workout = self._owned_workout(user_id, workout_id)
        names = [item.exercise_name or "" for item in self.repository.items(workout_id)]
        self.repository.delete_workout(workout)
        self.refresh_records(user_id, names)

    def create_item(
        self, user_id: int, workout_id: int, request: WorkoutItemRequest
    ) -> WorkoutItemResponse:
        validate_item(request)
        self._owned_workout(user_id, workout_id)
        item = self.repository.create_item(workout_id, request)
        self.refresh_records(user_id, [request.exercise_name])
        return WorkoutItemResponse.model_validate(item)

    def update_item(
        self, user_id: int, workout_id: int, item_id: int, request: WorkoutItemRequest
    ) -> None:
        validate_item(request)
        item = self._owned_item(user_id, workout_id, item_id)
        old_name = item.exercise_name or ""
        self.repository.update_item(item, request)
        self.refresh_records(user_id, [old_name, request.exercise_name])

    def delete_item(self, user_id: int, workout_id: int, item_id: int) -> None:
        item = self._owned_item(user_id, workout_id, item_id)
        old_name = item.exercise_name or ""
        self.repository.delete_item(item)
        self.refresh_records(user_id, [old_name])
