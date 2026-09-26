from pydantic import EmailStr, Field
from sqlalchemy import ForeignKey, Index, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema
from app.core.validation import Name, Password
from app.features.profile.models import ProfileRequest


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True, nullable=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password: Mapped[bytes] = mapped_column(LargeBinary)


class AuthSessionORM(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("auth_sessions_user", "user_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[int]
    revoked_at: Mapped[int | None]


class RefreshTokenORM(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("refresh_tokens_session", "session_id"),)

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id", ondelete="CASCADE"))
    used_at: Mapped[int | None]


class RecoveryAddressORM(Base):
    __tablename__ = "recovery_addresses"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str | None] = mapped_column(Text)
    pending_email: Mapped[str | None] = mapped_column(Text)


class RecoveryTokenORM(Base):
    __tablename__ = "recovery_tokens"
    __table_args__ = (Index("recovery_tokens_user_purpose", "user_id", "purpose"),)

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int]
    used_at: Mapped[int | None]


class LoginRequest(RequestSchema):
    username: Name
    password: Password


class RegisterRequest(ProfileRequest):
    username: Name
    password: Password


class AuthResponse(Schema):
    token: str
    user_id: int
    username: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class RefreshRequest(RequestSchema):
    refresh_token: str = Field(min_length=20, max_length=200)


class PasswordConfirmation(RequestSchema):
    password: Password


class RecoveryAddressRequest(PasswordConfirmation):
    email: EmailStr


class RecoveryRequest(RequestSchema):
    username: Name


class RecoveryConfirmation(RequestSchema):
    token: str = Field(min_length=20, max_length=200)


class ResetRequest(RecoveryConfirmation):
    new_password: Password


class MessageResponse(Schema):
    message: str
