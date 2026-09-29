from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.core.pagination import Page
from app.features.nutrition.models import (
    FavoriteMealItemORM,
    FavoriteMealORM,
    FavoriteMealRequest,
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

    def meals(self, user_id: int, page: Page, date: str | None = None) -> Sequence[MealORM]:
        query = select(MealORM).where(MealORM.user_id == user_id)
        if date is not None:
            query = query.where(MealORM.date == date)
        return self.session.scalars(
            query.order_by(MealORM.id).limit(page.limit).offset(page.offset)
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

    def totals(self, user_id: int, date: str) -> tuple[int, int, int, int]:
        item = MealItemORM
        calories, protein, carbs, fat = self.session.execute(
            select(
                *(
                    func.coalesce(func.sum(column), 0)
                    for column in (item.calories, item.protein, item.carbs, item.fat)
                )
            )
            .select_from(item)
            .join(MealORM)
            .where(MealORM.user_id == user_id, MealORM.date == date)
        ).one()
        return calories, protein, carbs, fat

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

    def favorites(self, user_id: int, page: Page) -> Sequence[FavoriteMealORM]:
        return self.session.scalars(
            select(FavoriteMealORM)
            .where(FavoriteMealORM.user_id == user_id)
            .order_by(FavoriteMealORM.id)
            .limit(page.limit)
            .offset(page.offset)
        ).all()

    def favorite(self, user_id: int, favorite_id: int) -> FavoriteMealORM | None:
        return self.session.scalar(
            select(FavoriteMealORM).where(
                FavoriteMealORM.id == favorite_id, FavoriteMealORM.user_id == user_id
            )
        )

    def favorite_items_for(self, favorite_ids: list[int]) -> dict[int, list[FavoriteMealItemORM]]:
        grouped: dict[int, list[FavoriteMealItemORM]] = {id: [] for id in favorite_ids}
        if favorite_ids:
            rows = self.session.scalars(
                select(FavoriteMealItemORM)
                .where(FavoriteMealItemORM.favorite_id.in_(favorite_ids))
                .order_by(FavoriteMealItemORM.id)
            )
            for row in rows:
                grouped[row.favorite_id].append(row)
        return grouped

    def create_favorite(self, user_id: int, request: FavoriteMealRequest) -> FavoriteMealORM:
        favorite = FavoriteMealORM(user_id=user_id, name=request.name, meal_type=request.meal_type)
        self.session.add(favorite)
        self.session.flush()
        return favorite

    def update_favorite(self, favorite: FavoriteMealORM, request: FavoriteMealRequest) -> None:
        favorite.name, favorite.meal_type = request.name, request.meal_type
        self.session.flush()

    def replace_favorite_items(self, favorite_id: int, items: list[MealItemRequest]) -> None:
        self.session.execute(
            delete(FavoriteMealItemORM).where(FavoriteMealItemORM.favorite_id == favorite_id)
        )
        self.session.add_all(
            FavoriteMealItemORM(
                favorite_id=favorite_id,
                name=item.name,
                calories=item.calories,
                protein=item.protein,
                carbs=item.carbs,
                fat=item.fat,
            )
            for item in items
        )
        self.session.flush()

    def delete_favorite(self, favorite: FavoriteMealORM) -> None:
        self.session.execute(delete(FavoriteMealORM).where(FavoriteMealORM.id == favorite.id))
