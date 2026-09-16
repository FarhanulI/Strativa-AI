import uuid
from datetime import datetime

from sqlalchemy import select
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
