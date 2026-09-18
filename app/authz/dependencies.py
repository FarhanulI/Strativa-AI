"""Ownership-chain authorization dependencies (Day 21).

Retrofits the "mismatch at any level returns 404" rule from
docs/product/product-architecture.md ("Identity, Tenancy, and
Authorization") onto every router that accepts a client-supplied
`workspace_id`/`profile_id`. `workspace_id`/`profile_id` are still read
from the request (query or path, wherever the route already declares
them) -- what changes is that they are no longer trusted at face value.
`require_workspace_access` verifies the authenticated caller (from Day
20's `get_current_user`) actually has a `WorkspaceMember` row for the
requested workspace; `require_profile_access` composes on top of it to
verify a requested profile belongs to that same workspace. Both return
404 (never 403) on any mismatch, so cross-tenant resource existence is
never leaked.

Not scoped to solve multi-workspace-per-user switching -- a real
membership row is always queried by (user_id, workspace_id), so adding
that later needs no rework here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.core.database import get_db_session
from app.models.content_profile import ContentProfile
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember

_WORKSPACE_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
)
_PROFILE_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Content profile not found"
)


async def require_workspace_access(
    workspace_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceMember:
    """Verify the authenticated caller is a member of `workspace_id`.

    A genuine, indexed `(user_id, workspace_id)` lookup -- not a
    hardcoded single-workspace shortcut -- so multi-workspace-per-user
    support can be added later without a second retrofit. Returns 404
    (never 403) whether `workspace_id` doesn't exist at all or exists but
    the caller isn't a member, so cross-tenant workspace existence is
    never leaked.
    """
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == UUID(current_user.id),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise _WORKSPACE_NOT_FOUND
    return member


async def get_current_workspace(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Workspace:
    """Resolve the authenticated caller's workspace from their
    `WorkspaceMember` row -- no `workspace_id` is ever accepted from the
    client (Day 22: onboarding never lets the client specify which
    workspace it means, unlike `require_workspace_access`).

    MVP: one User maps to exactly one Workspace (see
    docs/development/day-20.md), so the first membership match is the
    caller's workspace. A genuine, indexed lookup by `user_id` -- not a
    shortcut -- matching Day 21's own pattern.
    """
    result = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.user_id == UUID(current_user.id))
    )
    member = result.scalars().first()
    if member is None:
        raise _WORKSPACE_NOT_FOUND

    workspace = await session.get(Workspace, member.workspace_id)
    if workspace is None:
        raise _WORKSPACE_NOT_FOUND
    return workspace


async def require_profile_access(
    profile_id: UUID,
    workspace_member: Annotated[WorkspaceMember, Depends(require_workspace_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentProfile:
    """Verify `profile_id` belongs to a workspace the caller is a member of.

    Composes `require_workspace_access` rather than re-checking membership
    itself. Returns 404 whether the profile doesn't exist or belongs to a
    different workspace.
    """
    profile = await session.get(ContentProfile, profile_id)
    if profile is None or profile.workspace_id != workspace_member.workspace_id:
        raise _PROFILE_NOT_FOUND
    return profile
