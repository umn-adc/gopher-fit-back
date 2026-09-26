"""Shared input types; response schemas deliberately remain tolerant of legacy rows."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field


def nonblank(value: str) -> str:
    value.encode("utf-8")  # Reject unpaired JSON surrogates before reaching SQLite.
    if not value.strip():
        raise ValueError("Must not be blank")
    return value


def password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return value


def utc_datetime(value: object) -> datetime:
    if isinstance(value, str):
        if "T" not in value:
            raise ValueError("Use an ISO 8601 timestamp with timezone")
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise ValueError("Timestamp is outside the supported UTC range") from error


def timestamp_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


Name = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(nonblank)]
Password = Annotated[str, Field(min_length=1), AfterValidator(password_bytes)]
NonnegativeInt = Annotated[int, Field(ge=0, le=2**63 - 1)]
NonnegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Timestamp = Annotated[datetime, BeforeValidator(utc_datetime)]
