import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, refresh_token: RefreshToken) -> RefreshToken:
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, refresh_token: RefreshToken, revoked_at: datetime) -> None:
        refresh_token.revoked_at = revoked_at
        await self.session.flush()

    async def claim_for_rotation(
        self, token_hash: str, revoked_at: datetime
    ) -> RefreshToken | None:
        """Atomically revokes the token row matching token_hash ONLY IF
        it is not already revoked, returning the pre-update row's data
        needed by the caller (user_id, session_id) if the claim
        succeeded, or None if another request already claimed/revoked
        it first (or it doesn't exist). This is the single source of
        truth for "did THIS request win the right to rotate this
        token" -- callers must not separately check revoked_at before
        calling this (see AuthService.refresh's TOCTOU note).
        """
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(RefreshToken),
            execution_options={"populate_existing": True, "synchronize_session": False},
        )
        row = result.scalar_one_or_none()
        await self.session.flush()
        return row

    async def revoke_session(self, session_id: uuid.UUID, revoked_at: datetime) -> None:
        """Revokes every non-revoked refresh token in a session's rotation
        chain -- used both by logout and by reuse-detection on a stale
        token, so a compromised token cannot be used again even if it
        isn't the specific row that was replayed.
        """
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in result.scalars():
            token.revoked_at = revoked_at
        await self.session.flush()


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(reset_token)
        await self.session.flush()
        return reset_token

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()
