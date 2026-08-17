"""
One-off bootstrap script: grant a role (default: admin) to a user by email.

Needed because there is currently no API endpoint that assigns admin/hr —
`AuthService.register()` only ever grants the default "employee" role.
Run this once to create your first admin, then build a proper
admin-only "assign role" endpoint for everything after that.

Usage (from the project root, with your venv activated):
    python scripts/promote_user.py user@example.com admin
    python scripts/promote_user.py user@example.com hr
"""
import asyncio
import sys
from pathlib import Path

# When run as `python scripts/promote_user.py`, Python only adds the
# script's own folder (scripts/) to sys.path — not the project root
# where the `app` package lives. Add it explicitly so the import below
# resolves no matter which directory this is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.features.auth.models.user import Role, User, UserRole


async def promote(email: str, role_name: str) -> None:
    async with AsyncSessionLocal() as db:
        # 1. Find the user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with email: {email}")
            return

        # 2. Find or create the role
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=f"{role_name.title()} access.")
            db.add(role)
            await db.flush()
            print(f"Created new role: {role_name}")

        # 3. Skip if already granted
        result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.role_id == role.id
            )
        )
        if result.scalar_one_or_none() is not None:
            print(f"{email} already has role '{role_name}'.")
            return

        # 4. Grant it
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
        print(f"Granted role '{role_name}' to {email}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/promote_user.py <email> [role_name=admin]")
        sys.exit(1)

    target_email = sys.argv[1]
    target_role = sys.argv[2] if len(sys.argv) > 2 else "admin"
    asyncio.run(promote(target_email, target_role))
