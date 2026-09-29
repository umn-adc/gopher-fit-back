from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID, ResourceID
from app.core.pagination import Pagination
from app.core.responses import errors
from app.features.auth.dependencies import CurrentUser
from app.features.nutrition.models import (
    FavoriteMealRequest,
    FavoriteMealResponse,
    LogFavoriteRequest,
    MacroGoalsRequest,
    MacroGoalsResponse,
    MealDate,
    MealItemRequest,
    MealItemResponse,
    MealRequest,
    MealResponse,
    NutritionSummaryResponse,
)
from app.features.nutrition.repository import NutritionRepository
from app.features.nutrition.service import NutritionService

router = APIRouter(prefix="/nutrition", tags=["nutrition"], responses=errors(401, 500))


def get_service(session: DatabaseSession) -> NutritionService:
    return NutritionService(NutritionRepository(session))


Service = Annotated[NutritionService, Depends(get_service)]
DATE = "Local calendar date, YYYY-MM-DD, compared with each meal's date"


@router.get("/meals", responses=errors(400))
def meals(
    user: CurrentUser,
    service: Service,
    page: Pagination,
    date: Annotated[MealDate | None, Query(description=DATE)] = None,
) -> list[MealResponse]:
    return service.meals(user, page, date)


@router.get("/summary", responses=errors(400))
def summary(
    user: CurrentUser, service: Service, date: Annotated[MealDate, Query(description=DATE)]
) -> NutritionSummaryResponse:
    return service.summary(user, date)


@router.post("/meals", status_code=201, responses=errors(400))
def create_meal(request: MealRequest, user: CurrentUser, service: Service) -> MealResponse:
    return service.create_meal(user, request)


@router.get("/meals/{id}", responses=errors(400, 404))
def meal(id: ResourceID, user: CurrentUser, service: Service) -> MealResponse:
    return service.meal(user, id)


@router.put("/meals/{id}", status_code=204, responses=errors(400, 404))
def update_meal(
    id: ResourceID, request: MealRequest, user: CurrentUser, service: Service
) -> Response:
    service.update_meal(user, id, request)
    return Response(status_code=204)


@router.delete("/meals/{id}", status_code=204, responses=errors(400, 404))
def delete_meal(id: ResourceID, user: CurrentUser, service: Service) -> Response:
    service.delete_meal(user, id)
    return Response(status_code=204)


@router.post("/meals/{id}/items", status_code=201, responses=errors(400, 404))
def create_item(
    id: ResourceID, request: MealItemRequest, user: CurrentUser, service: Service
) -> MealItemResponse:
    return service.create_item(user, id, request)


@router.put("/meals/{id}/items/{itemId}", responses=errors(400, 404))
def update_item(
    id: PositiveResourceID,
    itemId: PositiveResourceID,
    request: MealItemRequest,
    user: CurrentUser,
    service: Service,
) -> MealItemResponse:
    return service.update_item(user, id, itemId, request)


@router.delete("/meals/{id}/items/{itemId}", status_code=204, responses=errors(400, 404))
def delete_item(
    id: ResourceID, itemId: ResourceID, user: CurrentUser, service: Service
) -> Response:
    service.delete_item(user, id, itemId)
    return Response(status_code=204)


@router.get("/macros", responses=errors((404, "No macro targets configured")))
def macro_goals(user: CurrentUser, service: Service) -> MacroGoalsResponse:
    return service.macro_goals(user)


@router.put("/macros", responses=errors(400))
def update_macro_goals(
    request: MacroGoalsRequest, user: CurrentUser, service: Service
) -> MacroGoalsResponse:
    return service.update_macro_goals(user, request)


@router.get("/favorites", responses=errors(400))
def favorites(user: CurrentUser, service: Service, page: Pagination) -> list[FavoriteMealResponse]:
    return service.favorites(user, page)


@router.post("/favorites", status_code=201, responses=errors(400))
def create_favorite(
    request: FavoriteMealRequest, user: CurrentUser, service: Service
) -> FavoriteMealResponse:
    return service.create_favorite(user, request)


@router.get("/favorites/{id}", responses=errors(400, 404))
def favorite(id: PositiveResourceID, user: CurrentUser, service: Service) -> FavoriteMealResponse:
    return service.favorite(user, id)


@router.put("/favorites/{id}", responses=errors(400, 404))
def update_favorite(
    id: PositiveResourceID, request: FavoriteMealRequest, user: CurrentUser, service: Service
) -> FavoriteMealResponse:
    return service.update_favorite(user, id, request)


@router.delete("/favorites/{id}", status_code=204, responses=errors(400, 404))
def delete_favorite(id: PositiveResourceID, user: CurrentUser, service: Service) -> Response:
    service.delete_favorite(user, id)
    return Response(status_code=204)


@router.post("/favorites/{id}/log", status_code=201, responses=errors(400, 404))
def log_favorite(
    id: PositiveResourceID, request: LogFavoriteRequest, user: CurrentUser, service: Service
) -> MealResponse:
    return service.log_favorite(user, id, request)
