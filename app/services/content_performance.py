from datetime import date
from statistics import median
from typing import Any
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.infrastructure.jobs.registry import register_handler
from app.infrastructure.jobs.service import submit_job
from app.models.ai_job import AIJob
from app.models.content_performance import ContentPerformance
from app.models.performance_analysis import PerformanceAnalysis
from app.repositories.content_performance import ContentPerformanceRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.published_content import PublishedContentRepository
from app.services.ai.errors import AIError

PERFORMANCE_ANALYSIS_TASK = "performance_analysis"


class DuplicateReportingPeriodError(ValueError):
    """Raised when metrics have already been recorded for this published
    content and reporting period -- surfaced by the database's unique
    constraint, not an application-level pre-check.
    """


class ContentPerformanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ContentPerformanceRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.published_repository = PublishedContentRepository(session)

    async def _profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def create(
        self, profile_id: UUID, workspace_id: UUID, **values: Any
    ) -> ContentPerformance:
        await self._profile(profile_id, workspace_id)
        record = ContentPerformance(profile_id=profile_id, **values)
        await self.repository.create(record)
        await self.session.commit()
        return record

    async def get(self, profile_id: UUID, workspace_id: UUID, record_id: UUID):
        await self._profile(profile_id, workspace_id)
        return await self.repository.get(profile_id, record_id)

    async def list(self, profile_id: UUID, workspace_id: UUID, **filters: Any):
        await self._profile(profile_id, workspace_id)
        return await self.repository.list(profile_id, **filters)

    async def update(self, profile_id: UUID, workspace_id: UUID, record_id: UUID, **values: Any):
        await self._profile(profile_id, workspace_id)
        record = await self.repository.get(profile_id, record_id)
        if not record:
            return None
        for key, value in values.items():
            if value is not None:
                setattr(record, key, value)
        await self.session.commit()
        return record

    async def delete(self, profile_id: UUID, workspace_id: UUID, record_id: UUID) -> bool:
        await self._profile(profile_id, workspace_id)
        record = await self.repository.get(profile_id, record_id)
        if not record:
            return False
        await self.repository.delete(record)
        await self.session.commit()
        return True

    async def analyze(
        self, profile_id: UUID, workspace_id: UUID, record_id: UUID
    ) -> PerformanceAnalysis:
        await self._profile(profile_id, workspace_id)
        current = await self.repository.get(profile_id, record_id)
        if not current:
            raise ValueError("Content performance not found")
        records = [item for item in await self.repository.all(profile_id) if item.id != record_id]
        matching = [
            item
            for item in records
            if item.platform == current.platform and item.format == current.format
        ]
        if len(matching) < 3:
            matching = [item for item in records if item.platform == current.platform]
        if len(matching) < 3:
            matching = records
        metrics = self._metrics(current)
        baselines = {}
        for name in ("engagement_rate", "share_rate", "save_rate", "retention_rate"):
            values = [
                self._metrics(item)[name]
                for item in matching
                if self._metrics(item)[name] is not None
            ]
            if values:
                baselines[name] = median(values)
        available = len(matching) >= 3
        relative = {
            key: self._relative(metrics[key], baselines.get(key)) if available else None
            for key in baselines
        }
        evidence = {
            "baseline_available": available,
            "comparables_count": len(matching),
            "metrics": {
                key: {
                    "current": metrics[key],
                    "baseline": baselines.get(key),
                    "relative": relative[key],
                }
                for key in metrics
                if key in baselines
            },
        }
        classification = (
            self._classification([value for value in relative.values() if value is not None])
            if available
            else None
        )
        analysis = current.analysis or PerformanceAnalysis(
            profile_id=profile_id, content_performance_id=record_id
        )
        for key, value in metrics.items():
            setattr(analysis, key, value)
        for key, value in baselines.items():
            setattr(analysis, f"baseline_{key}", value if available else None)
        analysis.relative_engagement = relative.get("engagement_rate")
        analysis.relative_shares = relative.get("share_rate")
        analysis.relative_saves = relative.get("save_rate")
        analysis.relative_retention = relative.get("retention_rate")
        analysis.performance_classification = classification
        analysis.baseline_available = available
        analysis.comparables_count = len(matching)
        analysis.evidence = evidence
        self.session.add(analysis)
        await self.session.commit()
        return analysis

    async def submit_metrics(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        published_content_id: UUID,
        arq_pool: ArqRedis,
        reporting_period: date,
        **metrics: Any,
    ) -> tuple[ContentPerformance, AIJob]:
        """Attach a manual metrics snapshot to a specific PublishedContent
        the caller owns, then enqueue the Day 15 async job that runs the
        Day 9 analysis pipeline against it. Returns immediately with the
        created record and its job reference -- analysis never runs inline.
        """
        await self._profile(profile_id, workspace_id)
        published = await self.published_repository.get_by_id(profile_id, published_content_id)
        if not published:
            raise ValueError("Published content not found")

        record = ContentPerformance(
            profile_id=profile_id,
            published_content_id=published_content_id,
            platform=published.platform,
            reporting_period=reporting_period,
            **metrics,
        )
        self.session.add(record)
        try:
            await self.session.flush()
        except IntegrityError as error:
            await self.session.rollback()
            raise DuplicateReportingPeriodError(
                "Metrics have already been recorded for this published content and period"
            ) from error

        job = await submit_job(
            self.session,
            arq_pool,
            PERFORMANCE_ANALYSIS_TASK,
            profile_id,
            {
                "content_performance_id": str(record.id),
                "profile_id": str(profile_id),
                "workspace_id": str(workspace_id),
            },
        )
        await self.session.commit()
        return record, job

    async def enqueue_analysis(
        self, profile_id: UUID, workspace_id: UUID, record_id: UUID, arq_pool: ArqRedis
    ) -> AIJob:
        """Entry point for the manual `/analyze` trigger -- Day 25 converts
        this from an inline call to `analyze()` into an explicit Day 15
        async job submission, per the required update to the existing call
        pattern. `analyze()` itself (the Day 9 scoring/classification logic)
        is unchanged; only how it gets invoked changes.
        """
        await self._profile(profile_id, workspace_id)
        current = await self.repository.get(profile_id, record_id)
        if not current:
            raise ValueError("Content performance not found")

        job = await submit_job(
            self.session,
            arq_pool,
            PERFORMANCE_ANALYSIS_TASK,
            profile_id,
            {
                "content_performance_id": str(record_id),
                "profile_id": str(profile_id),
                "workspace_id": str(workspace_id),
            },
        )
        await self.session.commit()
        return job

    @staticmethod
    def _denominator(record: ContentPerformance) -> int | None:
        return next(
            (
                value
                for value in (record.reach, record.views, record.impressions)
                if value is not None and value > 0
            ),
            None,
        )

    @classmethod
    def _metrics(cls, record: ContentPerformance) -> dict[str, float | None]:
        denominator = cls._denominator(record)

        def rate(value: int | None) -> float | None:
            return value / denominator if value is not None and denominator else None

        return {
            "engagement_rate": rate(
                sum(
                    value or 0
                    for value in (record.likes, record.comments, record.shares, record.saves)
                )
            ),
            "share_rate": rate(record.shares),
            "save_rate": rate(record.saves),
            "comment_rate": rate(record.comments),
            "click_through_rate": rate(record.clicks),
            "conversion_rate": rate(record.conversions),
            "retention_rate": record.retention_rate,
        }

    @staticmethod
    def _relative(current: float | None, baseline: float | None) -> float | None:
        if current is None or baseline is None or baseline == 0:
            return None
        return current / baseline

    @staticmethod
    def _classification(values: list[float]) -> str | None:
        if not values:
            return None
        score = median(values)
        return (
            "exceptional"
            if score >= 1.75
            else "strong"
            if score >= 1.25
            else "normal"
            if score >= 0.8
            else "weak"
            if score >= 0.5
            else "poor"
        )


