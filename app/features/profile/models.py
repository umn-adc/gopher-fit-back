from pydantic import Field
from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.schemas import RequestSchema, Schema
from app.core.validation import Name, Password


class ProfileORM(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("gender IN ('Male', 'Female', 'Other')"),
        CheckConstraint(
            "activity_level IN ('Sedentary', 'Lightly Active', "
            "'Moderately Active', 'Very Active', 'Extra Active')"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None]
    height: Mapped[int | None]
    weight: Mapped[int | None]
    gender: Mapped[str | None] = mapped_column(Text)
    activity_level: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    sports: Mapped[str | None] = mapped_column(Text)


class ProfileRequest(RequestSchema):
    name: Name
    age: int = Field(default=0, ge=0, le=130)
    height: int = Field(default=0, ge=0, le=300)
    weight: int = Field(default=0, ge=0, le=700)
    gender: str = ""
    activity_level: str = ""
    goals: list[str] | None = None
    sports: list[str] | None = None


class ProfileResponse(Schema):
    user_id: int
    name: str
    age: int
    height: int
    weight: int
    gender: str
    activity_level: str
    goals: list[str] | None
    sports: list[str] | None


class PublicProfileResponse(Schema):
    user_id: int
    username: str


class UsernameRequest(RequestSchema):
    username: Name


class PasswordRequest(RequestSchema):
    old_password: Password
    new_password: Password


class UsernameResponse(Schema):
    username: str


class PasswordResponse(Schema):
    message: str = "Password updated successfully"
