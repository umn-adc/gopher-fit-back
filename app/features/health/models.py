"""Health data the user's phone imports from Apple Health or Health Connect.

The backend never contacts either platform. The app reads the data on the device
and uploads windows of it; imported data stays separate from logged workouts,
personal records and the profile.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema
from app.core.validation import Name, Timestamp
from app.features.nutrition.models import MealDate

Provider = Literal["apple_health", "health_connect"]
PROVIDERS: tuple[Provider, ...] = ("apple_health", "health_connect")
DataType = Literal[
    "steps", "active_energy", "heart_rate", "resting_heart_rate", "workouts", "weight"
]
ActivityType = Literal[
    "running", "walking", "cycling", "swimming", "strength_training", "hiit", "yoga", "other"
]

MAX_WINDOW_DAYS = 31
MAX_DAILY_ROWS = 31
MAX_SAMPLES = 500

Steps = Annotated[int, Field(ge=0, le=200_000)]
Kilocalories = Annotated[float, Field(ge=0, le=20_000)]
BeatsPerMinute = Annotated[float, Field(ge=20, le=250)]
Kilograms = Annotated[float, Field(ge=20, le=400)]


def unique_types(value: list[DataType]) -> list[DataType]:
    if len(set(value)) != len(value):
        raise ValueError("Duplicate data type")
    return value


DataTypes = Annotated[
    list[DataType], Field(min_length=1, max_length=6), AfterValidator(unique_types)
]


class HealthConnectionORM(Base):
    __tablename__ = "health_connections"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    connected: Mapped[bool]
    data_types: Mapped[str] = mapped_column(Text)  # JSON array of DataType
    connected_at: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[str | None] = mapped_column(Text)


class HealthDailyActivityORM(Base):
    __tablename__ = "health_daily_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "date"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    date: Mapped[str] = mapped_column(Text)
    steps: Mapped[int | None]
    active_energy_kcal: Mapped[float | None]
    resting_heart_rate_bpm: Mapped[float | None]
    heart_rate_min_bpm: Mapped[float | None]
    heart_rate_avg_bpm: Mapped[float | None]
    heart_rate_max_bpm: Mapped[float | None]


class HealthWorkoutORM(Base):
    __tablename__ = "health_workouts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_id"),
        Index("health_workouts_user_provider_start", "user_id", "provider", "start_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    activity_type: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    start_at: Mapped[str] = mapped_column(Text)
    end_at: Mapped[str] = mapped_column(Text)
    energy_kcal: Mapped[float | None]
    avg_heart_rate_bpm: Mapped[float | None]
    max_heart_rate_bpm: Mapped[float | None]
    source_name: Mapped[str | None] = mapped_column(Text)


class HealthWeightSampleORM(Base):
    __tablename__ = "health_weight_samples"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_id"),
        Index("health_weight_samples_user_measured", "user_id", "measured_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    measured_at: Mapped[str] = mapped_column(Text)
    weight_kg: Mapped[float]


class HealthConnectRequest(RequestSchema):
    data_types: DataTypes = Field(description="Types the user granted on the device")


class HealthConnectionResponse(Schema):
    provider: Provider
    connected: bool
    data_types: list[DataType]
    connected_at: datetime | None
    last_synced_at: datetime | None = Field(
        description="End of the most recently synced window; null before the first sync"
    )
    synced_days: int
    synced_workouts: int
    synced_weights: int


class HealthDailyRequest(RequestSchema):
    """One local calendar day. Values of types the request doesn't cover are ignored."""

    date: MealDate
    steps: Steps | None = None
    active_energy_kcal: Kilocalories | None = None
    resting_heart_rate_bpm: BeatsPerMinute | None = None
    heart_rate_min_bpm: BeatsPerMinute | None = None
    heart_rate_avg_bpm: BeatsPerMinute | None = None
    heart_rate_max_bpm: BeatsPerMinute | None = None

    @model_validator(mode="after")
    def ordered_heart_rate(self) -> Self:
        rates = [
            rate
            for rate in (self.heart_rate_min_bpm, self.heart_rate_avg_bpm, self.heart_rate_max_bpm)
            if rate is not None
        ]
        if rates != sorted(rates):
            raise ValueError("Heart rate min, avg and max are out of order")
        return self


class HealthWorkoutRequest(RequestSchema):
    external_id: Name = Field(description="HealthKit UUID or Health Connect record id")
    activity_type: ActivityType
    source_type: Name = Field(description="The platform's own workout type")
    start_at: Timestamp
    end_at: Timestamp
    energy_kcal: Kilocalories | None = None
    avg_heart_rate_bpm: BeatsPerMinute | None = None
    max_heart_rate_bpm: BeatsPerMinute | None = None
    source_name: Name | None = Field(default=None, description="App or device that recorded it")

    @model_validator(mode="after")
    def valid_session(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("Workout must end after it starts")
        if (self.end_at - self.start_at).total_seconds() > 24 * 3600:
            raise ValueError("Workout is longer than 24 hours")
        if (
            self.avg_heart_rate_bpm is not None
            and self.max_heart_rate_bpm is not None
            and self.avg_heart_rate_bpm > self.max_heart_rate_bpm
        ):
            raise ValueError("Workout average heart rate exceeds its maximum")
        return self


class HealthWeightRequest(RequestSchema):
    external_id: Name = Field(description="HealthKit UUID or Health Connect record id")
    measured_at: Timestamp
    weight_kg: Kilograms


class HealthSyncRequest(RequestSchema):
    since: Timestamp = Field(description="Window start (inclusive)")
    until: Timestamp = Field(description="Window end (exclusive), at most 31 days after since")
    data_types: DataTypes = Field(description="Types read for this window; others are untouched")
    daily: list[HealthDailyRequest] = Field(default_factory=list, max_length=MAX_DAILY_ROWS)
    workouts: list[HealthWorkoutRequest] = Field(default_factory=list, max_length=MAX_SAMPLES)
    weights: list[HealthWeightRequest] = Field(default_factory=list, max_length=MAX_SAMPLES)
