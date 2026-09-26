import re
from typing import Annotated

from fastapi import Path
from pydantic import BeforeValidator


def parse_path_integer(value: str) -> int:
    if not re.fullmatch(r"[+-]?[0-9]+", value):
        raise ValueError("Invalid integer")
    return int(value)


ResourceID = Annotated[int, BeforeValidator(parse_path_integer), Path(ge=-(2**63), le=2**63 - 1)]
PositiveResourceID = Annotated[int, BeforeValidator(parse_path_integer), Path(gt=0, le=2**63 - 1)]
