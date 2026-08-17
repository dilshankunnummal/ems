from typing import Sequence, Union
 
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
 
from alembic import op
 
# revision identifiers, used by Alembic.
revision: str = "b55aee9a2382"
down_revision: Union[str, None] = "18cc390a0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
# --- Native PostgreSQL ENUM type definitions -------------------------------
# Defined once here and reused (with create_type=False) on the column
# itself, so each type is created exactly once via explicit .create()
# calls below rather than implicitly and inconsistently by create_table.
gender_enum = postgresql.ENUM(
    "male",
    "female",
    "other",
    "prefer_not_to_say",
    name="gender_enum",
    create_type=False,
)
employment_status_enum = postgresql.ENUM(
    "active",
    "on_leave",
    "suspended",
    "terminated",
    name="employment_status_enum",
    create_type=False,
)
employment_type_enum = postgresql.ENUM(
    "full_time",
    "part_time",
    "contract",
    "intern",
    name="employment_type_enum",
    create_type=False,
)
 
 
def upgrade() -> None:
    bind = op.get_bind()
 
    # Create the native ENUM types before any table references them.
    gender_enum.create(bind, checkfirst=True)
    employment_status_enum.create(bind, checkfirst=True)
    employment_type_enum.create(bind, checkfirst=True)
 
    op.create_table(
        "employees",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("employee_code", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", gender_enum, nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column(
            "employment_status",
            employment_status_enum,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "employment_type",
            employment_type_enum,
            server_default=sa.text("'full_time'"),
            nullable=False,
        ),
        sa.Column("job_title", sa.String(length=150), nullable=True),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("manager_id", sa.UUID(), nullable=True),
        sa.Column("profile_image_path", sa.String(length=500), nullable=True),
        sa.Column("resume_path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "date_of_birth IS NULL OR date_of_birth < hire_date",
            name=op.f("ck_employees_date_of_birth_before_hire_date"),
        ),
        sa.CheckConstraint(
            "length(employee_code) >= 3",
            name=op.f("ck_employees_employee_code_min_length"),
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["employees.id"],
            name=op.f("fk_employees_manager_id_employees"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_employees_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
        sa.UniqueConstraint("employee_code", name=op.f("uq_employees_employee_code")),
        sa.UniqueConstraint("user_id", name=op.f("uq_employees_user_id")),
    )
 
    # --- Indexes ------------------------------------------------------------
    op.create_index(
        op.f("ix_employees_employee_code"), "employees", ["employee_code"], unique=True
    )
    op.create_index(op.f("ix_employees_user_id"), "employees", ["user_id"], unique=True)
    op.create_index(
        op.f("ix_employees_employment_status"), "employees", ["employment_status"], unique=False
    )
    op.create_index(
        op.f("ix_employees_department_id"), "employees", ["department_id"], unique=False
    )
    op.create_index(op.f("ix_employees_manager_id"), "employees", ["manager_id"], unique=False)
    op.create_index(
        "ix_employees_employment_status_department_id",
        "employees",
        ["employment_status", "department_id"],
        unique=False,
    )
    op.create_index(
        "ix_employees_last_name_first_name",
        "employees",
        ["last_name", "first_name"],
        unique=False,
    )
 
 
def downgrade() -> None:
    bind = op.get_bind()
 
    op.drop_index("ix_employees_last_name_first_name", table_name="employees")
    op.drop_index("ix_employees_employment_status_department_id", table_name="employees")
    op.drop_index(op.f("ix_employees_manager_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_department_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_employment_status"), table_name="employees")
    op.drop_index(op.f("ix_employees_user_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_employee_code"), table_name="employees")
 
    op.drop_table("employees")
 
    employment_type_enum.drop(bind, checkfirst=True)
    employment_status_enum.drop(bind, checkfirst=True)
    gender_enum.drop(bind, checkfirst=True)
 