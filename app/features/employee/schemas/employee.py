import re
from datetime import date, datetime
from uuid import UUID
 
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)
 
from app.features.employee.models.enums import EmploymentStatus, EmploymentType, Gender
from app.shared.validators.common import validate_phone_number
 
__all__ = [
    "EmployeeUserSummary",
    "EmployeeCreateRequest",
    "EmployeeUpdateRequest",
    "EmployeeResponse",
    "EmployeeDetailResponse",
    "EmployeeStatusUpdateRequest",
    "EmployeeRestoreRequest",
]
 
# Employee codes are a business identifier, not a database implementation
# detail — kept human-typeable: uppercase letters, digits, and hyphens.
# Mirrors (and stays intentionally in sync with) the database-level
# `ck_employees_employee_code_min_length` CHECK constraint, so a bad
# value is rejected by the API with a clear message instead of surfacing
# as an opaque 500 from a constraint violation.
_EMPLOYEE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,18}[A-Z0-9]$")
 
# Mirrors the database-level `ck_employees_date_of_birth_before_hire_date`
# CHECK constraint for the same reason: fail fast with a field-level
# error instead of a database round trip that ends in a 500.
_MIN_WORKING_AGE_YEARS = 15
 
 
def _normalize_employee_code(value: str) -> str:
    """Uppercase and validate an employee code. Shared by every schema
    that accepts one, so the format rule is defined exactly once.
    """
    normalized = value.strip().upper()
    if not _EMPLOYEE_CODE_PATTERN.match(normalized):
        raise ValueError(
            "employee_code must be 3-20 characters, using only uppercase "
            "letters, digits, and hyphens (not at the start or end), "
            "e.g. 'EMP-00001'."
        )
    return normalized
 
 
def _years_between(earlier: date, later: date) -> int:
    """Whole years elapsed between two dates, accounting for whether the
    later date's month/day has passed the earlier date's anniversary.
    """
    years = later.year - earlier.year
    if (later.month, later.day) < (earlier.month, earlier.day):
        years -= 1
    return years
 
 
def _validate_dob_hire_relationship(date_of_birth: date | None, hire_date: date | None) -> None:
    """Cross-field validation shared by create and update: a
    `date_of_birth` must precede `hire_date`, and the employee must have
    been at least `_MIN_WORKING_AGE_YEARS` old on their hire date.
 
    A no-op if either side of the comparison is absent (e.g. a partial
    update that only touches one of the two fields) — full-record
    consistency in that case is enforced by the database CHECK
    constraint at write time using the *persisted* values for whichever
    field wasn't part of this particular request.
    """
    if date_of_birth is None or hire_date is None:
        return
    if date_of_birth >= hire_date:
        raise ValueError("date_of_birth must be earlier than hire_date.")
    if _years_between(date_of_birth, hire_date) < _MIN_WORKING_AGE_YEARS:
        raise ValueError(
            f"Employee must be at least {_MIN_WORKING_AGE_YEARS} years old as of hire_date."
        )
 
 
class EmployeeUserSummary(BaseModel):
    """Minimal, read-only view of the linked `User` account.
 
    Deliberately defined locally rather than imported from
    `app.features.auth.schemas.user`: the `Employee` model has no ORM
    relationship back to `User` (see `employee.py`'s module docstring —
    keeping `auth` fully unaware of `employee` is a hard architectural
    requirement), so this object is never populated by `from_attributes`
    off the `Employee` row itself. The service layer assembles it
    separately (one extra lookup via `UserRepository`) and attaches it
    when building an `EmployeeDetailResponse`.
    """
 
    model_config = ConfigDict(from_attributes=True)
 
    id: UUID
    email: EmailStr
    is_active: bool
    is_verified: bool
 
 
class EmployeeCreateRequest(BaseModel):
    """Payload for `POST /employees`.
 
    `employee_code` is optional — when omitted, the service layer
    generates the next sequential code. When supplied (e.g. migrating
    historical employee IDs from a legacy system), it is validated and
    normalized here.
    """
 
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "b3f1c2a4-5e6d-4f7a-8b9c-0d1e2f3a4b5c",
                    "employee_code": "EMP-00001",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "phone": "+14155552671",
                    "date_of_birth": "1994-03-12",
                    "gender": "female",
                    "address": "123 Market St, San Francisco, CA",
                    "hire_date": "2024-06-01",
                    "employment_status": "active",
                    "employment_type": "full_time",
                    "job_title": "Senior Backend Engineer",
                    "department_id": None,
                    "manager_id": None,
                }
            ]
        },
    )
 
    user_id: UUID = Field(description="The auth User account this employee profile belongs to.")
    employee_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=20,
        description="Business-facing employee identifier. Auto-generated if omitted.",
    )
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = Field(default=None, max_length=255)
    hire_date: date
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    job_title: str | None = Field(default=None, max_length=150)
    department_id: UUID | None = Field(
        default=None,
        description=(
            "Department this employee belongs to. Not yet database-enforced "
            "as a foreign key pending the Department feature — validated "
            "for existence at the service layer once that feature ships."
        ),
    )
    manager_id: UUID | None = None
 
    @field_validator("employee_code")
    @classmethod
    def _validate_employee_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_employee_code(value)
 
    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_phone_number(value)
 
    @model_validator(mode="after")
    def _validate_dates(self) -> "EmployeeCreateRequest":
        _validate_dob_hire_relationship(self.date_of_birth, self.hire_date)
        return self
 
 
