from statistics import mean
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.infrastructure.locks.service import try_lock
from app.infrastructure.redis_client import get_redis
from app.models.content_performance import ContentPerformance
from app.models.learning import ExplanationGenerationSource, Learning, LearningDimension
from app.repositories.content_performance import ContentPerformanceRepository
from app.repositories.learning import LearningRepository
from app.services.ai.errors import AIError
from app.services.ai.router import AIRouter
from app.services.llm.learning_explainer import LearningExplainer

# Only `format` and `topic` have real structured backing data on
# ContentPerformance today (see app/models/content_performance.py) -- the
# other LearningDimension members (pillar/hook_style/cta/timing) are valid
# for manually-created or future learnings but this v1 extraction job
# cannot derive them from anything currently recorded.
_EXTRACTABLE_DIMENSIONS: dict[LearningDimension, str] = {
    LearningDimension.FORMAT: "format",
    LearningDimension.TOPIC: "topic",
}


def _relative_engagement(record: ContentPerformance) -> float | None:
    analysis = record.analysis
    if analysis is None or not analysis.baseline_available:
        return None
    return analysis.relative_engagement


async def extract_learnings_for_profile(
    session: AsyncSession, profile_id: UUID, router: AIRouter
) -> list[Learning]:
    """Deterministic pattern extraction: compares relative-engagement
    performance across `format`/`topic` values for a profile and upserts a
    `Learning` row for any value that meaningfully outperforms the
    profile's overall average. Read-only against Performance data (via
    `ContentPerformanceRepository`) -- never writes to ContentPerformance/
    PerformanceAnalysis.
    """
    performance_repository = ContentPerformanceRepository(session)
    learning_repository = LearningRepository(session)
    explainer = LearningExplainer(router)

    records = await performance_repository.all(profile_id)
    scored = [
        (record, _relative_engagement(record))
        for record in records
        if _relative_engagement(record) is not None
    ]
    if len(scored) < settings.learning_extraction_min_analyses:
        return []

    overall_average = mean(value for _, value in scored)
    if overall_average <= 0:
        return []

    touched: list[Learning] = []
    for dimension, attribute in _EXTRACTABLE_DIMENSIONS.items():
        groups: dict[str, list[tuple[ContentPerformance, float]]] = {}
        for record, value in scored:
            dimension_value = getattr(record, attribute)
            if not dimension_value:
                continue
            groups.setdefault(dimension_value, []).append((record, value))

        for dimension_value, group in groups.items():
            if len(group) < settings.learning_extraction_min_group_size:
                continue
            group_average = mean(value for _, value in group)
            delta = (group_average - overall_average) / overall_average
            if delta < settings.learning_extraction_min_delta_threshold:
                continue

            confidence_level = min(0.95, 0.4 + delta * 0.5 + min(len(group), 10) * 0.02)
            analysis_ids = [str(record.analysis.id) for record, _ in group if record.analysis]
            pattern_description = (
                f"Content with {dimension.value}={dimension_value!r} shows "
                f"{delta * 100:.0f}% higher relative engagement than {profile_id}'s "
                f"overall average, across {len(group)} analyzed posts."
            )
            supporting_evidence = {
                "performance_analysis_ids": analysis_ids,
                "sample_size": len(group),
                "relative_engagement_avg": group_average,
                "profile_overall_average": overall_average,
            }

            learning = await learning_repository.get_by_pattern(
                profile_id, dimension, dimension_value
            )
            if learning is None:
                learning = Learning(
                    profile_id=profile_id,
                    dimension=dimension,
                    dimension_value=dimension_value,
                    pattern_description=pattern_description,
                    confidence_level=confidence_level,
                    supporting_evidence=supporting_evidence,
                )
                await learning_repository.create(learning)
            else:
                learning.pattern_description = pattern_description
                learning.confidence_level = confidence_level
                learning.supporting_evidence = supporting_evidence

            try:
                ai_result = await explainer.explain(
                    context={
                        "pattern_description": pattern_description,
                        "dimension": dimension.value,
                        "dimension_value": dimension_value,
                        "supporting_evidence": supporting_evidence,
                    }
                )
                learning.explanation = ai_result.output.explanation
                learning.explanation_generation_source = ExplanationGenerationSource.AI
            except AIError:
                learning.explanation = pattern_description
                learning.explanation_generation_source = ExplanationGenerationSource.DETERMINISTIC

            touched.append(learning)

    await session.commit()
    return touched


async def extract_learnings_cron(ctx: dict) -> None:
    """arq cron entrypoint (Day 15 pattern, see
    app.services.publish_promotion): runs nightly across every profile that
    has ContentPerformance history. `try_lock` is a performance
    optimization against redundant concurrent runs across worker
    instances, not a correctness guarantee -- `extract_learnings_for_profile`
    is itself idempotent via the `(profile_id, dimension, dimension_value)`
    unique constraint.
    """
    redis = get_redis()
    async with try_lock(redis, "learning-extraction:tick") as acquired:
        if not acquired:
            return
        async with async_session_factory() as session:
            router = AIRouter()
            result = await session.execute(select(ContentPerformance.profile_id).distinct())
            profile_ids = [row[0] for row in result.all()]
            for profile_id in profile_ids:
                await extract_learnings_for_profile(session, profile_id, router)
