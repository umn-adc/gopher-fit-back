from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.core.pagination import Page
from app.features.nutrition.models import (
    MacroGoalsORM,
    MacroGoalsRequest,
    MealItemORM,
    MealItemRequest,
    MealORM,
    MealRequest,
)


class NutritionRepository:
    def __init__(self, session: Session):
        self.session = session

    def meals(self, user_id: int, page: Page) -> Sequence[MealORM]:
        return self.session.scalars(
            select(MealORM)
            .where(MealORM.user_id == user_id)
            .order_by(MealORM.id)
            .limit(page.limit)
            .offset(page.offset)
        ).all()

    def meal(self, user_id: int, meal_id: int) -> MealORM | None:
        return self.session.scalar(
            select(MealORM).where(MealORM.id == meal_id, MealORM.user_id == user_id)
        )

    def items(self, meal_id: int) -> Sequence[MealItemORM]:
        return self.session.scalars(
            select(MealItemORM).where(MealItemORM.meal_id == meal_id).order_by(MealItemORM.id)
        ).all()

    def items_for(self, parent_ids: list[int]) -> dict[int, list[MealItemORM]]:
        grouped: dict[int, list[MealItemORM]] = {parent_id: [] for parent_id in parent_ids}
        if parent_ids:
            rows = self.session.scalars(
                select(MealItemORM)
                .where(MealItemORM.meal_id.in_(parent_ids))
                .order_by(MealItemORM.id)
            )
            for row in rows:
                grouped[row.meal_id].append(row)
        return grouped

    def item(self, user_id: int, meal_id: int, item_id: int) -> MealItemORM | None:
        return self.session.scalar(
            select(MealItemORM)
            .join(MealORM)
            .where(
                MealItemORM.id == item_id,
                MealItemORM.meal_id == meal_id,
                MealORM.user_id == user_id,
            )
        )

    def create_meal(self, user_id: int, request: MealRequest) -> MealORM:
        meal = MealORM(
            user_id=user_id, date=request.date, meal_type=request.meal_type, time=request.time
        )
        self.session.add(meal)
        self.session.flush()
        return meal

    def update_meal(self, meal: MealORM, request: MealRequest) -> None:
        meal.date, meal.meal_type, meal.time = request.date, request.meal_type, request.time
        self.session.flush()

    def delete_meal(self, meal: MealORM) -> None:
        self.session.execute(delete(MealORM).where(MealORM.id == meal.id))

    def create_item(self, meal_id: int, request: MealItemRequest) -> MealItemORM:
        item = MealItemORM(
            meal_id=meal_id,
            name=request.name,
            calories=request.calories,
            protein=request.protein,
            carbs=request.carbs,
            fat=request.fat,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def update_item(self, item: MealItemORM, request: MealItemRequest) -> None:
        item.name = request.name
        item.calories, item.protein = request.calories, request.protein
        item.carbs, item.fat = request.carbs, request.fat
        self.session.flush()

    def delete_item(self, item: MealItemORM) -> None:
        self.session.delete(item)
        self.session.flush()

    def macro_goals(self, user_id: int) -> MacroGoalsORM | None:
        return self.session.get(MacroGoalsORM, user_id)

    def save_macro_goals(self, user_id: int, request: MacroGoalsRequest) -> None:
        statement = insert(MacroGoalsORM).values(user_id=user_id, **request.model_dump())
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[MacroGoalsORM.user_id], set_=request.model_dump()
            )
        )