class EmployeeUpdateRequest(BaseModel):
    """Payload for `PATCH /employees/{id}`.
 
    Every field is optional — only supplied fields are changed (partial
    update semantics). `user_id` and `employee_code` are deliberately
    excluded: they are identity-defining fields that should never be
    silently rewritten by a generic profile update. `employment_status`
    is also excluded — status transitions go through the dedicated
    `EmployeeStatusUpdateRequest` flow instead of this general-purpose
    one, so that a status change (which may need reason/effective-date
    tracking) can never be smuggled in as a side effect of an unrelated
    profile edit.
    """
 
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "phone": "+14155552671",
                    "address": "456 Mission St, San Francisco, CA",
                    "job_title": "Staff Backend Engineer",
                    "department_id": "d4e5f6a7-8b9c-0d1e-2f3a-4b5c6d7e8f9a",
                    "manager_id": None,
                }
            ]
        },
    )
 
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = Field(default=None, max_length=255)
    hire_date: date | None = None
    employment_type: EmploymentType | None = None
    job_title: str | None = Field(default=None, max_length=150)
    department_id: UUID | None = None
    manager_id: UUID | None = None
 
    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_phone_number(value)
 
    @model_validator(mode="after")
    def _validate_dates(self) -> "EmployeeUpdateRequest":
        _validate_dob_hire_relationship(self.date_of_birth, self.hire_date)
        return self
 
    @model_validator(mode="after")
    def _validate_at_least_one_field(self) -> "EmployeeUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied for an update.")
        return self
 
 
class EmployeeStatusUpdateRequest(BaseModel):
    """Payload for the dedicated employment-status transition endpoint
    (e.g. `PATCH /employees/{id}/status`).
 
    Kept separate from `EmployeeUpdateRequest` so that status changes —
    which typically need an audit trail (reason, effective date) and
    tighter authorization than a general profile edit — have their own
    explicit, narrow contract.
    """
 
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "employment_status": "on_leave",
                    "reason": "Approved medical leave.",
                    "effective_date": "2026-09-01",
                }
            ]
        },
    )
 
    employment_status: EmploymentStatus = Field(description="The new employment status.")
    reason: str | None = Field(
        default=None, max_length=500, description="Optional reason recorded for audit purposes."
    )
    effective_date: date | None = Field(
        default=None,
        description="Date the status change takes effect. Defaults to today if omitted.",
    )
 
 
class EmployeeRestoreRequest(BaseModel):
    """Payload for `POST /employees/{id}/restore`, undoing a soft delete."""
 
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [{"reason": "Reinstated after HR review of termination appeal."}]
        },
    )
 
    reason: str | None = Field(
        default=None, max_length=500, description="Optional reason recorded for audit purposes."
    )
 
 
class EmployeeResponse(BaseModel):
    """Full, public-facing representation of an `Employee` row."""
 
    model_config = ConfigDict(from_attributes=True)
 
    id: UUID
    user_id: UUID
    employee_code: str
    first_name: str
    last_name: str
    phone: str | None
    date_of_birth: date | None
    gender: Gender | None
    address: str | None
    hire_date: date
    employment_status: EmploymentStatus
    employment_type: EmploymentType
    job_title: str | None
    department_id: UUID | None
    manager_id: UUID | None
    profile_image_path: str | None
    resume_path: str | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
 
    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
 
 
class EmployeeDetailResponse(EmployeeResponse):
    """`EmployeeResponse` plus the linked user account summary.
 
    `user` is populated by the service layer (not automatically via
    `from_attributes`) — see `EmployeeUserSummary`'s docstring for why.
    """
 
    user: EmployeeUserSummary | None = Field(
        default=None,
        description="Summary of the linked auth User account, when available.",
    )
 