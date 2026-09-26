import time

from app.core.config import Settings
from app.core.errors import AuthenticationFailed, InvalidInput, Unavailable
from app.features.auth.delivery import Delivery
from app.features.auth.models import (
    AuthResponse,
    LoginRequest,
    RecoveryTokenORM,
    RegisterRequest,
    UserORM,
)
from app.features.auth.repository import AuthRepository
from app.features.auth.security import (
    AccessClaims,
    TokenService,
    hash_password,
    new_token,
    token_hash,
    valid_password,
    verify_password,
)
from app.features.profile.service import ProfileService

# Use a real hash for missing accounts so login does not have a cheap username timing oracle.
DUMMY_HASH = b"$2b$10$mZKVeAzYXLLmJKQlQcfsIefUuCtFMXuQVgaUlPmMbW8xLDJKRM7Xi"


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        profiles: ProfileService,
        tokens: TokenService,
        settings: Settings,
    ):
        self.repository = repository
        self.profiles = profiles
        self.tokens = tokens
        self.settings = settings

    def _response(self, user: UserORM, session_id: str, refresh: str) -> AuthResponse:
        return AuthResponse(
            token=self.tokens.create(user.id, user.username, session_id),
            user_id=user.id,
            username=user.username,
            refresh_token=refresh,
            expires_in=self.tokens.ttl_seconds,
        )

    def _login(self, user: UserORM) -> AuthResponse:
        refresh, session_id = new_token(), new_token()
        self.repository.add_session(
            user.id,
            session_id,
            int(time.time()) + self.settings.refresh_ttl_seconds,
            token_hash(refresh),
        )
        return self._response(user, session_id, refresh)

    def register(self, request: RegisterRequest) -> AuthResponse:
        if not valid_password(request.password):
            raise InvalidInput("Invalid credentials")
        user = self.repository.create(request.username, hash_password(request.password))
        self.profiles.create(user.id, request)
        return self._login(user)

    def login(self, request: LoginRequest) -> AuthResponse:
        user = self.repository.by_username(request.username)
        valid = verify_password(request.password, user.password if user else DUMMY_HASH)
        if user is None or not valid:
            raise AuthenticationFailed("Invalid credentials")
        return self._login(user)

    def refresh(self, raw_token: str) -> AuthResponse | None:
        now = int(time.time())
        token = self.repository.refresh(token_hash(raw_token))
        if token is None:
            return None
        session = self.repository.auth_session(token.session_id)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        if token.used_at is not None:
            self.repository.revoke_session(session, now)
            # Return a failure value, not an exception: the revocation MUST commit on HTTP 401.
            return None
        user = self.repository.user(session.user_id)
        if user is None:
            return None
        refresh = new_token()
        self.repository.consume_refresh(token, now)
        self.repository.add_refresh(session.id, token_hash(refresh))
        return self._response(user, session.id, refresh)

    def logout(self, claims: AccessClaims, all_sessions: bool = False) -> None:
        if all_sessions:
            self.repository.revoke_all(claims.user_id, int(time.time()))
        elif session := self.repository.auth_session(claims.session_id):
            self.repository.revoke_session(session, int(time.time()))

    def _confirmed_user(self, user_id: int, password: str) -> UserORM:
        user = self.repository.user(user_id)
        if user is None or not verify_password(password, user.password):
            raise AuthenticationFailed("Invalid credentials")
        return user

    def delete_account(self, user_id: int, password: str) -> None:
        self.repository.delete_user(self._confirmed_user(user_id, password))

    def _recovery_enabled(self) -> None:
        if not self.settings.recovery_enabled:
            raise Unavailable("Account recovery is not configured")

    def _issue_recovery(self, user_id: int, email: str, purpose: str) -> Delivery:
        now, token = int(time.time()), new_token()
        self.repository.invalidate_recovery(user_id, now, purpose)
        self.repository.add_recovery(
            user_id, purpose, token_hash(token), now + self.settings.recovery_ttl_seconds
        )
        return Delivery(email, token, purpose)

    def enroll(self, user_id: int, password: str, email: str) -> Delivery:
        self._recovery_enabled()
        self._confirmed_user(user_id, password)
        self.repository.stage_address(user_id, email)
        return self._issue_recovery(user_id, email, "verify")

    def request_recovery(self, username: str) -> Delivery | None:
        self._recovery_enabled()
        user = self.repository.by_username(username)
        address = self.repository.address(user.id) if user else None
        if user is None or address is None or not address.email:
            return None
        return self._issue_recovery(user.id, address.email, "reset")

    def _valid_recovery(self, raw_token: str, purpose: str) -> RecoveryTokenORM:
        self._recovery_enabled()
        token = self.repository.recovery(token_hash(raw_token))
        if (
            token is None
            or token.purpose != purpose
            or token.used_at is not None
            or token.expires_at <= int(time.time())
        ):
            raise InvalidInput("Invalid or expired recovery token")
        return token

    def confirm_address(self, raw_token: str) -> None:
        token = self._valid_recovery(raw_token, "verify")
        address = self.repository.address(token.user_id)
        if address is None or not address.pending_email:
            raise InvalidInput("Invalid or expired recovery token")
        self.repository.confirm_address(address)
        self.repository.invalidate_recovery(token.user_id, int(time.time()))

    def reset_password(self, raw_token: str, password: str) -> None:
        if not valid_password(password):
            raise InvalidInput("New password is invalid")
        token = self._valid_recovery(raw_token, "reset")
        user = self.repository.user(token.user_id)
        if user is None:
            raise InvalidInput("Invalid or expired recovery token")
        self.repository.change_password(user, hash_password(password), int(time.time()))
