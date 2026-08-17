"""
Employee-specific exception types.

Thin wrappers over the shared exception hierarchy so every employee
failure mode gets a stable, descriptive `error_code` without each call
site repeating the same message/status boilerplate — mirrors
`app.features.auth.exceptions.auth_exceptions`.
"""
from app.shared.exceptions import BadRequestException, ConflictException, NotFoundException


class EmployeeNotFoundException(NotFoundException):
    """Raised when an employee_id does not resolve to an active
    (non-soft-deleted) employee row.
    """

    def __init__(self, message: str = "Employee not found.") -> None:
        super().__init__(message, error_code="EMPLOYEE_NOT_FOUND")


class EmployeeCodeAlreadyExistsException(ConflictException):
    """Raised when a caller-supplied `employee_code` is already in use.

    Distinct from the repository's generic `EMPLOYEE_ALREADY_EXISTS`
    conflict (which only fires on a genuine race at insert time) — this
    is the clean, pre-insert rejection for a code the service already
    knows is taken.
    """

    def __init__(self, employee_code: str) -> None:
        super().__init__(
            f"An employee with code '{employee_code}' already exists.",
            error_code="EMPLOYEE_CODE_ALREADY_EXISTS",
        )


class UserAlreadyHasEmployeeProfileException(ConflictException):
    """Raised when `EmployeeCreateRequest.user_id` already has an
    employee profile (active or soft-deleted) — the schema enforces at
    most one `Employee` row per `User` row.
    """

    def __init__(self) -> None:
        super().__init__(
            "This user already has an employee profile.",
            error_code="USER_ALREADY_HAS_EMPLOYEE_PROFILE",
        )


class LinkedUserNotFoundException(BadRequestException):
    """Raised when `EmployeeCreateRequest.user_id` does not resolve to
    any existing auth `User` account.

    A `BadRequestException` (not `NotFoundException`): the failure is
    with the caller's input, not with a resource the caller is trying
    to look up directly.
    """

    def __init__(self) -> None:
        super().__init__(
            "The specified user_id does not correspond to an existing user account.",
            error_code="LINKED_USER_NOT_FOUND",
        )


class EmployeeNotSoftDeletedException(BadRequestException):
    """Raised when `restore_employee` is called on an employee that is
    not currently soft-deleted — restoring an already-active employee
    is not a meaningful operation.
    """

    def __init__(self) -> None:
        super().__init__(
            "This employee is not currently deleted, so it cannot be restored.",
            error_code="EMPLOYEE_NOT_SOFT_DELETED",
        )