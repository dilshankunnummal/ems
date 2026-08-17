"""
Employee service — orchestrates the create/read/list/update, status-
transition, soft-delete, and restore flows on top of `EmployeeRepository`
and (for the linked-user checks and detail-view assembly) auth's
`UserRepository`.

Route handlers stay thin (see `api/employee_router.py`, added in a later
pass); every rule about *how* an employee profile is created, updated, or
retired — linked-user existence, one-profile-per-user, employee-code
generation vs. collision checking, soft-delete/restore state machine —
lives here. The repository layer stays pure data access with zero
business rules, exactly mirroring how `AuthService` sits on top of
`UserRepository` / `RoleRepository` / `RefreshTokenRepository`.
"""
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.repository.user_repository import UserRepository
from app.features.employee.exceptions.employee_exceptions import (
    EmployeeCodeAlreadyExistsException,
    EmployeeNotFoundException,
    EmployeeNotSoftDeletedException,
    LinkedUserNotFoundException,
    UserAlreadyHasEmployeeProfileException,
)
from app.features.employee.models.employee import Employee
from app.features.employee.repository.employee_repository import EmployeeRepository
from app.features.employee.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeRestoreRequest,
    EmployeeStatusUpdateRequest,
    EmployeeUpdateRequest,
    EmployeeUserSummary,
)
from app.features.employee.schemas.filters import EmployeeFilterParams
from app.shared.pagination.params import PaginationParams

logger = structlog.get_logger(__name__)


