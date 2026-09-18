import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.auth.models import User
from app.models.workspace import Workspace, WorkspaceOnboardingStatus
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


async def test_register_creates_user_workspace_and_owner_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new.user@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    claims = decode_access_token(body["access_token"])

    users = (
        (await db_session.execute(select(User).where(User.email == "new.user@example.com")))
        .scalars()
        .all()
    )
    assert len(users) == 1
    user = users[0]
    assert claims.sub == str(user.id)

    members = (
        (
            await db_session.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(members) == 1
    assert members[0].role == WorkspaceRole.OWNER

    workspace = await db_session.get(Workspace, members[0].workspace_id)
    assert workspace is not None
    assert workspace.onboarding_status == WorkspaceOnboardingStatus.NOT_STARTED


async def test_register_duplicate_email_rejected_without_duplicate_records(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@example.com", "password": "correct-horse-battery"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@example.com", "password": "another-password-456"},
    )
    assert second.status_code == 409

    users = (
        (await db_session.execute(select(User).where(User.email == "dupe@example.com")))
        .scalars()
        .all()
    )
    assert len(users) == 1

    workspaces = (await db_session.execute(select(Workspace))).scalars().all()
    assert len(workspaces) == 1


async def test_register_duplicate_email_case_insensitive(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "Mixed.Case@example.com", "password": "correct-horse-battery"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "mixed.case@example.com", "password": "another-password-456"},
    )
    assert second.status_code == 409


async def test_register_rate_limited_after_threshold(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.infrastructure.ratelimit.middleware.settings.rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_register_rate_limit_requests_per_window",
        2,
    )
    monkeypatch.setattr(
        "app.infrastructure.ratelimit.middleware.settings.auth_register_rate_limit_window_seconds",
        60,
    )

    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate1@example.com", "password": "correct-horse-battery"},
    )
    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate2@example.com", "password": "correct-horse-battery"},
    )
    third = await client.post(
        "/api/v1/auth/register",
        json={"email": "rate3@example.com", "password": "correct-horse-battery"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429


async def test_register_then_onboarding_status_is_not_started(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "onboarding.status@example.com", "password": "correct-horse-battery"},
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    status_response = await client.get("/api/v1/onboarding")

    assert status_response.status_code == 200
    assert status_response.json()["onboarding_status"] == "not_started"
