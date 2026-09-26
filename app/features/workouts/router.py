from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.database import DatabaseSession
from app.core.http import PositiveResourceID, ResourceID
from app.core.pagination import Pagination
from app.core.validation import Timestamp
from app.features.auth.dependencies import CurrentUser
from app.features.workouts.models import (
    WorkoutItemRequest,
    WorkoutItemResponse,
    WorkoutRequest,
    WorkoutResponse,
)
from app.features.workouts.repository import WorkoutRepository
from app.features.workouts.service import WorkoutService

router = APIRouter(prefix="/workouts", tags=["workouts"])


def get_service(session: DatabaseSession) -> WorkoutService:
    return WorkoutService(WorkoutRepository(session))


Service = Annotated[WorkoutService, Depends(get_service)]


@router.get("/")
def workouts(
    user: CurrentUser,
    service: Service,
    page: Pagination,
    start: Timestamp | None = None,
    end: Timestamp | None = None,
) -> list[WorkoutResponse]:
    return service.workouts(user, page, start, end)


@router.post("/", status_code=201)
def create_workout(request: WorkoutRequest, user: CurrentUser, service: Service) -> WorkoutResponse:
    return service.create_workout(user, request)


@router.get("/{id}")
def workout(id: ResourceID, user: CurrentUser, service: Service) -> WorkoutResponse:
    return service.workout(user, id)


@router.put("/{id}")
def update_workout(
    id: ResourceID, request: WorkoutRequest, user: CurrentUser, service: Service
) -> WorkoutResponse:
    return service.update_workout(user, id, request)


@router.delete("/{id}", status_code=204)
def delete_workout(id: PositiveResourceID, user: CurrentUser, service: Service) -> Response:
    service.delete_workout(user, id)
    return Response(status_code=204)


@router.post("/{id}/items", status_code=201)
def create_item(
    id: PositiveResourceID, request: WorkoutItemRequest, user: CurrentUser, service: Service
) -> WorkoutItemResponse:
    return service.create_item(user, id, request)


@router.put("/{id}/items/{itemId}", status_code=204)
def update_item(
    id: PositiveResourceID,
    itemId: PositiveResourceID,
    request: WorkoutItemRequest,
    user: CurrentUser,
    service: Service,
) -> Response:
    service.update_item(user, id, itemId, request)
    return Response(status_code=204)


@router.delete("/{id}/items/{itemId}", status_code=204)
def delete_item(
    id: PositiveResourceID,
    itemId: PositiveResourceID,
    user: CurrentUser,
    service: Service,
) -> Response:
    service.delete_item(user, id, itemId)
    return Response(status_code=204)