async def _run_performance_analysis_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Background handler for `PERFORMANCE_ANALYSIS_TASK`: runs the
    unchanged Day 9 deterministic analysis, then attempts the AI-reasoned
    insight on top of it. `analyze()` commits before the reasoner is ever
    called, so the deterministic `PerformanceAnalysis` survives even if AI
    reasoning fails or every provider is unavailable, per the "deterministic
    first, AI enriched" architectural rule -- the job never fails the
    analysis just because insight generation did.
    """
    # Local imports: app.services.performance_insight imports
    # ContentPerformanceService from this module, so importing it back at
    # module scope here would be circular.
    from app.services.llm.performance_reasoner import PerformanceReasoner
    from app.services.performance_insight import PerformanceInsightService

    profile_id = UUID(payload["profile_id"])
    workspace_id = UUID(payload["workspace_id"])
    record_id = UUID(payload["content_performance_id"])

    async with async_session_factory() as session:
        from app.services.ai.router import AIRouter

        insight_service = PerformanceInsightService(session, PerformanceReasoner(AIRouter()))
        try:
            insight = await insight_service.create(profile_id, workspace_id, record_id)
        except AIError:
            performance_service = ContentPerformanceService(session)
            record = await performance_service.repository.get(profile_id, record_id)
            analysis = record.analysis if record else None
            return {
                "analysis_id": str(analysis.id) if analysis else None,
                "insight_id": None,
            }
        return {
            "analysis_id": str(insight.performance_analysis_id),
            "insight_id": str(insight.id),
        }


register_handler(PERFORMANCE_ANALYSIS_TASK, _run_performance_analysis_job)
