from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.repositories.competitor import CompetitorRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository


class CompetitorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CompetitorRepository(session)
        self.market_repository = MarketIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        name: str,
        description: str | None = None,
        platform: str | None = None,
        profile_url: str | None = None,
        niche: str | None = None,
        relevance_score: float | None = None,
        competitor_metadata: dict[str, Any] | None = None,
    ) -> Competitor:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        competitor = Competitor(
            market_intelligence_id=market_intelligence_id,
            name=name,
            description=description,
            platform=platform,
            profile_url=profile_url,
            niche=niche,
            relevance_score=relevance_score,
            competitor_metadata=competitor_metadata,
        )
        await self.repository.create(competitor)
        await self.session.commit()
        return competitor

    async def get(
        self, market_intelligence_id: UUID, competitor_id: UUID, workspace_id: UUID
    ) -> Competitor | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        competitor = await self.repository.get_by_id(competitor_id)
        if not competitor or competitor.market_intelligence_id != market_intelligence_id:
            return None
        return competitor

    async def list(
        self,
        market_intelligence_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Competitor]:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)
        return await self.repository.list_by_market(market_intelligence_id, skip=skip, limit=limit)

    async def update(
        self,
        market_intelligence_id: UUID,
        competitor_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        description: str | None = None,
        platform: str | None = None,
        profile_url: str | None = None,
        niche: str | None = None,
        relevance_score: float | None = None,
        competitor_metadata: dict[str, Any] | None = None,
    ) -> Competitor | None:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        competitor = await self.repository.get_by_id(competitor_id)
        if not competitor or competitor.market_intelligence_id != market_intelligence_id:
            return None

        if name is not None:
            competitor.name = name
        if description is not None:
            competitor.description = description
        if platform is not None:
            competitor.platform = platform
        if profile_url is not None:
            competitor.profile_url = profile_url
        if niche is not None:
            competitor.niche = niche
        if relevance_score is not None:
            competitor.relevance_score = relevance_score
        if competitor_metadata is not None:
            competitor.competitor_metadata = competitor_metadata

        await self.repository.update(competitor)
        await self.session.commit()
        return competitor

    async def delete(
        self, market_intelligence_id: UUID, competitor_id: UUID, workspace_id: UUID
    ) -> bool:
        await self._verify_workspace_access(market_intelligence_id, workspace_id)

        competitor = await self.repository.get_by_id(competitor_id)
        if not competitor or competitor.market_intelligence_id != market_intelligence_id:
            return False

        success = await self.repository.delete(competitor_id)
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
