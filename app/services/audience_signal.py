from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audience_signal import AudienceSignal
from app.repositories.audience_signal import AudienceSignalRepository
from app.repositories.content_profile import ContentProfileRepository


class AudienceSignalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AudienceSignalRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(self, profile_id: UUID, workspace_id: UUID, **values: Any) -> AudienceSignal:
        await self._verify_profile(profile_id, workspace_id)
        signal = AudienceSignal(
            profile_id=profile_id,
            signal_type=values.get("signal_type", "question"),
            question=values["question"],
            topic=values.get("topic"),
            description=values.get("description"),
            intent=values["intent"],
            strength_score=values.get("strength_score", 0.5),
            status=values.get("status", "active"),
            source=values.get("source", "manual"),
            signal_metadata=values.get("signal_metadata"),
            observed_at=values.get("observed_at") or datetime.now(UTC),
            expires_at=values.get("expires_at"),
        )
        await self.repository.create(signal)
        await self.session.commit()
        return signal

    async def get(
        self, profile_id: UUID, signal_id: UUID, workspace_id: UUID
    ) -> AudienceSignal | None:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.get_by_id(profile_id, signal_id)

    async def list(
        self, profile_id: UUID, workspace_id: UUID, **filters: Any
    ) -> list[AudienceSignal]:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(profile_id, **filters)

    async def update(
        self, profile_id: UUID, signal_id: UUID, workspace_id: UUID, **values: Any
    ) -> AudienceSignal | None:
        await self._verify_profile(profile_id, workspace_id)
        signal = await self.repository.get_by_id(profile_id, signal_id)
        if not signal:
            return None
        for field in (
            "signal_type",
            "question",
            "topic",
            "description",
            "intent",
            "strength_score",
            "status",
            "source",
            "signal_metadata",
            "observed_at",
            "expires_at",
        ):
            if field in values:
                setattr(signal, field, values[field])
        await self.repository.update(signal)
        await self.session.commit()
        return signal

    async def delete(self, profile_id: UUID, signal_id: UUID, workspace_id: UUID) -> bool:
        await self._verify_profile(profile_id, workspace_id)
        signal = await self.repository.get_by_id(profile_id, signal_id)
        if not signal:
            return False
        await self.repository.delete(signal)
        await self.session.commit()
        return True

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID) -> None:
        if not await self.profile_repository.get_by_id(profile_id, workspace_id):
            raise ValueError("Content profile not found")
