from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.database import DatabaseSession
from app.core.responses import errors
from app.features.auth.delivery import Delivery
from app.features.auth.dependencies import CurrentSession, CurrentUser, get_tokens
from app.features.auth.models import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    PasswordConfirmation,
    RecoveryAddressRequest,
    RecoveryConfirmation,
    RecoveryRequest,
    RefreshRequest,
    RegisterRequest,
    ResetRequest,
)
from app.features.auth.repository import AuthRepository
from app.features.auth.security import TokenService
from app.features.auth.service import AuthService
from app.features.profile.repository import ProfileRepository
from app.features.profile.service import ProfileService

# Every /auth route is throttled per client IP (see OperationsService.throttle).
router = APIRouter(prefix="/auth", tags=["auth"], responses=errors(429, 500))


def get_service(
    request: Request, session: DatabaseSession, tokens: Annotated[TokenService, Depends(get_tokens)]
) -> AuthService:
    repository = AuthRepository(session)
    return AuthService(
        repository,
        ProfileService(ProfileRepository(session), repository),
        tokens,
        request.app.state.settings,
    )


Service = Annotated[AuthService, Depends(get_service)]


def deliver(request: Request, delivery: Delivery | None) -> None:
    if delivery is not None:
        success = request.app.state.mailer.send(delivery)
        request.app.state.metrics.delivery(success)


@router.post("/register", status_code=201, responses=errors(400, (409, "Username already exists")))
def register(request: RegisterRequest, service: Service) -> AuthResponse:
    return service.register(request)


@router.post("/login", responses=errors(400, (401, "Invalid credentials")))
def login(request: LoginRequest, service: Service) -> AuthResponse:
    return service.login(request)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    responses=errors(400, (401, "Revoked, expired or reused token")),
)
def refresh(request: RefreshRequest, service: Service) -> AuthResponse | JSONResponse:
    result = service.refresh(request.refresh_token)
    if result is None:
        return JSONResponse({"error": "Invalid refresh token"}, status_code=401)
    return result


@router.post("/logout", status_code=204, responses=errors(401))
def logout(claims: CurrentSession, service: Service) -> Response:
    service.logout(claims)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204, responses=errors(401))
def logout_all(claims: CurrentSession, service: Service) -> Response:
    service.logout(claims, all_sessions=True)
    return Response(status_code=204)


@router.delete(
    "/account",
    status_code=204,
    responses=errors(400, (401, "Access token rejected or password incorrect")),
)
def delete_account(request: PasswordConfirmation, user: CurrentUser, service: Service) -> Response:
    service.delete_account(user, request.password)
    return Response(status_code=204)


@router.put(
    "/recovery-address",
    status_code=202,
    responses=errors(400, (401, "Access token rejected or password incorrect"), 503),
)
def enroll_recovery(
    body: RecoveryAddressRequest,
    user: CurrentUser,
    service: Service,
    request: Request,
    background: BackgroundTasks,
) -> MessageResponse:
    delivery = service.enroll(user, body.password, str(body.email))
    background.add_task(deliver, request, delivery)
    return MessageResponse(message="Verification requested")


@router.post("/recovery-address/confirm", status_code=204, responses=errors(400, 503))
def confirm_recovery(body: RecoveryConfirmation, service: Service) -> Response:
    service.confirm_address(body.token)
    return Response(status_code=204)


@router.post("/recovery/request", status_code=202, responses=errors(400, 503))
def request_recovery(
    body: RecoveryRequest,
    service: Service,
    request: Request,
    background: BackgroundTasks,
) -> MessageResponse:
    delivery = service.request_recovery(body.username)
    background.add_task(deliver, request, delivery)
    return MessageResponse(message="If recovery is available, instructions will be sent")


@router.post("/recovery/reset", status_code=204, responses=errors(400, 503))
def reset_password(body: ResetRequest, service: Service) -> Response:
    service.reset_password(body.token, body.new_password)
    return Response(status_code=204)
