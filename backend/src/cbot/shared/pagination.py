from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

PageParam = Annotated[int, Query(ge=1)]
LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


class Page[T](BaseModel):
    """Envelope de paginação: `{ data, total, page, limit }` (PEP 695 genérico)."""

    data: list[T]
    total: int
    page: int
    limit: int
