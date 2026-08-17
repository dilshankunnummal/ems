"""
Alembic environment script — wired to the project's async engine and
declarative Base so `alembic revision --autogenerate` picks up every
model registered across every feature package.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import get_settings
from app.core.database.base import Base
from app.features.auth.models import user

# --- Import every feature's models so Base.metadata is fully populated. ---
# As each feature is built, its models module is added here.
# from app.features.auth.models import user  # noqa: F401
# from app.features.employee.models import employee  # noqa: F401
# from app.features.department.models import department  # noqa: F401
# from app.features.attendance.models import attendance  # noqa: F401
# from app.features.leave.models import leave  # noqa: F401
# from app.features.documents.models import document  # noqa: F401
# from app.features.audit.models import audit_log  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
