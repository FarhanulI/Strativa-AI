from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.repositories.topic import TopicRepository


class TopicService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TopicRepository(session)
        self.market_repository = MarketIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        relevance_score: float | None = None,
    ) -> Topic:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        existing = await self.repository.get_by_name(market_intelligence_id, name)
        if existing:
            raise ValueError("A topic with this name already exists for this market intelligence.")

        topic = Topic(
            market_intelligence_id=market_intelligence_id,
            name=name,
            description=description,
            relevance_score=relevance_score,
        )
        await self.repository.create(topic)
        await self.session.commit()
        return topic

    async def get(
        self, market_intelligence_id: UUID, topic_id: UUID, workspace_id: UUID
    ) -> Topic | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        topic = await self.repository.get_by_id(topic_id)
        if not topic or topic.market_intelligence_id != market_intelligence_id:
            return None
        return topic

    async def list(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Topic]:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)
        return await self.repository.list_by_market(market_intelligence_id, skip=skip, limit=limit)

    async def update(
        self,
        market_intelligence_id: UUID,
        topic_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
        relevance_score: float | None = None,
    ) -> Topic | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        topic = await self.repository.get_by_id(topic_id)
        if not topic or topic.market_intelligence_id != market_intelligence_id:
            return None

        if name is not None and name != topic.name:
            existing = await self.repository.get_by_name(market_intelligence_id, name)
            if existing and existing.id != topic.id:
                raise ValueError(
                    "A topic with this name already exists for this market intelligence."
                )
            topic.name = name
        if description is not None:
            topic.description = description
        if relevance_score is not None:
            topic.relevance_score = relevance_score

        await self.repository.update(topic)
        await self.session.commit()
        return topic

    async def delete(
        self, market_intelligence_id: UUID, topic_id: UUID, workspace_id: UUID
    ) -> bool:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        topic = await self.repository.get_by_id(topic_id)
        if not topic or topic.market_intelligence_id != market_intelligence_id:
            return False

        success = await self.repository.delete(topic_id)
        if success:
            await self.session.commit()
        return success

    async def _verify_workspace_access(
        self, market_intelligence_id: UUID, workspace_id: UUID
    ) -> None:
        """Ensure the MarketIntelligence exists and its ContentProfile is in the workspace."""
        market = await self.market_repository.get_by_id(market_intelligence_id)
        if not market:
            raise ValueError("Market intelligence not found")
        profile = await self.profile_repository.get_by_id(market.content_profile_id, workspace_id)
        if not profile:
            raise ValueError("Workspace access denied")
