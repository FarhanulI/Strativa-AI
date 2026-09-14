from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_intelligence_synthesis import ContentIntelligenceSynthesis


class ContentIntelligenceSynthesisRepository:
    """Persistence for the single `content_intelligence_synthesis` table.

    Mirrors `app.repositories.intelligence_analysis.IntelligenceAnalysisRepository`'s
    shape (current-row lookup, clear-current, create) plus `mark_stale`, the
    write side of the staleness flag components flip on regeneration.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current(self, profile_id: UUID) -> ContentIntelligenceSynthesis | None:
        stmt = select(ContentIntelligenceSynthesis).where(
            ContentIntelligenceSynthesis.profile_id == profile_id,
            ContentIntelligenceSynthesis.is_current.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_current(self, profile_id: UUID) -> None:
        stmt = (
            update(ContentIntelligenceSynthesis)
            .where(
                ContentIntelligenceSynthesis.profile_id == profile_id,
                ContentIntelligenceSynthesis.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await self.session.execute(stmt)

    async def mark_stale(self, profile_id: UUID) -> None:
        stmt = (
            update(ContentIntelligenceSynthesis)
            .where(
                ContentIntelligenceSynthesis.profile_id == profile_id,
                ContentIntelligenceSynthesis.is_current.is_(True),
            )
            .values(is_stale=True)
        )
        await self.session.execute(stmt)

    async def create(self, synthesis: ContentIntelligenceSynthesis) -> ContentIntelligenceSynthesis:
        self.session.add(synthesis)
        await self.session.flush()
        return synthesis
