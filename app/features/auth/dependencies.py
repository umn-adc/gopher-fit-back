import time
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPBearer

from app.core.database import DatabaseSession
from app.core.errors import AuthenticationFailed
from app.features.auth.repository import AuthRepository
from app.features.auth.security import AccessClaims, TokenService

bearer = HTTPBearer(auto_error=False)


def get_tokens(request: Request) -> TokenService:
    tokens: TokenService = request.app.state.tokens
    return tokens


def current_session(
    request: Request,
    session: DatabaseSession,
    tokens: Annotated[TokenService, Depends(get_tokens)],
    _: Annotated[object, Depends(bearer)],
) -> AccessClaims:
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationFailed("Requires Bearer JWT token")
    claims = tokens.verify(parts[1])
    repository = AuthRepository(session)
    stored = repository.auth_session(claims.session_id)
    if (
        stored is None
        or stored.user_id != claims.user_id
        or stored.revoked_at is not None
        or stored.expires_at <= int(time.time())
        or repository.user(claims.user_id) is None
    ):
        raise AuthenticationFailed("Session expired or revoked")
    return claims


CurrentSession = Annotated[AccessClaims, Depends(current_session)]


def current_user_id(claims: CurrentSession) -> int:
    return claims.user_id


CurrentUser = Annotated[int, Depends(current_user_id)]
