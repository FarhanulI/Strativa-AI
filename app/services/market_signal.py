from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_signal import MarketSignal
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.repositories.market_signal import MarketSignalRepository
from app.repositories.topic import TopicRepository


class MarketSignalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MarketSignalRepository(session)
        self.market_repository = MarketIntelligenceRepository(session)
        self.topic_repository = TopicRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        title: str,
        description: str | None = None,
        topic_id: UUID | None = None,
        source_type: str | None = None,
        source_url: str | None = None,
        signal_type: str | None = None,
        velocity_score: float | None = None,
        relevance_score: float | None = None,
        engagement_score: float | None = None,
        status: str | None = None,
        detected_at: datetime | None = None,
        expires_at: datetime | None = None,
        signal_metadata: dict[str, Any] | None = None,
    ) -> MarketSignal:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        if topic_id is not None:
            await self._verify_topic_belongs_to_market(topic_id, market_intelligence_id)

        signal = MarketSignal(
            market_intelligence_id=market_intelligence_id,
            topic_id=topic_id,
            title=title,
            description=description,
            source_type=source_type,
            source_url=source_url,
            signal_type=signal_type,
            velocity_score=velocity_score,
            relevance_score=relevance_score,
            engagement_score=engagement_score,
            status=status or "active",
            detected_at=detected_at or datetime.now(UTC),
            expires_at=expires_at,
            signal_metadata=signal_metadata,
        )
        await self.repository.create(signal)
        await self.session.commit()
        return signal

    async def get(
        self, market_intelligence_id: UUID, signal_id: UUID, workspace_id: UUID
    ) -> MarketSignal | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        signal = await self.repository.get_by_id(signal_id)
        if not signal or signal.market_intelligence_id != market_intelligence_id:
            return None
        return signal

    async def list(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        status: str | None = None,
        signal_type: str | None = None,
        topic_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MarketSignal]:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)
        return await self.repository.list_by_market(
            market_intelligence_id,
            status=status,
            signal_type=signal_type,
            topic_id=topic_id,
            skip=skip,
            limit=limit,
        )

    async def update(
        self,
        market_intelligence_id: UUID,
        signal_id: UUID,
        workspace_id: UUID,
        title: str | None = None,
        description: str | None = None,
        topic_id: UUID | None = None,
        source_type: str | None = None,
        source_url: str | None = None,
        signal_type: str | None = None,
        velocity_score: float | None = None,
        relevance_score: float | None = None,
        engagement_score: float | None = None,
        status: str | None = None,
        detected_at: datetime | None = None,
        expires_at: datetime | None = None,
        signal_metadata: dict[str, Any] | None = None,
    ) -> MarketSignal | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        signal = await self.repository.get_by_id(signal_id)
        if not signal or signal.market_intelligence_id != market_intelligence_id:
            return None

        if topic_id is not None:
            await self._verify_topic_belongs_to_market(topic_id, market_intelligence_id)
            signal.topic_id = topic_id
        if title is not None:
            signal.title = title
        if description is not None:
            signal.description = description
        if source_type is not None:
            signal.source_type = source_type
        if source_url is not None:
            signal.source_url = source_url
        if signal_type is not None:
            signal.signal_type = signal_type
        if velocity_score is not None:
            signal.velocity_score = velocity_score
        if relevance_score is not None:
            signal.relevance_score = relevance_score
        if engagement_score is not None:
            signal.engagement_score = engagement_score
        if status is not None:
            signal.status = status
        if detected_at is not None:
            signal.detected_at = detected_at
        if expires_at is not None:
            signal.expires_at = expires_at
        if signal_metadata is not None:
            signal.signal_metadata = signal_metadata

        await self.repository.update(signal)
        await self.session.commit()
        return signal

    async def delete(
        self, market_intelligence_id: UUID, signal_id: UUID, workspace_id: UUID
    ) -> bool:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        signal = await self.repository.get_by_id(signal_id)
        if not signal or signal.market_intelligence_id != market_intelligence_id:
            return False

        success = await self.repository.delete(signal_id)
        if success:
            await self.session.commit()
        return success

    async def _verify_workspace_access(
        self, market_intelligence_id: UUID, workspace_id: UUID
    ) -> None:
        market = await self.market_repository.get_by_id(market_intelligence_id)
        if not market:
            raise ValueError("Market intelligence not found")
        profile = await self.profile_repository.get_by_id(market.content_profile_id, workspace_id)
        if not profile:
            raise ValueError("Workspace access denied")

    async def _verify_topic_belongs_to_market(
        self, topic_id: UUID, market_intelligence_id: UUID
    ) -> None:
        """A signal may only reference a topic from the same MarketIntelligence."""
        topic = await self.topic_repository.get_by_id(topic_id)
        if not topic or topic.market_intelligence_id != market_intelligence_id:
            raise ValueError("Topic does not belong to this market intelligence")
