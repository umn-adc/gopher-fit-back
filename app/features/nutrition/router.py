from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID, ResourceID
from app.core.pagination import Pagination
from app.features.auth.dependencies import CurrentUser
from app.features.nutrition.models import (
    MacroGoalsRequest,
    MacroGoalsResponse,
    MealItemRequest,
    MealItemResponse,
    MealRequest,
    MealResponse,
)
from app.features.nutrition.repository import NutritionRepository
from app.features.nutrition.service import NutritionService

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def get_service(session: DatabaseSession) -> NutritionService:
    return NutritionService(NutritionRepository(session))


Service = Annotated[NutritionService, Depends(get_service)]


@router.get("/meals")
def meals(user: CurrentUser, service: Service, page: Pagination) -> list[MealResponse]:
    return service.meals(user, page)


@router.post("/meals", status_code=201)
def create_meal(request: MealRequest, user: CurrentUser, service: Service) -> MealResponse:
    return service.create_meal(user, request)


@router.get("/meals/{id}")
def meal(id: ResourceID, user: CurrentUser, service: Service) -> MealResponse:
    return service.meal(user, id)


@router.put("/meals/{id}", status_code=204)
def update_meal(
    id: ResourceID, request: MealRequest, user: CurrentUser, service: Service
) -> Response:
    service.update_meal(user, id, request)
    return Response(status_code=204)


@router.delete("/meals/{id}", status_code=204)
def delete_meal(id: ResourceID, user: CurrentUser, service: Service) -> Response:
    service.delete_meal(user, id)
    return Response(status_code=204)


@router.post("/meals/{id}/items", status_code=201)
def create_item(
    id: ResourceID, request: MealItemRequest, user: CurrentUser, service: Service
) -> MealItemResponse:
    return service.create_item(user, id, request)


@router.put("/meals/{id}/items/{itemId}")
def update_item(
    id: PositiveResourceID,
    itemId: PositiveResourceID,
    request: MealItemRequest,
    user: CurrentUser,
    service: Service,
) -> MealItemResponse:
    return service.update_item(user, id, itemId, request)


@router.delete("/meals/{id}/items/{itemId}", status_code=204)
def delete_item(
    id: ResourceID, itemId: ResourceID, user: CurrentUser, service: Service
) -> Response:
    service.delete_item(user, id, itemId)
    return Response(status_code=204)


@router.get("/macros")
def macro_goals(user: CurrentUser, service: Service) -> MacroGoalsResponse:
    return service.macro_goals(user)


@router.put("/macros")
def update_macro_goals(
    request: MacroGoalsRequest, user: CurrentUser, service: Service
) -> MacroGoalsResponse:
    return service.update_macro_goals(user, request)
