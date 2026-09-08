from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_performance import ContentPerformance
from app.models.performance_analysis import PerformanceAnalysis
from app.repositories.content_performance import ContentPerformanceRepository
from app.repositories.content_profile import ContentProfileRepository


class ContentPerformanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ContentPerformanceRepository(session)
        self.profile_repository = ContentProfileRepository(session)

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
