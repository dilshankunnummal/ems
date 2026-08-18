from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from app.features.employee.models.enums import EmploymentStatus, EmploymentType
from app.shared.pagination.response import PaginatedResponse

__all__ = ["EmployeeListItemResponse", "EmployeeListResponse"]


class EmployeeListItemResponse(BaseModel):
    """A single row in the employee list/table view."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    "employee_code": "EMP-00001",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "job_title": "Senior Backend Engineer",
                    "employment_status": "active",
                    "employment_type": "full_time",
                    "department_id": None,
                    "hire_date": "2024-06-01",
                    "profile_image_path": None,
                }
            ]
        },
    )

    id: UUID
    employee_code: str
    first_name: str
    last_name: str
    job_title: str | None
    employment_status: EmploymentStatus
    employment_type: EmploymentType
    department_id: UUID | None
    hire_date: date
    profile_image_path: str | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class EmployeeListResponse(PaginatedResponse[EmployeeListItemResponse]):
    """Named, concrete paginated-response type for `GET /employees`.

    Subclassing `PaginatedResponse[EmployeeListItemResponse]` (rather
    than using the generic alias inline on the route) gives this shape
    its own name in the generated OpenAPI schema — `EmployeeListResponse`
    instead of an auto-generated `PaginatedResponse_EmployeeListItemResponse_`
    — while still reusing 100% of the shared pagination-envelope logic
    (`total`, `page`, `total_pages`, `has_next`, `has_previous`, and the
    `.create()` constructor) rather than redefining it.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                            "employee_code": "EMP-00001",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "job_title": "Senior Backend Engineer",
                            "employment_status": "active",
                            "employment_type": "full_time",
                            "department_id": None,
                            "hire_date": "2024-06-01",
                            "profile_image_path": None,
                        }
                    ],
                    "total": 137,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 7,
                    "has_next": True,
                    "has_previous": False,
                }
            ]
        }
    )
