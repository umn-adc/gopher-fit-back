from collections.abc import Sequence

from app.core.errors import InvalidInput, NotFound
from app.core.pagination import Page
from app.features.nutrition.models import (
    FavoriteMealItemORM,
    FavoriteMealItemResponse,
    FavoriteMealORM,
    FavoriteMealRequest,
    FavoriteMealResponse,
    LogFavoriteRequest,
    MacroGoalsRequest,
    MacroGoalsResponse,
    MealItemORM,
    MealItemRequest,
    MealItemResponse,
    MealORM,
    MealRequest,
    MealResponse,
    NestedMealItemRequest,
    NutritionSummaryResponse,
)
from app.features.nutrition.repository import NutritionRepository
from app.features.workouts.exercises import display_name


class NutritionService:
    def __init__(self, repository: NutritionRepository):
        self.repository = repository

    def _owned_meal(self, user_id: int, meal_id: int) -> MealORM:
        meal = self.repository.meal(user_id, meal_id)
        if meal is None:
            raise NotFound("Meal not found")
        return meal

    def _response(
        self, meal: MealORM, children: Sequence[MealItemORM] | None = None
    ) -> MealResponse:
        children = self.repository.items(meal.id) if children is None else children
        items = [MealItemResponse.model_validate(item) for item in children]
        return MealResponse(
            id=meal.id,
            user_id=meal.user_id,
            date=meal.date,
            meal_type=meal.meal_type,
            time=meal.time or "",
            items=items,
            total_calories=sum(item.calories for item in items),
        )

    def meals(self, user_id: int, page: Page, date: str | None = None) -> list[MealResponse]:
        meals = self.repository.meals(user_id, page, date)
        children = self.repository.items_for([meal.id for meal in meals])
        return [self._response(meal, children[meal.id]) for meal in meals]

    def meal(self, user_id: int, meal_id: int) -> MealResponse:
        return self._response(self._owned_meal(user_id, meal_id))

    def create_meal(self, user_id: int, request: MealRequest) -> MealResponse:
        meal = self.repository.create_meal(user_id, request)
        for item in request.items or []:
            if item.id or item.meal_id:
                raise InvalidInput("New nested items cannot specify existing IDs")
            self.repository.create_item(meal.id, item)
        return self._response(meal)

    def update_meal(self, user_id: int, meal_id: int, request: MealRequest) -> None:
        meal = self._owned_meal(user_id, meal_id)
        if request.items is not None:
            existing = {item.id: item for item in self.repository.items(meal_id)}
            seen: set[int] = set()
            for item in request.items:
                if item.meal_id not in (0, meal_id) or (item.id and item.id not in existing):
                    raise NotFound("Meal item not found")
                if item.id and item.id in seen:
                    raise InvalidInput("Duplicate nested item ID")
                seen.add(item.id)
            for item in request.items:
                if item.id:
                    self.repository.update_item(existing[item.id], item)
                else:
                    self.repository.create_item(meal_id, item)
            for item_id, stored in existing.items():
                if item_id not in seen:
                    self.repository.delete_item(stored)
        self.repository.update_meal(meal, request)

    def delete_meal(self, user_id: int, meal_id: int) -> None:
        self.repository.delete_meal(self._owned_meal(user_id, meal_id))

    def create_item(self, user_id: int, meal_id: int, request: MealItemRequest) -> MealItemResponse:
        self._owned_meal(user_id, meal_id)
        return MealItemResponse.model_validate(self.repository.create_item(meal_id, request))

    def update_item(
        self, user_id: int, meal_id: int, item_id: int, request: MealItemRequest
    ) -> MealItemResponse:
        if (
            not display_name(request.name)
            or min(request.calories, request.protein, request.carbs, request.fat) < 0
        ):
            raise InvalidInput("Name is required and nutrition values must be nonnegative")
        item = self.repository.item(user_id, meal_id, item_id)
        if item is None:
            raise NotFound("Meal item not found")
        self.repository.update_item(item, request)
        return MealItemResponse.model_validate(item)

    def delete_item(self, user_id: int, meal_id: int, item_id: int) -> None:
        item = self.repository.item(user_id, meal_id, item_id)
        if item is None:
            raise NotFound("Meal item not found")
        self.repository.delete_item(item)

    def summary(self, user_id: int, date: str) -> NutritionSummaryResponse:
        calories, protein, carbs, fat = self.repository.totals(user_id, date)
        goals = self.repository.macro_goals(user_id)
        return NutritionSummaryResponse(
            date=date,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            targets=None if goals is None else MacroGoalsResponse.model_validate(goals),
        )

    def macro_goals(self, user_id: int) -> MacroGoalsResponse:
        goals = self.repository.macro_goals(user_id)
        if goals is None:
            raise NotFound("Macro goals not found")
        return MacroGoalsResponse.model_validate(goals)

    def update_macro_goals(self, user_id: int, request: MacroGoalsRequest) -> MacroGoalsResponse:
        self.repository.save_macro_goals(user_id, request)
        return MacroGoalsResponse(user_id=user_id, **request.model_dump())

    def _owned_favorite(self, user_id: int, favorite_id: int) -> FavoriteMealORM:
        favorite = self.repository.favorite(user_id, favorite_id)
        if favorite is None:
            raise NotFound("Favorite meal not found")
        return favorite

    def _favorite_response(
        self, favorite: FavoriteMealORM, children: Sequence[FavoriteMealItemORM] | None = None
    ) -> FavoriteMealResponse:
        if children is None:
            children = self.repository.favorite_items_for([favorite.id])[favorite.id]
        items = [FavoriteMealItemResponse.model_validate(item) for item in children]
        return FavoriteMealResponse(
            id=favorite.id,
            user_id=favorite.user_id,
            name=favorite.name,
            meal_type=favorite.meal_type,
            total_calories=sum(item.calories for item in items),
            items=items,
        )

    def favorites(self, user_id: int, page: Page) -> list[FavoriteMealResponse]:
        favorites = self.repository.favorites(user_id, page)
        children = self.repository.favorite_items_for([favorite.id for favorite in favorites])
        return [self._favorite_response(favorite, children[favorite.id]) for favorite in favorites]

    def favorite(self, user_id: int, favorite_id: int) -> FavoriteMealResponse:
        return self._favorite_response(self._owned_favorite(user_id, favorite_id))

    def create_favorite(self, user_id: int, request: FavoriteMealRequest) -> FavoriteMealResponse:
        favorite = self.repository.create_favorite(user_id, request)
        self.repository.replace_favorite_items(favorite.id, request.items or [])
        return self._favorite_response(favorite)

    def update_favorite(
        self, user_id: int, favorite_id: int, request: FavoriteMealRequest
    ) -> FavoriteMealResponse:
        favorite = self._owned_favorite(user_id, favorite_id)
        self.repository.update_favorite(favorite, request)
        if request.items is not None:
            self.repository.replace_favorite_items(favorite.id, request.items)
        return self._favorite_response(favorite)

    def delete_favorite(self, user_id: int, favorite_id: int) -> None:
        self.repository.delete_favorite(self._owned_favorite(user_id, favorite_id))

    def log_favorite(
        self, user_id: int, favorite_id: int, request: LogFavoriteRequest
    ) -> MealResponse:
        """Create an ordinary meal from the template; later template edits don't change it."""
        favorite = self._owned_favorite(user_id, favorite_id)
        items = self.repository.favorite_items_for([favorite.id])[favorite.id]
        meal = MealRequest(
            date=request.date,
            time=request.time,
            meal_type=request.meal_type or favorite.meal_type,
            items=[
                NestedMealItemRequest(
                    name=item.name,
                    calories=item.calories,
                    protein=item.protein,
                    carbs=item.carbs,
                    fat=item.fat,
                )
                for item in items
            ],
        )
        return self.create_meal(user_id, meal)
