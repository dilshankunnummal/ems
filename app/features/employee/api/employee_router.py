"""
Employee API routes.

Handlers stay thin: request validation, dependency resolution, and
response-contract shaping only. Every business rule (linked-user checks,
employee-code generation, soft-delete/restore state machine, status
transitions) lives in `EmployeeService`; exceptions it raises
(`EmployeeNotFoundException`, `EmployeeCodeAlreadyExistsException`, etc.)
are translated to the standard error envelope by the global exception
handler registered in `app.main` — handlers never catch them locally.

Authorization policy (documented per-route below):
    - Create / status-transition / delete / restore: Admin or HR only —
      these mutate the employee lifecycle in ways an ordinary manager
      or employee should never be able to trigger directly.
    - General profile update: Admin, HR, or Manager — a manager may
      need to correct a direct report's job title/department/phone
      without full HR-level lifecycle access. (No "manager can only
      edit their own direct reports" scoping yet — that requires
      comparing `employee.manager_id` to the caller's own employee
      profile, which needs a manager-to-employee lookup not yet wired
      up; documented here as a deliberate, narrow gap rather than a
      silent omission.)
    - Read (detail + list): Admin, HR, or Manager — any authenticated
      staff-level role. Self-service ("employee views their own
      profile") is intentionally out of scope for this router; it
      belongs behind `/auth/me`-style routes or a future `/employees/me`
      endpoint, not this admin-facing CRUD surface.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.features.auth.dependencies.auth_dependencies import permission_required
from app.features.employee.dependencies.employee_dependencies import (
    get_employee_service,
)
from app.features.employee.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeDetailResponse,
    EmployeeRestoreRequest,
    EmployeeResponse,
    EmployeeStatusUpdateRequest,
    EmployeeUpdateRequest,
)
from app.features.employee.schemas.employee_list import (
    EmployeeListItemResponse,
    EmployeeListResponse,
)
from app.features.employee.schemas.filters import (
    EmployeeFilterParams,
    employee_filter_params,
)
from app.features.employee.service.employee_service import EmployeeService
from app.shared.pagination.params import PaginationParams, pagination_params
from app.shared.responses.envelope import ResponseEnvelope

router = APIRouter(prefix="/employees", tags=["Employees"])

_ADMIN_HR = ("admin", "hr")
_ADMIN_HR_MANAGER = ("admin", "hr", "manager")


@router.post(
    "",
    response_model=ResponseEnvelope[EmployeeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee profile",
    dependencies=[Depends(permission_required(*_ADMIN_HR))],
)
async def create_employee(
    payload: EmployeeCreateRequest,
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeResponse]:
    employee = await service.create_employee(payload)
    return ResponseEnvelope(
        data=EmployeeResponse.model_validate(employee),
        message="Employee created successfully.",
    )


@router.get(
    "",
    response_model=ResponseEnvelope[EmployeeListResponse],
    summary="List employees with pagination, filtering, and sorting",
    dependencies=[Depends(permission_required(*_ADMIN_HR_MANAGER))],
)
async def list_employees(
    pagination: PaginationParams = Depends(pagination_params),
    filters: EmployeeFilterParams = Depends(employee_filter_params),
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeListResponse]:
    employees, total = await service.list_employees(pagination, filters)
    items = [
        EmployeeListItemResponse.model_validate(employee) for employee in employees
    ]
    return ResponseEnvelope(
        data=EmployeeListResponse.create(items, total, pagination),
    )


@router.get(
    "/{employee_id}",
    response_model=ResponseEnvelope[EmployeeDetailResponse],
    summary="Get a single employee's full profile, including linked user summary",
    dependencies=[Depends(permission_required(*_ADMIN_HR_MANAGER))],
)
async def get_employee(
    employee_id: UUID,
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeDetailResponse]:
    employee, user_summary = await service.get_employee_detail(employee_id)
    detail = EmployeeDetailResponse.model_validate(employee)
    detail.user = user_summary
    return ResponseEnvelope(data=detail)


@router.patch(
    "/{employee_id}",
    response_model=ResponseEnvelope[EmployeeResponse],
    summary="Update an employee's profile (partial update)",
    dependencies=[Depends(permission_required(*_ADMIN_HR_MANAGER))],
)
async def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdateRequest,
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeResponse]:
    employee = await service.update_employee(employee_id, payload)
    return ResponseEnvelope(
        data=EmployeeResponse.model_validate(employee),
        message="Employee updated successfully.",
    )


@router.patch(
    "/{employee_id}/status",
    response_model=ResponseEnvelope[EmployeeResponse],
    summary="Transition an employee's employment status",
    dependencies=[Depends(permission_required(*_ADMIN_HR))],
)
async def update_employee_status(
    employee_id: UUID,
    payload: EmployeeStatusUpdateRequest,
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeResponse]:
    employee = await service.update_employee_status(employee_id, payload)
    return ResponseEnvelope(
        data=EmployeeResponse.model_validate(employee),
        message="Employee status updated successfully.",
    )


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an employee profile",
    dependencies=[Depends(permission_required("admin"))],
)
async def delete_employee(
    employee_id: UUID,
    service: EmployeeService = Depends(get_employee_service),
) -> None:
    await service.soft_delete_employee(employee_id)


@router.post(
    "/{employee_id}/restore",
    response_model=ResponseEnvelope[EmployeeResponse],
    summary="Restore a previously soft-deleted employee profile",
    dependencies=[Depends(permission_required("admin"))],
)
async def restore_employee(
    employee_id: UUID,
    payload: EmployeeRestoreRequest,
    service: EmployeeService = Depends(get_employee_service),
) -> ResponseEnvelope[EmployeeResponse]:
    employee = await service.restore_employee(employee_id, payload)
    return ResponseEnvelope(
        data=EmployeeResponse.model_validate(employee),
        message="Employee restored successfully.",
    )
