import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.employee.models.employee import Employee
from app.features.employee.models.enums import EmploymentStatus, EmploymentType, Gender
from app.features.employee.schemas.filters import EmployeeFilterParams
from app.shared.exceptions import ConflictException
from app.shared.pagination.params import PaginationParams, SortOrder

logger = structlog.get_logger(__name__)

_DEFAULT_CODE_PREFIX = "EMP-"
_DEFAULT_CODE_PADDING = 5
_CODE_SUFFIX_PATTERN = re.compile(r"^(\d+)$")


class EmployeeRepository:
    """Async repository providing basic persistence operations for `Employee`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None:
        """Fetch a non-deleted employee by primary key, or None if it
        doesn't exist (or exists but is soft-deleted).
        """
        result = await self.db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_including_deleted(
        self, employee_id: uuid.UUID
    ) -> Employee | None:
        """Fetch an employee by primary key regardless of soft-delete
        state. Used by the restore flow, where the whole point is to
        locate a currently soft-deleted row.
        """
        result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self, user_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Employee | None:
        """Fetch the employee profile linked to a given auth User.

        `include_deleted=False` (the default) matches the common case
        of "does this user currently have an active employee profile".
        """
        conditions = [Employee.user_id == user_id]
        if not include_deleted:
            conditions.append(Employee.is_deleted.is_(False))
        result = await self.db.execute(select(Employee).where(*conditions))
        return result.scalar_one_or_none()

    async def get_by_employee_code(
        self, employee_code: str, *, include_deleted: bool = False
    ) -> Employee | None:
        """Fetch an employee by their business-facing employee code."""
        conditions = [Employee.employee_code == employee_code]
        if not include_deleted:
            conditions.append(Employee.is_deleted.is_(False))
        result = await self.db.execute(select(Employee).where(*conditions))
        return result.scalar_one_or_none()

    async def exists_by_employee_code(self, employee_code: str) -> bool:
        """True if `employee_code` is already in use by any row —
        deleted or not.

        Deliberately ignores `is_deleted`: the `uq_employees_employee_code`
        database constraint applies to every row regardless of
        soft-delete state, so a code "freed up" by a soft delete is not
        actually free. Checking the full table here is what keeps this
        pre-check consistent with what the database will actually
        enforce, so callers get a clean `ConflictException` from the
        service layer instead of a raw `IntegrityError` surfacing on
        insert.
        """
        result = await self.db.execute(
            select(Employee.id).where(Employee.employee_code == employee_code).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_user_id(self, user_id: uuid.UUID) -> bool:
        """True if `user_id` already has an employee profile — deleted
        or not. See `exists_by_employee_code` for why soft-delete state
        is ignored here.
        """
        result = await self.db.execute(
            select(Employee.id).where(Employee.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------ #
    # List / count
    # ------------------------------------------------------------------ #

    def _build_conditions(
        self, filters: EmployeeFilterParams, search: str | None = None
    ) -> list[Any]:
        """Translate `EmployeeFilterParams` (plus an optional free-text
        search term) into a list of SQLAlchemy WHERE conditions, ANDed
        together by every caller via `.where(*conditions)`.

        Centralized so `list_paginated` and `count` can never drift —
        "how many employees match X" and "give me page 2 of employees
        matching X" must always agree on what X means.
        """
        conditions: list[Any] = []

        if not filters.include_deleted:
            conditions.append(Employee.is_deleted.is_(False))
        if filters.employment_status is not None:
            conditions.append(Employee.employment_status == filters.employment_status)
        if filters.employment_type is not None:
            conditions.append(Employee.employment_type == filters.employment_type)
        if filters.department_id is not None:
            conditions.append(Employee.department_id == filters.department_id)
        if filters.manager_id is not None:
            conditions.append(Employee.manager_id == filters.manager_id)
        if filters.hire_date_from is not None:
            conditions.append(Employee.hire_date >= filters.hire_date_from)
        if filters.hire_date_to is not None:
            conditions.append(Employee.hire_date <= filters.hire_date_to)

        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Employee.employee_code.ilike(pattern),
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                )
            )

        return conditions

    async def list_paginated(
        self, pagination: PaginationParams, filters: EmployeeFilterParams
    ) -> tuple[list[Employee], int]:
        """Return `(page_of_employees, total_matching_count)`.

        Paging (`page`/`page_size`) and the free-text `search` term come
        from the shared `PaginationParams`; every other filter and the
        sort field/direction come from the employee-specific
        `EmployeeFilterParams` — see that module's docstring for why the
        two are kept separate rather than merged into one contract.

        `filters.sort_by` is an `EmployeeSortField` enum whose values are
        exact `Employee` attribute names, so the sort column is resolved
        with a plain `getattr` rather than a second lookup table — and
        because it's an enum (not a client-supplied string), it can
        never resolve to a column the API didn't intend to expose for
        sorting.
        """
        conditions = self._build_conditions(filters, search=pagination.search)

        total = (
            await self.db.execute(select(func.count(Employee.id)).where(*conditions))
        ).scalar_one()

        sort_column = getattr(Employee, filters.sort_by.value)
        order_expression = (
            sort_column.asc()
            if filters.sort_order == SortOrder.ASC
            else sort_column.desc()
        )

        stmt = (
            select(Employee)
            .where(*conditions)
            .order_by(order_expression)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.db.execute(stmt)
        employees = list(result.scalars().all())

        return employees, total

    async def count(
        self, filters: EmployeeFilterParams | None = None, search: str | None = None
    ) -> int:
        """Count employees matching `filters`/`search` without paging.

        `filters=None` counts every non-deleted employee (the default
        `EmployeeFilterParams()` excludes soft-deleted rows) — the
        common case for a dashboard "total active employees" figure.
        """
        effective_filters = filters if filters is not None else EmployeeFilterParams()
        conditions = self._build_conditions(effective_filters, search=search)
        result = await self.db.execute(
            select(func.count(Employee.id)).where(*conditions)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        employee_code: str,
        first_name: str,
        last_name: str,
        hire_date: date,
        phone: str | None = None,
        date_of_birth: date | None = None,
        gender: Gender | None = None,
        address: str | None = None,
        employment_status: EmploymentStatus = EmploymentStatus.ACTIVE,
        employment_type: EmploymentType = EmploymentType.FULL_TIME,
        job_title: str | None = None,
        department_id: uuid.UUID | None = None,
        manager_id: uuid.UUID | None = None,
        profile_image_path: str | None = None,
        resume_path: str | None = None,
    ) -> Employee:
        """Persist a new employee row.

        Expects an already-validated, already-normalized `employee_code`
        (uppercased, format-checked) — that validation is the caller's
        (schema/service layer's) responsibility, not the repository's.
        """
        employee = Employee(
            user_id=user_id,
            employee_code=employee_code,
            first_name=first_name,
            last_name=last_name,
            hire_date=hire_date,
            phone=phone,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            employment_status=employment_status,
            employment_type=employment_type,
            job_title=job_title,
            department_id=department_id,
            manager_id=manager_id,
            profile_image_path=profile_image_path,
            resume_path=resume_path,
        )
        self.db.add(employee)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            logger.warning(
                "employee_create_conflict",
                employee_code=employee_code,
                user_id=str(user_id),
            )
            raise ConflictException(
                "An employee with this employee code or user already exists.",
                error_code="EMPLOYEE_ALREADY_EXISTS",
            ) from exc
        await self.db.refresh(employee)
        return employee

    async def update(self, employee: Employee, update_data: dict[str, Any]) -> Employee:
        """Apply a partial set of column updates to an already-loaded
        `Employee` instance and flush.

        `update_data` is expected to already be filtered to only the
        fields the caller actually wants to change (e.g. via a Pydantic
        schema's `.model_dump(exclude_unset=True)`) — this method does
        not interpret "unset vs. None" itself, it simply applies
        whatever mapping it is given.
        """
        for field_name, value in update_data.items():
            setattr(employee, field_name, value)

        try:
            await self.db.flush()
        except IntegrityError as exc:
            logger.warning("employee_update_conflict", employee_id=str(employee.id))
            raise ConflictException(
                "This update would conflict with an existing employee record.",
                error_code="EMPLOYEE_UPDATE_CONFLICT",
            ) from exc
        await self.db.refresh(employee)
        return employee

    async def soft_delete(self, employee: Employee) -> Employee:
        """Mark an employee as soft-deleted rather than issuing a hard
        DELETE, per `SoftDeleteMixin`'s contract.
        """
        employee.is_deleted = True
        employee.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(employee)
        logger.info("employee_soft_deleted", employee_id=str(employee.id))
        return employee

    async def restore(self, employee: Employee) -> Employee:
        """Reverse a soft delete, clearing `deleted_at`."""
        employee.is_deleted = False
        employee.deleted_at = None
        await self.db.flush()
        await self.db.refresh(employee)
        logger.info("employee_restored", employee_id=str(employee.id))
        return employee

    async def update_status(
        self, employee: Employee, new_status: EmploymentStatus
    ) -> Employee:
        """Persist an employment-status change.

        Only writes the column — legality of the transition (e.g.
        whether `TERMINATED` -> `ACTIVE` is allowed at all, or requires
        going through `restore` instead) is a service-layer rule, not
        enforced here.
        """
        employee.employment_status = new_status
        await self.db.flush()
        await self.db.refresh(employee)
        logger.info(
            "employee_status_updated",
            employee_id=str(employee.id),
            new_status=new_status.value,
        )
        return employee

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def generate_next_employee_code(
        self,
        *,
        prefix: str = _DEFAULT_CODE_PREFIX,
        padding: int = _DEFAULT_CODE_PADDING,
    ) -> str:
        """Compute the next sequential employee code for `prefix`, e.g.
        `EMP-00001` -> `EMP-00002`.

        Scans every row matching `prefix` — including soft-deleted ones,
        since the underlying `employee_code` uniqueness constraint is
        not relaxed by soft delete (see `exists_by_employee_code`) — and
        takes the numeric max of the suffix rather than trusting
        lexicographic `ORDER BY ... DESC LIMIT 1`, which only sorts
        correctly if every existing code happens to share the same
        zero-padding width. That assumption is fine for codes this
        method generated itself, but not safe against manually entered
        or migrated legacy codes of a different width.

        A high-volume production system would typically replace this
        with a dedicated PostgreSQL sequence (`nextval()`) to avoid the
        full table scan and the (small, flush-boundary-limited) race
        window between read and insert; this implementation is the
        straightforward, dependency-free starting point for that later
        optimization.
        """
        result = await self.db.execute(
            select(Employee.employee_code).where(
                Employee.employee_code.like(f"{prefix}%")
            )
        )
        existing_codes = result.scalars().all()

        max_suffix = 0
        for code in existing_codes:
            suffix = code[len(prefix) :]
            if _CODE_SUFFIX_PATTERN.match(suffix):
                max_suffix = max(max_suffix, int(suffix))

        next_number = max_suffix + 1
        return f"{prefix}{next_number:0{padding}d}"
