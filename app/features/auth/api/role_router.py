"""
Role-management API routes.

Admin-only surface for granting/revoking roles on existing users.
Separate from `auth_router.py` (self-service identity) and from
`employee_router.py` (HR-domain employee records) — this operates on
the `User`/`Role`/`UserRole` auth-domain tables directly.

Authorization policy: every route here requires the "admin" role.
Unlike employee management (which HR/managers can also touch), granting
or revoking permissions is deliberately restricted to admins only.

Users are addressed by email (not user_id) here since that's what an
admin realistically has on hand when granting access.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.auth.dependencies.auth_dependencies import (
    current_active_user,
    permission_required,
)
from app.features.auth.models.user import User
from app.features.auth.schemas.role import RoleAssignRequest, UserRolesResponse
from app.features.auth.service.role_service import RoleService
from app.shared.responses.envelope import ResponseEnvelope

router = APIRouter(prefix="/users", tags=["Role Management"])


def _to_roles_response(user: User) -> UserRolesResponse:
    return UserRolesResponse(
        user_id=str(user.id),
        roles=sorted(user_role.role.name for user_role in user.user_roles),
    )


@router.get(
    "/{email}/roles",
    response_model=ResponseEnvelope[UserRolesResponse],
    summary="List the roles currently held by a user",
    dependencies=[Depends(permission_required("admin"))],
)
async def list_user_roles(
    email: str,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UserRolesResponse]:
    service = RoleService(db)
    user = await service.list_user_roles(email)
    return ResponseEnvelope(data=_to_roles_response(user))


@router.post(
    "/{email}/roles",
    response_model=ResponseEnvelope[UserRolesResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Grant a role to a user",
    dependencies=[Depends(permission_required("admin"))],
)
async def assign_role(
    email: str,
    payload: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(current_active_user),
) -> ResponseEnvelope[UserRolesResponse]:
    service = RoleService(db)
    user = await service.assign_role(email, payload.role_name, granted_by=admin.id)
    return ResponseEnvelope(
        data=_to_roles_response(user),
        message=f"Granted role '{payload.role_name}'.",
    )


@router.delete(
    "/{email}/roles/{role_name}",
    response_model=ResponseEnvelope[UserRolesResponse],
    summary="Revoke a role from a user",
    dependencies=[Depends(permission_required("admin"))],
)
async def revoke_role(
    email: str,
    role_name: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(current_active_user),
) -> ResponseEnvelope[UserRolesResponse]:
    service = RoleService(db)
    user = await service.revoke_role(email, role_name, revoked_by=admin.id)
    return ResponseEnvelope(
        data=_to_roles_response(user),
        message=f"Revoked role '{role_name}'.",
    )