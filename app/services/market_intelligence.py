from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_intelligence import MarketIntelligence
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository


class MarketIntelligenceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MarketIntelligenceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        summary: str | None = None,
        market_context: str | None = None,
    ) -> MarketIntelligence:
        """
        Create MarketIntelligence for a ContentProfile.

        MarketIntelligence is intelligence input only. It does not directly
        generate ContentOpportunity — that will be produced by the future
        Strategy/Opportunity engine.
        """
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")

        existing = await self.repository.get_by_profile(profile_id)
        if existing:
            raise ValueError("Market intelligence already exists for this content profile.")

        market_intelligence = MarketIntelligence(
            content_profile_id=profile_id,
            summary=summary,
            market_context=market_context,
        )
        await self.repository.create(market_intelligence)
        await self.session.commit()
        return market_intelligence

    async def get(self, profile_id: UUID, workspace_id: UUID) -> MarketIntelligence | None:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None
        return await self.repository.get_by_profile(profile_id)

    async def update(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        summary: str | None = None,
        market_context: str | None = None,
    ) -> MarketIntelligence | None:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return None

        market_intelligence = await self.repository.get_by_profile(profile_id)
        if not market_intelligence:
            return None

        if summary is not None:
            market_intelligence.summary = summary
        if market_context is not None:
            market_intelligence.market_context = market_context

        await self.repository.update(market_intelligence)
        await self.session.commit()
        return market_intelligence

    async def delete(self, profile_id: UUID, workspace_id: UUID) -> bool:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            return False

        market_intelligence = await self.repository.get_by_profile(profile_id)
        if not market_intelligence:
            return False

        success = await self.repository.delete(market_intelligence.id)
        if success:
            await self.session.commit()
        return success
