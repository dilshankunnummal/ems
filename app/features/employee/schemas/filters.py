from datetime import date
from enum import Enum
from uuid import UUID
 
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
 
from app.features.employee.models.enums import EmploymentStatus, EmploymentType
 
# Re-exported (not redefined) so `EmployeeSortOrder` is importable from this
# module — the employee list endpoint's public sort-direction contract —
# while the single source of truth for "what ASC/DESC means" stays in
# `app.shared.pagination`. Duplicating this enum here would risk the two
# drifting apart (e.g. one gaining a third value the other lacks).
from app.shared.pagination.params import SortOrder as EmployeeSortOrder
 
__all__ = ["EmployeeSortField", "EmployeeSortOrder", "EmployeeFilterParams", "employee_filter_params"]
 
 
class EmployeeSortField(str, Enum):
    """Columns the employee list endpoint permits sorting by.
 
    Values are exact `Employee` model attribute names by design — see
    module docstring.
    """
 
    EMPLOYEE_CODE = "employee_code"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    HIRE_DATE = "hire_date"
    EMPLOYMENT_STATUS = "employment_status"
    JOB_TITLE = "job_title"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
 
 
class EmployeeFilterParams(BaseModel):
    """Domain-specific filters for `GET /employees`.
 
    Combined with (not replacing) `app.shared.pagination.PaginationParams`
    on the route: this model carries *what to filter on*, the shared
    model carries *how to page/search/sort-direction*. `sort_by` here is
    the employee-specific, allow-listed counterpart to the shared
    model's generic free-text `sort_by`.
    """
 
    model_config = ConfigDict(str_strip_whitespace=True)
 
    employment_status: EmploymentStatus | None = Field(
        default=None, description="Filter to a single employment status."
    )
    employment_type: EmploymentType | None = Field(
        default=None, description="Filter to a single employment type."
    )
    department_id: UUID | None = Field(
        default=None, description="Filter to employees in a specific department."
    )
    manager_id: UUID | None = Field(
        default=None, description="Filter to direct reports of a specific manager."
    )
    hire_date_from: date | None = Field(
        default=None, description="Only include employees hired on or after this date."
    )
    hire_date_to: date | None = Field(
        default=None, description="Only include employees hired on or before this date."
    )
    include_deleted: bool = Field(
        default=False,
        description=(
            "Include soft-deleted employees in the results. Defaults to "
            "False — the vast majority of callers only ever want active "
            "records, and this keeps that the safe default."
        ),
    )
    sort_by: EmployeeSortField = Field(
        default=EmployeeSortField.CREATED_AT,
        description="Column to sort results by.",
    )
    sort_order: EmployeeSortOrder = Field(
        default=EmployeeSortOrder.DESC, description="Sort direction."
    )
 
    @model_validator(mode="after")
    def _validate_hire_date_range(self) -> "EmployeeFilterParams":
        if (
            self.hire_date_from is not None
            and self.hire_date_to is not None
            and self.hire_date_from > self.hire_date_to
        ):
            raise ValueError("hire_date_from must not be after hire_date_to.")
        return self
 
 
def employee_filter_params(
    employment_status: EmploymentStatus | None = Query(
        None, description="Filter to a single employment status."
    ),
    employment_type: EmploymentType | None = Query(
        None, description="Filter to a single employment type."
    ),
    department_id: UUID | None = Query(
        None, description="Filter to employees in a specific department."
    ),
    manager_id: UUID | None = Query(
        None, description="Filter to direct reports of a specific manager."
    ),
    hire_date_from: date | None = Query(
        None, description="Only include employees hired on or after this date."
    ),
    hire_date_to: date | None = Query(
        None, description="Only include employees hired on or before this date."
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted employees."),
    sort_by: EmployeeSortField = Query(
        EmployeeSortField.CREATED_AT, description="Column to sort results by."
    ),
    sort_order: EmployeeSortOrder = Query(EmployeeSortOrder.DESC, description="Sort direction."),
) -> EmployeeFilterParams:
    """FastAPI dependency assembling validated employee filters from the
    query string, mirroring the shape of
    `app.shared.pagination.params.pagination_params`. Use alongside it as:
 
        @router.get("/")
        async def list_employees(
            pagination: PaginationParams = Depends(pagination_params),
            filters: EmployeeFilterParams = Depends(employee_filter_params),
        ):
            ...
    """
    return EmployeeFilterParams(
        employment_status=employment_status,
        employment_type=employment_type,
        department_id=department_id,
        manager_id=manager_id,
        hire_date_from=hire_date_from,
        hire_date_to=hire_date_to,
        include_deleted=include_deleted,
        sort_by=sort_by,
        sort_order=sort_order,
    )
 