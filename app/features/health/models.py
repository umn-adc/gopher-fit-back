"""Health data the user's phone imports from Apple Health or Health Connect.

The backend never contacts either platform. The app reads the data on the device
and uploads windows of it; imported data stays separate from logged workouts,
personal records and the profile.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema

Provider = Literal["apple_health", "health_connect"]
PROVIDERS: tuple[Provider, ...] = ("apple_health", "health_connect")
DataType = Literal[
    "steps", "active_energy", "heart_rate", "resting_heart_rate", "workouts", "weight"
]


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
