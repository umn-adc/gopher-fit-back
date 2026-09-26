from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.features.auth.models import (
    AuthSessionORM,
    RecoveryAddressORM,
    RecoveryTokenORM,
    RefreshTokenORM,
    UserORM,
)


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def by_username(self, username: str) -> UserORM | None:
        return self.session.scalar(select(UserORM).where(UserORM.username == username))

    def create(self, username: str, password: bytes) -> UserORM:
        user = UserORM(username=username, password=password)
        self.session.add(user)
        try:
            self.session.flush()
        except IntegrityError as error:
            if "UNIQUE constraint failed" in str(error.orig):
                raise Conflict("Username already exists") from error
            raise
        return user

    def user(self, user_id: int) -> UserORM | None:
        return self.session.get(UserORM, user_id)

    def add_session(self, user_id: int, session_id: str, expires_at: int, digest: str) -> None:
        self.session.add(AuthSessionORM(id=session_id, user_id=user_id, expires_at=expires_at))
        self.session.flush()
        self.add_refresh(session_id, digest)

    def auth_session(self, session_id: str) -> AuthSessionORM | None:
        return self.session.get(AuthSessionORM, session_id)

    def refresh(self, digest: str) -> RefreshTokenORM | None:
        return self.session.get(RefreshTokenORM, digest)

    def add_refresh(self, session_id: str, digest: str) -> None:
        self.session.add(RefreshTokenORM(token_hash=digest, session_id=session_id))
        self.session.flush()

    def consume_refresh(self, token: RefreshTokenORM, now: int) -> None:
        token.used_at = now
        self.session.flush()

    def revoke_session(self, session: AuthSessionORM, now: int) -> None:
        session.revoked_at = now
        self.session.flush()

    def revoke_all(self, user_id: int, now: int) -> None:
        self.session.execute(
            update(AuthSessionORM).where(AuthSessionORM.user_id == user_id).values(revoked_at=now)
        )

    def address(self, user_id: int) -> RecoveryAddressORM | None:
        return self.session.get(RecoveryAddressORM, user_id)

    def stage_address(self, user_id: int, email: str) -> None:
        address = self.address(user_id)
        if address is None:
            address = RecoveryAddressORM(user_id=user_id)
            self.session.add(address)
        address.pending_email = email
        self.session.flush()

    def confirm_address(self, address: RecoveryAddressORM) -> None:
        address.email = address.pending_email
        address.pending_email = None
        self.session.flush()

    def recovery(self, digest: str) -> RecoveryTokenORM | None:
        return self.session.get(RecoveryTokenORM, digest)

    def invalidate_recovery(self, user_id: int, now: int, purpose: str | None = None) -> None:
        query = update(RecoveryTokenORM).where(RecoveryTokenORM.user_id == user_id)
        if purpose:
            query = query.where(RecoveryTokenORM.purpose == purpose)
        self.session.execute(query.values(used_at=now))

    def add_recovery(self, user_id: int, purpose: str, digest: str, expires_at: int) -> None:
        self.session.add(
            RecoveryTokenORM(
                user_id=user_id, purpose=purpose, token_hash=digest, expires_at=expires_at
            )
        )
        self.session.flush()

    def change_password(self, user: UserORM, password: bytes, now: int) -> None:
        user.password = password
        self.revoke_all(user.id, now)
        self.invalidate_recovery(user.id, now)
        address = self.address(user.id)
        if address:
            address.pending_email = None
        self.session.flush()

    def delete_user(self, user: UserORM) -> None:
        # Existing and new foreign keys cascade all owned rows within this transaction.
        self.session.delete(user)
        self.session.flush()
