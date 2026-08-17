"""
Shared pagination/sorting/filtering query-parameter contract.

Every feature's "list" endpoint depends on `PaginationParams` via
`Depends()` instead of redefining `page`/`page_size`/`sort_by` on each
router — one implementation, one set of validation rules, one place to
change the defaults.
"""
from enum import Enum

from fastapi import Query
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = settings.DEFAULT_PAGE_SIZE
    sort_by: str | None = None
    sort_order: SortOrder = SortOrder.DESC
    search: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description=f"Items per page (max {settings.MAX_PAGE_SIZE})",
    ),
    sort_by: str | None = Query(None, description="Column name to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="asc or desc"),
    search: str | None = Query(None, min_length=1, max_length=200, description="Free-text search"),
) -> PaginationParams:
    """FastAPI dependency that assembles validated pagination parameters
    from the query string. Use as:

        @router.get("/")
        async def list_items(params: PaginationParams = Depends(pagination_params)):
            ...
    """
    return PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )
