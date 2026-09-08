from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance_insight import PerformanceInsight
from app.repositories.content_profile import ContentProfileRepository
from app.services.content_performance import ContentPerformanceService
from app.services.llm.performance_reasoner import PerformanceReasoner


class PerformanceInsightService:
    def __init__(self, session: AsyncSession, reasoner: PerformanceReasoner):
        self.session = session
        self.reasoner = reasoner
        self.performance = ContentPerformanceService(session)
        self.profile_repository = ContentProfileRepository(session)

    async def create(
        self, profile_id: UUID, workspace_id: UUID, record_id: UUID
    ) -> PerformanceInsight:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        content = await self.performance.repository.get(profile_id, record_id)
        if not content:
            raise ValueError("Content performance not found")
        analysis = content.analysis or await self.performance.analyze(
            profile_id, workspace_id, record_id
        )
        ai_result = await self.reasoner.reason(profile=profile, content=content, analysis=analysis)
        insight = PerformanceInsight(
            profile_id=profile_id,
            performance_analysis_id=analysis.id,
            evidence=analysis.evidence,
            model_provider=ai_result.metadata.provider,
            model_name=ai_result.metadata.model,
            prompt_version=self.reasoner.prompt_version,
            **ai_result.output.model_dump(),
        )
        self.session.add(insight)
        await self.session.commit()
        return insight

    async def list_for_record(self, profile_id: UUID, workspace_id: UUID, record_id: UUID):
        if not await self.performance.get(profile_id, workspace_id, record_id):
            raise ValueError("Content performance not found")
        result = await self.session.execute(
            select(PerformanceInsight)
            .join(PerformanceInsight.analysis)
            .where(
                PerformanceInsight.profile_id == profile_id,
                PerformanceInsight.analysis.has(content_performance_id=record_id),
            )
        )
        return list(result.scalars().all())

    async def list_for_profile(self, profile_id: UUID, workspace_id: UUID, **filters: Any):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        statement = select(PerformanceInsight).where(PerformanceInsight.profile_id == profile_id)
        for field in ("insight_type", "status"):
            if filters.get(field) is not None:
                statement = statement.where(getattr(PerformanceInsight, field) == filters[field])
        if filters.get("minimum_confidence") is not None:
            statement = statement.where(
                PerformanceInsight.confidence_score >= filters["minimum_confidence"]
            )
        result = await self.session.execute(
            statement.order_by(PerformanceInsight.created_at.desc())
        )
        return list(result.scalars().all())
