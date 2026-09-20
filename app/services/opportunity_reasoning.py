from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.infrastructure.jobs.registry import register_handler
from app.infrastructure.ratelimit.errors import RateLimitDeferredError
from app.infrastructure.ratelimit.limiter import check_sliding_window
from app.infrastructure.ratelimit.policy import reasoning_rule
from app.infrastructure.redis_client import get_redis
from app.models.content_opportunity import ContentOpportunity, RationaleGenerationSource
from app.models.intelligence_analysis import AnalysisGenerationSource
from app.models.learning import Learning
from app.repositories.content_intelligence_synthesis import ContentIntelligenceSynthesisRepository
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AITask
from app.services.llm.opportunity_reasoner import OpportunityReasoner

# A synthesis carrying only a templated `insufficient_data` message is not
# real reasoning -- mirrors app.content_intelligence.grounding's
# `_SUBSTANTIVE_SOURCES`, so an insufficient-data synthesis counts the same
# as "no synthesis yet" for grounding purposes.
_SUBSTANTIVE_SOURCES = {AnalysisGenerationSource.AI, AnalysisGenerationSource.AI_FALLBACK}


async def generate_rationale(
    session: AsyncSession, opportunity_id: UUID, profile_id: UUID, router: AIRouter
) -> ContentOpportunity:
    """Run (or fall back on) the `opportunity_reasoning` AI task and update
    `strategic_rationale` in place. Called from the background job handler;
    never invoked synchronously from a request. The deterministic score,
    score components, priority, and ranking are never read or written here
    -- only the natural-language rationale text and its provenance.
    """
    opportunity = await session.get(ContentOpportunity, opportunity_id)
    if opportunity is None or opportunity.profile_id != profile_id:
        raise ValueError("Content opportunity not found")

    synthesis_repository = ContentIntelligenceSynthesisRepository(session)
    synthesis = await synthesis_repository.get_current(profile_id)
    synthesis_available = (
        synthesis is not None and synthesis.generation_source in _SUBSTANTIVE_SOURCES
    )

    if synthesis_available:
        metadata = opportunity.opportunity_metadata or {}
        score_components = metadata.get("score_components", {})
        context: dict[str, Any] = {
            "opportunity": {
                "title": opportunity.title,
                "source_signal": opportunity.source_signal.value,
                "target_objective": opportunity.target_objective.value,
                "opportunity_score": opportunity.opportunity_score,
                "relevance_score": opportunity.relevance_score,
                "priority": opportunity.priority.value,
                "score_components": score_components,
            },
            "intelligence_synthesis": {
                "summary": synthesis.summary,
                "key_themes": synthesis.key_themes,
            },
        }

        # Day 26 feedback-loop closure: when a Learning influenced this
        # opportunity's score (see app.ai.strategy.opportunity_scorer's
        # learning_alignment factor), surface it so the AI-reasoned
        # rationale can explicitly reference the pattern instead of only
        # ever grounding in the cross-domain synthesis.
        influencing_learning_id = metadata.get("influencing_learning_id")
        if influencing_learning_id:
            learning = await session.get(Learning, UUID(influencing_learning_id))
            if learning is not None and learning.profile_id == profile_id:
                context["influencing_learning"] = {
                    "dimension": learning.dimension.value,
                    "dimension_value": learning.dimension_value,
                    "pattern_description": learning.pattern_description,
                    "explanation": learning.explanation,
                }
        reasoner = OpportunityReasoner(router)
        try:
            ai_result = await reasoner.reason(context=context)
            opportunity.strategic_rationale = ai_result.output.strategic_rationale
            opportunity.rationale_generation_source = RationaleGenerationSource.AI
        except AIError:
            # AI provider failure: leave the existing (deterministic
            # placeholder) strategic_rationale as final, per day-18's
            # "deterministic fallback" requirement.
            opportunity.rationale_generation_source = RationaleGenerationSource.DETERMINISTIC
    else:
        # No current substantive synthesis yet for the profile: the
        # deterministic placeholder written at creation stays final.
        opportunity.rationale_generation_source = RationaleGenerationSource.DETERMINISTIC

    opportunity.rationale_generated_at = datetime.now(UTC)
    await session.flush()
    await session.commit()
    return opportunity


async def _run_opportunity_reasoning_job(payload: dict) -> dict:
    profile_id = UUID(payload["profile_id"])
    opportunity_id = UUID(payload["opportunity_id"])

    # Per-profile rate limiting (Day 15 sliding-window limiter) so a burst
    # of newly-created opportunities for one profile doesn't spike AI cost.
    # An exceeded limit defers the job rather than dropping or failing it —
    # see app.infrastructure.jobs.worker_tasks._handle_rate_limit_deferral.
    redis = get_redis()
    rule = reasoning_rule()
    allowed, _ = await check_sliding_window(
        redis, f"opportunity_reasoning:profile:{profile_id}", rule
    )
    if not allowed:
        raise RateLimitDeferredError(rule.window_seconds)

    async with async_session_factory() as session:
        router = AIRouter()
        opportunity = await generate_rationale(session, opportunity_id, profile_id, router)

    return {
        "opportunity_id": str(opportunity.id),
        "rationale_generation_source": opportunity.rationale_generation_source.value,
    }


register_handler(AITask.OPPORTUNITY_REASONING.value, _run_opportunity_reasoning_job)
