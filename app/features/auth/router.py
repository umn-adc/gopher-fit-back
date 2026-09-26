from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.database import DatabaseSession
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

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/register", status_code=201)
def register(request: RegisterRequest, service: Service) -> AuthResponse:
    return service.register(request)


@router.post("/login")
def login(request: LoginRequest, service: Service) -> AuthResponse:
    return service.login(request)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    responses={401: {"description": "Revoked, expired or reused token"}},
)
def refresh(request: RefreshRequest, service: Service) -> AuthResponse | JSONResponse:
    result = service.refresh(request.refresh_token)
    if result is None:
        return JSONResponse({"error": "Invalid refresh token"}, status_code=401)
    return result


@router.post("/logout", status_code=204)
def logout(claims: CurrentSession, service: Service) -> Response:
    service.logout(claims)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204)
def logout_all(claims: CurrentSession, service: Service) -> Response:
    service.logout(claims, all_sessions=True)
    return Response(status_code=204)


@router.delete("/account", status_code=204)
def delete_account(request: PasswordConfirmation, user: CurrentUser, service: Service) -> Response:
    service.delete_account(user, request.password)
    return Response(status_code=204)


@router.put("/recovery-address", status_code=202)
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


@router.post("/recovery-address/confirm", status_code=204)
def confirm_recovery(body: RecoveryConfirmation, service: Service) -> Response:
    service.confirm_address(body.token)
    return Response(status_code=204)


@router.post("/recovery/request", status_code=202)
def request_recovery(
    body: RecoveryRequest,
    service: Service,
    request: Request,
    background: BackgroundTasks,
) -> MessageResponse:
    delivery = service.request_recovery(body.username)
    background.add_task(deliver, request, delivery)
    return MessageResponse(message="If recovery is available, instructions will be sent")


@router.post("/recovery/reset", status_code=204)
def reset_password(body: ResetRequest, service: Service) -> Response:
    service.reset_password(body.token, body.new_password)
    return Response(status_code=204)
