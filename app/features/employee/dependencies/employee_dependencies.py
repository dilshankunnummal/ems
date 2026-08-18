from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.employee.service.employee_service import EmployeeService


def get_employee_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    """FastAPI dependency that provides a request-scoped `EmployeeService`.

    Usage:
        @router.get("/employees/{employee_id}")
        async def get_employee(
            employee_id: UUID,
            service: EmployeeService = Depends(get_employee_service),
        ):
            ...
    """
    return EmployeeService(db)
