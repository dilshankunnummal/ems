"""
Generic paginated response envelope, layered on top of the pagination
query params so every list endpoint returns the same shape:

    {
      "items": [...],
      "total": 137,
      "page": 1,
      "page_size": 20,
      "total_pages": 7,
      "has_next": true,
      "has_previous": false
    }
"""

import math
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel

from app.shared.pagination.params import PaginationParams

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        total: int,
        params: PaginationParams,
    ) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / params.page_size) if params.page_size else 0
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_previous=params.page > 1,
        )
