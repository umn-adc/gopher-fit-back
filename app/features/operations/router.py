import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.features.operations.models import HealthResponse

router = APIRouter(tags=["operations"])
metrics_bearer = HTTPBearer(auto_error=False, scheme_name="MetricsBearer")


@router.get("/health/live")
def liveness() -> HealthResponse:
    return HealthResponse(status="alive")


@router.get(
    "/health/ready", response_model=HealthResponse, responses={503: {"description": "Not ready"}}
)
def readiness(request: Request) -> HealthResponse | JSONResponse:
    if not request.app.state.operations.ready():
        return JSONResponse({"error": "Not ready"}, status_code=503)
    return HealthResponse(status="ready")


@router.get(
    "/metrics",
    response_class=Response,
    responses={401: {"description": "Requires metrics token"}, 404: {"description": "Disabled"}},
)
def metrics(
    request: Request,
    _: Annotated[HTTPAuthorizationCredentials | None, Depends(metrics_bearer)],
) -> Response:
    expected = request.app.state.settings.metrics_token
    if expected is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if not hmac.compare_digest(
        request.headers.get("Authorization", "").encode(),
        ("Bearer " + expected.get_secret_value()).encode(),
    ):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return Response(request.app.state.metrics.render(), media_type="text/plain; version=0.0.4")
