import re
from datetime import date as date_value
from datetime import time as time_value
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator
from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema
from app.core.validation import Name, NonnegativeInt


def real_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Use YYYY-MM-DD")
    date_value.fromisoformat(value)
    return value


# Meal dates are local calendar dates; the API never infers a timezone.
MealDate = Annotated[str, AfterValidator(real_date)]


class MealORM(Base):
    __tablename__ = "meals"
    __table_args__ = (
        Index("meals_user_id_id", "user_id", "id"),
        Index("meals_user_date_id", "user_id", "date", "id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[str] = mapped_column(Text)
    meal_type: Mapped[str] = mapped_column(Text)
    time: Mapped[str | None] = mapped_column(Text)


class MealItemORM(Base):
    __tablename__ = "meal_items"
    __table_args__ = (Index("meal_items_meal_id", "meal_id"), {"sqlite_autoincrement": True})

    id: Mapped[int] = mapped_column(primary_key=True, nullable=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    calories: Mapped[int | None] = mapped_column(server_default=text("0"))
    protein: Mapped[int | None] = mapped_column(server_default=text("0"))
    carbs: Mapped[int | None] = mapped_column(server_default=text("0"))
    fat: Mapped[int | None] = mapped_column(server_default=text("0"))


class MacroGoalsORM(Base):
    __tablename__ = "macro_goals"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=True
    )
    calories_target: Mapped[int | None]
    protein_target: Mapped[int | None]
    carbs_target: Mapped[int | None]
    fat_target: Mapped[int | None]


class MealItemRequest(RequestSchema):
    name: Name
    calories: NonnegativeInt = 0
    protein: NonnegativeInt = 0
    carbs: NonnegativeInt = 0
    fat: NonnegativeInt = 0


class NestedMealItemRequest(MealItemRequest):
    id: int = Field(default=0, ge=0)
    meal_id: int = Field(default=0, ge=0)


class MealItemResponse(Schema):
    id: int
    meal_id: int
    name: str
    calories: int = 0
    protein: int = 0
    carbs: int = 0
    fat: int = 0


class MealRequest(RequestSchema):
    date: MealDate
    meal_type: Name
    time: str = ""
    total_calories: NonnegativeInt = 0
    items: list[NestedMealItemRequest] | None = Field(default=None, max_length=500)

    @field_validator("time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        if value:
            if not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", value):
                raise ValueError("Use HH:MM or HH:MM:SS local wall time")
            time_value.fromisoformat(value)
        return value


class MealResponse(Schema):
    id: int
    user_id: int
    date: str
    meal_type: str
    time: str
    total_calories: int = 0
    # Empty collections are omitted from responses, as the Go API did.
    items: list[MealItemResponse] = Field(default_factory=list, exclude_if=lambda items: not items)


class MacroGoalsRequest(RequestSchema):
    calories_target: NonnegativeInt = 0
    protein_target: NonnegativeInt = 0
    carbs_target: NonnegativeInt = 0
    fat_target: NonnegativeInt = 0


class MacroGoalsResponse(Schema):
    user_id: int
    calories_target: int = 0
    protein_target: int = 0
    carbs_target: int = 0
    fat_target: int = 0


class NutritionSummaryResponse(Schema):
    date: str
    calories: int
    protein: int
    carbs: int
    fat: int
    targets: MacroGoalsResponse | None = Field(description="null when no targets are set")
