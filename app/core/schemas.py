from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RequestSchema(Schema):
    """Strict input scalars with a common integer bound and error envelope."""

    model_config = ConfigDict(strict=True, extra="ignore", allow_inf_nan=False)

    @field_validator("*")
    @classmethod
    def integer_range(cls, value: Any) -> Any:
        if type(value) is int and not -(2**63) <= value < 2**63:
            raise ValueError("Integer out of range")
        return value
