from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from app.core.database import DatabaseSession
from app.core.responses import errors
from app.features.auth.dependencies import CurrentUser
from app.features.health.models import (
    HealthConnectionResponse,
    HealthConnectRequest,
    HealthSyncRequest,
    Provider,
)
from app.features.health.repository import HealthRepository
from app.features.health.service import HealthService

router = APIRouter(prefix="/health/connections", tags=["health"], responses=errors(401, 500))


def get_service(session: DatabaseSession) -> HealthService:
    return HealthService(HealthRepository(session))


Service = Annotated[HealthService, Depends(get_service)]
ProviderPath = Annotated[
    Provider, Path(description="apple_health (iOS HealthKit) or health_connect (Android)")
]


@router.get("")
def connections(user: CurrentUser, service: Service) -> list[HealthConnectionResponse]:
    return service.connections(user)


@router.put("/{provider}", responses=errors(400))
def connect(
    provider: ProviderPath, request: HealthConnectRequest, user: CurrentUser, service: Service
) -> HealthConnectionResponse:
    return service.connect(user, provider, request)


@router.delete("/{provider}", status_code=204, responses=errors(400))
def disconnect(provider: ProviderPath, user: CurrentUser, service: Service) -> Response:
    service.disconnect(user, provider)
    return Response(status_code=204)


@router.delete("/{provider}/data", status_code=204, responses=errors(400))
def delete_data(provider: ProviderPath, user: CurrentUser, service: Service) -> Response:
    service.delete_data(user, provider)
    return Response(status_code=204)


@router.post(
    "/{provider}/sync",
    responses=errors(400, (409, "The provider is not connected for this account"), 429),
)
def sync(
    provider: ProviderPath, request: HealthSyncRequest, user: CurrentUser, service: Service
) -> HealthConnectionResponse:
    return service.sync(user, provider, request)