class EmployeeService:
    """Coordinates `EmployeeRepository`, `UserRepository`, and the
    employee schemas/exceptions to implement every employee use case.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.employees = EmployeeRepository(db)
        self.users = UserRepository(db)

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #

    async def create_employee(self, payload: EmployeeCreateRequest) -> Employee:
        """Create a new employee profile linked to an existing `User`.

        Validates, in order: the linked user actually exists, the user
        doesn't already have an employee profile, and — when the caller
        supplied an explicit `employee_code` — that code isn't already
        taken. When no `employee_code` was supplied, one is generated
        via `EmployeeRepository.generate_next_employee_code`.

        These pre-checks give a clean, typed error before any insert is
        attempted; `EmployeeRepository.create` still guards against a
        concurrent duplicate via the database's unique constraints, in
        which case a generic `ConflictException` surfaces instead — an
        acceptable, rare race-condition fallback.
        """
        user = await self.users.get_by_id(payload.user_id)
        if user is None:
            logger.warning("employee_create_rejected_unknown_user", user_id=str(payload.user_id))
            raise LinkedUserNotFoundException()

        if await self.employees.exists_by_user_id(payload.user_id):
            logger.warning(
                "employee_create_rejected_duplicate_user", user_id=str(payload.user_id)
            )
            raise UserAlreadyHasEmployeeProfileException()

        if payload.employee_code is not None:
            if await self.employees.exists_by_employee_code(payload.employee_code):
                logger.warning(
                    "employee_create_rejected_duplicate_code",
                    employee_code=payload.employee_code,
                )
                raise EmployeeCodeAlreadyExistsException(payload.employee_code)
            employee_code = payload.employee_code
        else:
            employee_code = await self.employees.generate_next_employee_code()

        employee = await self.employees.create(
            user_id=payload.user_id,
            employee_code=employee_code,
            first_name=payload.first_name,
            last_name=payload.last_name,
            hire_date=payload.hire_date,
            phone=payload.phone,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            address=payload.address,
            employment_status=payload.employment_status,
            employment_type=payload.employment_type,
            job_title=payload.job_title,
            department_id=payload.department_id,
            manager_id=payload.manager_id,
        )

        logger.info(
            "employee_created",
            employee_id=str(employee.id),
            employee_code=employee.employee_code,
            user_id=str(employee.user_id),
        )
        return employee

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    async def get_employee(self, employee_id: uuid.UUID) -> Employee:
        """Fetch a single active employee by id, or raise
        `EmployeeNotFoundException`.
        """
        employee = await self.employees.get_by_id(employee_id)
        if employee is None:
            logger.warning("employee_not_found", employee_id=str(employee_id))
            raise EmployeeNotFoundException()
        return employee

    async def get_employee_detail(
        self, employee_id: uuid.UUID
    ) -> tuple[Employee, EmployeeUserSummary | None]:
        """Fetch an employee together with a summary of its linked
        `User` account, for `GET /employees/{id}` (the detail view).

        Returns `(employee, None)` rather than raising if the linked
        user has somehow gone missing (should not happen given the
        `ON DELETE CASCADE` on `employees.user_id`, but the read path
        stays defensive rather than turning a data anomaly into a 500).
        """
        employee = await self.get_employee(employee_id)
        user = await self.users.get_by_id(employee.user_id)
        user_summary = EmployeeUserSummary.model_validate(user) if user is not None else None
        return employee, user_summary

    async def list_employees(
        self, pagination: PaginationParams, filters: EmployeeFilterParams
    ) -> tuple[list[Employee], int]:
        """Return `(page_of_employees, total_matching_count)` for
        `GET /employees`. A thin pass-through to the repository — no
        business rules apply to listing, only to individual writes.
        """
        return await self.employees.list_paginated(pagination, filters)

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    async def update_employee(
        self, employee_id: uuid.UUID, payload: EmployeeUpdateRequest
    ) -> Employee:
        """Apply a partial profile update to an existing employee.

        `payload.model_dump(exclude_unset=True)` ensures only fields
        the caller actually supplied are touched — a field explicitly
        set to `None` (e.g. clearing `manager_id`) is applied, while an
        omitted field is left untouched, matching standard PATCH
        semantics. `user_id`, `employee_code`, and `employment_status`
        are structurally absent from `EmployeeUpdateRequest`, so there
        is nothing here that could accidentally rewrite them.
        """
        employee = await self.get_employee(employee_id)
        update_data = payload.model_dump(exclude_unset=True)

        employee = await self.employees.update(employee, update_data)
        logger.info("employee_updated", employee_id=str(employee.id))
        return employee

    async def update_employee_status(
        self, employee_id: uuid.UUID, payload: EmployeeStatusUpdateRequest
    ) -> Employee:
        """Transition an employee's employment status.

        `payload.reason` and `payload.effective_date` are accepted for
        audit-trail purposes at the API layer (and future persistence
        into an audit log — see the `audit` feature) but are not
        additional columns on `Employee` itself; only `employment_status`
        is written here. No transition-legality matrix is enforced yet
        (e.g. `TERMINATED` -> `ACTIVE` is currently permitted) — that
        policy decision is deferred rather than hard-coded prematurely.
        """
        employee = await self.get_employee(employee_id)
        employee = await self.employees.update_status(employee, payload.employment_status)
        logger.info(
            "employee_status_transitioned",
            employee_id=str(employee.id),
            new_status=payload.employment_status.value,
            reason=payload.reason,
        )
        return employee

    # ------------------------------------------------------------------ #
    # Soft delete / restore
    # ------------------------------------------------------------------ #

    async def soft_delete_employee(self, employee_id: uuid.UUID) -> None:
        """Soft-delete an employee profile.

        Looks the employee up via the non-deleted-only getter, so
        calling this twice on the same id cleanly raises
        `EmployeeNotFoundException` the second time rather than
        silently re-deleting an already-deleted row.
        """
        employee = await self.get_employee(employee_id)
        await self.employees.soft_delete(employee)
        logger.info("employee_soft_deleted", employee_id=str(employee_id))

    async def restore_employee(
        self, employee_id: uuid.UUID, payload: EmployeeRestoreRequest
    ) -> Employee:
        """Reverse a soft delete.

        Uses `get_by_id_including_deleted` (the whole point is to find
        a currently soft-deleted row, which the default `get_by_id`
        would never return) and rejects the call outright if the
        employee isn't actually soft-deleted, so `restore` can never be
        used as a no-op way to "touch" an active employee.
        """
        employee = await self.employees.get_by_id_including_deleted(employee_id)
        if employee is None:
            logger.warning("employee_not_found", employee_id=str(employee_id))
            raise EmployeeNotFoundException()

        if not employee.is_deleted:
            logger.warning(
                "employee_restore_rejected_not_deleted", employee_id=str(employee_id)
            )
            raise EmployeeNotSoftDeletedException()

        employee = await self.employees.restore(employee)
        logger.info(
            "employee_restored",
            employee_id=str(employee.id),
            reason=payload.reason,
        )
        return employee