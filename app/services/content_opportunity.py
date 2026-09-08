from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.strategy.opportunity_scorer import OpportunityScorer
from app.models.content_opportunity import (
    ContentOpportunity,
    OpportunityPriority,
    OpportunitySource,
    OpportunityStatus,
)
from app.models.performance_insight import PerformanceInsight
from app.repositories.audience_signal import AudienceSignalRepository
from app.repositories.content_opportunity import ContentOpportunityRepository
from app.repositories.content_profile import ContentProfileRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.repositories.market_signal import MarketSignalRepository


class ContentOpportunityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ContentOpportunityRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.market_repository = MarketIntelligenceRepository(session)
        self.signal_repository = MarketSignalRepository(session)
        self.audience_signal_repository = AudienceSignalRepository(session)
        self.scorer = OpportunityScorer()

    async def create(
        self, profile_id: UUID, workspace_id: UUID, **values: Any
    ) -> ContentOpportunity:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        source_signal = values["source_signal"]
        market_signal_id = values.get("market_signal_id")
        audience_signal_id = values.get("audience_signal_id")
        performance_insight_id = values.get("performance_insight_id")
        if source_signal == OpportunitySource.PERFORMANCE_GAP:
            if not performance_insight_id or market_signal_id or audience_signal_id:
                raise ValueError("Performance gap opportunities require a performance insight")
            result = await self.session.execute(
                select(PerformanceInsight).where(
                    PerformanceInsight.id == performance_insight_id,
                    PerformanceInsight.profile_id == profile_id,
                )
            )
            insight = result.scalar_one_or_none()
            if not insight:
                raise ValueError("Performance insight not found")
            signal = type(
                "PerformanceSignal",
                (),
                {
                    "strength_score": insight.confidence_score,
                    "topic": insight.analysis.content_performance.topic,
                    "expires_at": None,
                    "detected_at": insight.created_at,
                },
            )()
        elif audience_signal_id is not None:
            signal = await self._get_audience_signal_for_profile(profile_id, audience_signal_id)
        else:
            signal = await self._get_signal_for_profile(profile_id, market_signal_id)
        if source_signal == OpportunitySource.AUDIENCE_QUESTION:
            if audience_signal_id is None or market_signal_id is not None:
                raise ValueError("Audience question opportunities require an audience signal")
            signal = await self._get_audience_signal_for_profile(profile_id, audience_signal_id)
        elif source_signal != OpportunitySource.PERFORMANCE_GAP:
            if audience_signal_id is not None:
                raise ValueError("Audience signals require an audience_question opportunity")
            signal = await self._get_signal_for_profile(profile_id, market_signal_id)
        score = self.scorer.score(profile, signal, values["target_objective"])
        opportunity = ContentOpportunity(
            profile_id=profile_id,
            market_signal_id=(
                signal.id
                if source_signal != OpportunitySource.AUDIENCE_QUESTION and signal
                else None
            ),
            audience_signal_id=(
                signal.id if source_signal == OpportunitySource.AUDIENCE_QUESTION else None
            ),
            performance_insight_id=(
                performance_insight_id
                if source_signal == OpportunitySource.PERFORMANCE_GAP
                else None
            ),
            source_signal=source_signal,
            title=values["title"],
            strategic_rationale=self._rationale(
                profile.name, signal, values["target_objective"], source_signal
            ),
            target_objective=values["target_objective"],
            recommended_format=values.get("recommended_format"),
            relevance_score=score.profile_relevance,
            opportunity_score=score.total,
            priority=self._priority(score.total),
            status=OpportunityStatus.DRAFT,
            expires_at=signal.expires_at if signal else None,
            opportunity_metadata={
                "scoring_version": "v1",
                "score_components": {
                    "signal_strength": score.signal_strength,
                    "profile_relevance": score.profile_relevance,
                    "goal_alignment": score.goal_alignment,
                    "timeliness": score.timeliness,
                },
            },
        )
        await self.repository.create(opportunity)
        await self.session.commit()
        return opportunity

    async def get(
        self, profile_id: UUID, opportunity_id: UUID, workspace_id: UUID
    ) -> ContentOpportunity | None:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.get_by_id(profile_id, opportunity_id)

    async def list(
        self, profile_id: UUID, workspace_id: UUID, **filters: Any
    ) -> list[ContentOpportunity]:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(profile_id, **filters)

    async def update(
        self, profile_id: UUID, opportunity_id: UUID, workspace_id: UUID, **values: Any
    ) -> ContentOpportunity | None:
        profile = await self._verify_profile(profile_id, workspace_id)
        opportunity = await self.repository.get_by_id(profile_id, opportunity_id)
        if not opportunity:
            return None
        for field in ("title", "recommended_format", "status"):
            if values.get(field) is not None:
                setattr(opportunity, field, values[field])
        if values.get("target_objective") is not None:
            opportunity.target_objective = values["target_objective"]
            signal = await self._get_opportunity_signal(profile_id, opportunity)
            score = self.scorer.score(profile, signal, opportunity.target_objective)
            opportunity.opportunity_score = score.total
            opportunity.priority = self._priority(score.total)
            opportunity.opportunity_metadata = {
                **(opportunity.opportunity_metadata or {}),
                "score_components": {
                    "signal_strength": score.signal_strength,
                    "profile_relevance": score.profile_relevance,
                    "goal_alignment": score.goal_alignment,
                    "timeliness": score.timeliness,
                },
            }
        await self.repository.update(opportunity)
        await self.session.commit()
        return opportunity

    async def delete(self, profile_id: UUID, opportunity_id: UUID, workspace_id: UUID) -> bool:
        await self._verify_profile(profile_id, workspace_id)
        opportunity = await self.repository.get_by_id(profile_id, opportunity_id)
        if not opportunity:
            return False
        await self.repository.delete(opportunity)
        await self.session.commit()
        return True

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID) -> Any:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    async def _get_signal_for_profile(self, profile_id: UUID, signal_id: UUID | None) -> Any | None:
        if signal_id is None:
            return None
        signal = await self.signal_repository.get_by_id(signal_id)
        market = (
            await self.market_repository.get_by_id(signal.market_intelligence_id)
            if signal
            else None
        )
        if not signal or not market or market.content_profile_id != profile_id:
            raise ValueError("Market signal not found")
        return signal

    async def _get_audience_signal_for_profile(self, profile_id: UUID, signal_id: UUID) -> Any:
        signal = await self.audience_signal_repository.get_by_id(profile_id, signal_id)
        if not signal or signal.status != "active":
            raise ValueError("Audience signal not found")
        return signal

    async def _get_opportunity_signal(
        self, profile_id: UUID, opportunity: ContentOpportunity
    ) -> Any:
        if opportunity.source_signal == OpportunitySource.AUDIENCE_QUESTION:
            return await self._get_audience_signal_for_profile(
                profile_id, opportunity.audience_signal_id
            )
        return await self._get_signal_for_profile(profile_id, opportunity.market_signal_id)

    @staticmethod
    def _priority(score: float) -> OpportunityPriority:
        if score >= 0.80:
            return OpportunityPriority.HIGH
        if score >= 0.50:
            return OpportunityPriority.MEDIUM
        return OpportunityPriority.LOW

    @staticmethod
    def _rationale(
        profile_name: str,
        signal: Any | None,
        objective: str,
        source_signal: OpportunitySource = OpportunitySource.TREND,
    ) -> str:
        if source_signal == OpportunitySource.AUDIENCE_QUESTION and signal is not None:
            topic = signal.topic or "this topic"
            return (
                f'The audience is asking "{signal.question}". This question aligns with '
                f"{profile_name}'s focus on {topic} and can support the {objective} objective."
            )
        event = signal.title if signal else "This opportunity"
        relevance = (
            "the profile's context"
            if signal is None
            else f"{profile_name}'s audience and expertise"
        )
        return (
            f"{event} is a structured strategic signal relevant to {relevance}. "
            f"Considering it can support the {objective} objective."
        )
