import uuid
from datetime import date
 
from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
 
from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.features.employee.models.enums import EmploymentStatus, EmploymentType, Gender
 
 
class Employee(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """The HR profile record for a single employee.
 
    Exactly one `Employee` row exists per `User` row (enforced by the
    unique constraint on `user_id`). Deletion is always soft (see
    `SoftDeleteMixin`) — repositories must filter `is_deleted == False`
    on every default read and expose an explicit restore path rather
    than ever issuing a hard DELETE against this table.
    """
 
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_employees_user_id"),
        UniqueConstraint("employee_code", name="uq_employees_employee_code"),
        # Note: constraint names below are passed as the *convention
        # token* only (not pre-prefixed) — the naming_convention on
        # `Base.metadata` (see app/core/database/base.py) automatically
        # expands each to `ck_employees_<name>`. Pre-prefixing here would
        # double the prefix (e.g. `ck_employees_ck_employees_...`).
        CheckConstraint(
            "date_of_birth IS NULL OR date_of_birth < hire_date",
            name="date_of_birth_before_hire_date",
        ),
        CheckConstraint(
            "length(employee_code) >= 3",
            name="employee_code_min_length",
        ),
        # Composite index backing the common dashboard/report query shape:
        # "how many active employees per department".
        Index(
            "ix_employees_employment_status_department_id",
            "employment_status",
            "department_id",
        ),
        # Composite index backing name-based sorting and search, the
        # default sort order for the employee list endpoint.
        Index("ix_employees_last_name_first_name", "last_name", "first_name"),
    )
 
    # --- Identity / linkage -------------------------------------------------
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    employee_code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
 
    # --- Personal details -----------------------------------------------------
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="gender_enum", native_enum=True, validate_strings=True),
        nullable=True,
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
 
    # --- Employment details --------------------------------------------------
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(
            EmploymentStatus,
            name="employment_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=EmploymentStatus.ACTIVE,
        server_default=EmploymentStatus.ACTIVE.value,
        index=True,
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(
            EmploymentType,
            name="employment_type_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=EmploymentType.FULL_TIME,
        server_default=EmploymentType.FULL_TIME.value,
    )
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
 
    # --- Organizational relationships ----------------------------------------
    # No FK constraint yet — see module docstring "Deferred foreign key".
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
 
    # --- Uploaded assets -------------------------------------------------------
    profile_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
 
    # --- Relationships -----------------------------------------------------
    manager: Mapped["Employee | None"] = relationship(
        "Employee",
        remote_side="Employee.id",
        back_populates="direct_reports",
        foreign_keys=[manager_id],
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        "Employee",
        back_populates="manager",
        foreign_keys=[manager_id],
    )