from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query


@dataclass(frozen=True)
class Page:
    limit: int = 50
    offset: int = 0


DEFAULT_PAGE = Page()


def get_page(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Page:
    return Page(limit, offset)


Pagination = Annotated[Page, Depends(get_page)]
