from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class IntelligenceAnalysisRepository:
    """Persistence for a single analysis table (BrandAnalysis/AudienceAnalysis/
    MarketAnalysis). Parameterized by model class rather than triplicated,
    per the day-16 "shared module" guidance — ownership/authorization stays
    in the service layer, this only queries/writes the given table.
    """

    def __init__(self, session: AsyncSession, model: type[Any]):
        self.session = session
        self.model = model

    async def get_current(self, profile_id: UUID) -> Any | None:
        stmt = select(self.model).where(
            self.model.profile_id == profile_id, self.model.is_current.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_current(self, profile_id: UUID) -> None:
        stmt = (
            update(self.model)
            .where(self.model.profile_id == profile_id, self.model.is_current.is_(True))
            .values(is_current=False)
        )
        await self.session.execute(stmt)

    async def create(self, analysis: Any) -> Any:
        self.session.add(analysis)
        await self.session.flush()
        return analysis
