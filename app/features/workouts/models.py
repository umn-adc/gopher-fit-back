from datetime import datetime
from typing import Any

from pydantic import Field, model_serializer
from sqlalchemy import REAL, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema
from app.core.validation import Name, NonnegativeFloat, NonnegativeInt, Timestamp


class WorkoutORM(Base):
    __tablename__ = "workouts"
    __table_args__ = (
        Index("workouts_user_id", "user_id"),
        Index("workouts_user_occurred_id", "user_id", "occurred_at", "id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workout_name: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[int | None]
    occurred_at: Mapped[str | None] = mapped_column(Text)


class WorkoutItemORM(Base):
    __tablename__ = "workout_item"
    __table_args__ = (
        Index("workout_item_workout_id", "workout_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, nullable=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"))
    exercise_name: Mapped[str | None] = mapped_column(Text)
    sets: Mapped[int | None]
    reps: Mapped[int | None]
    weight: Mapped[float | None] = mapped_column(REAL)
    duration_minutes: Mapped[float | None] = mapped_column(REAL)


class PersonalRecordORM(Base):
    __tablename__ = "personal_records"
    __table_args__ = (
        CheckConstraint("length(exercise_key) > 0"),
        CheckConstraint("max_weight > 0"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_key: Mapped[str] = mapped_column(Text, primary_key=True)
    exercise_name: Mapped[str] = mapped_column(Text)
    max_weight: Mapped[float] = mapped_column(REAL)
    source_workout_item_id: Mapped[int] = mapped_column(
        ForeignKey("workout_item.id", ondelete="CASCADE")
    )


Index(
    "personal_records_exercise_weight",
    PersonalRecordORM.exercise_key,
    PersonalRecordORM.max_weight.desc(),
    PersonalRecordORM.user_id,
)


class WorkoutItemRequest(RequestSchema):
    exercise_name: Name
    sets: NonnegativeInt = 0
    reps: NonnegativeInt = 0
    weight: NonnegativeFloat = 0
    duration_minutes: NonnegativeFloat = 0


class NestedWorkoutItemRequest(WorkoutItemRequest):
    id: int = Field(default=0, ge=0)
    workout_id: int = Field(default=0, ge=0)


class WorkoutItemResponse(Schema):
    id: int
    workout_id: int
    exercise_name: str
    sets: int = 0
    reps: int = 0
    weight: float = 0
    duration_minutes: float = 0


class WorkoutRequest(RequestSchema):
    workout_name: Name
    duration: NonnegativeInt = 0
    occurred_at: Timestamp | None = Field(
        default=None,
        description="ISO 8601 with offset; null means unknown; omitted on PUT preserves",
    )
    items: list[NestedWorkoutItemRequest] | None = Field(default=None, max_length=500)


class WorkoutResponse(Schema):
    id: int
    user_id: int
    workout_name: str
    duration: int
    occurred_at: datetime | None = None
    items: list[WorkoutItemResponse] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def omit_empty_items(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if not self.items:
            data.pop("items", None)
        return data
