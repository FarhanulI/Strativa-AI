from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_analysis import (
    AnalysisGenerationSource,
    AudienceAnalysis,
    BrandAnalysis,
    MarketAnalysis,
)
from app.models.performance_insight import PerformanceInsight
from app.repositories.intelligence_analysis import IntelligenceAnalysisRepository

# An `insufficient_data` component analysis carries only a templated
# "not enough data yet" message, not real reasoning -- it must not count as
# an available component for synthesis, or synthesis would be built on
# fabricated substance.
_SUBSTANTIVE_SOURCES = {AnalysisGenerationSource.AI, AnalysisGenerationSource.AI_FALLBACK}
_PERFORMANCE_INSIGHT_LIMIT = 5

_DOMAIN_MODELS: dict[str, type[Any]] = {
    "brand": BrandAnalysis,
    "audience": AudienceAnalysis,
    "market": MarketAnalysis,
}


@dataclass
class SynthesisGrounding:
    """What the synthesis reasoner needs, or refuses to run, for a profile.

    `supporting_analyses` is computed here, deterministically, from real
    component-analysis/insight ids -- never from anything the LLM returns --
    so lineage can't be fabricated, mirroring
    `app.services.intelligence.grounding.GroundingResult`.
    """

    sufficient: bool
    component_count: int
    available_domains: list[str] = field(default_factory=list)
    missing_domains: list[str] = field(default_factory=list)
    supporting_analyses: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    fallback_summary: str = ""


async def gather_synthesis_grounding(session: AsyncSession, profile_id: UUID) -> SynthesisGrounding:
    supporting_analyses: list[str] = []
    context: dict[str, Any] = {}
    available_domains: list[str] = []
    missing_domains: list[str] = []

    for domain, model in _DOMAIN_MODELS.items():
        repository = IntelligenceAnalysisRepository(session, model)
        analysis = await repository.get_current(profile_id)
        if analysis is not None and analysis.generation_source in _SUBSTANTIVE_SOURCES:
            available_domains.append(domain)
            supporting_analyses.append(str(analysis.id))
            context[domain] = {"available": True, "insights": analysis.insights}
        else:
            missing_domains.append(domain)
            context[domain] = {"available": False}

    result = await session.execute(
        select(PerformanceInsight)
        .where(PerformanceInsight.profile_id == profile_id, PerformanceInsight.status == "active")
        .order_by(PerformanceInsight.confidence_score.desc(), PerformanceInsight.created_at.desc())
        .limit(_PERFORMANCE_INSIGHT_LIMIT)
    )
    insights = list(result.scalars().all())
    if insights:
        available_domains.append("performance")
        supporting_analyses.extend(str(insight.id) for insight in insights)
        context["performance"] = {
            "available": True,
            "insights": [
                {
                    "summary": insight.summary,
                    "likely_reason": insight.likely_reason,
                    "strategic_learning": insight.strategic_learning,
                    "recommended_action": insight.recommended_action,
                    "confidence_score": insight.confidence_score,
                }
                for insight in insights
            ],
        }
    else:
        missing_domains.append("performance")
        context["performance"] = {"available": False}

    component_count = len(available_domains)
    sufficient = component_count >= 2

    if not sufficient:
        fallback_summary = (
            f"Only {component_count} of 4 intelligence domains "
            f"({', '.join(available_domains) or 'none'}) currently have grounded AI analysis. "
            "Strategic synthesis requires at least two grounded component analyses "
            f"(missing: {', '.join(missing_domains)})."
        )
    else:
        fallback_summary = (
            f"{component_count} of 4 intelligence domains ({', '.join(available_domains)}) have "
            "grounded analysis, but AI-generated synthesis is currently unavailable. Review "
            "each domain's analysis directly for strategic context."
        )

    return SynthesisGrounding(
        sufficient=sufficient,
        component_count=component_count,
        available_domains=available_domains,
        missing_domains=missing_domains,
        supporting_analyses=supporting_analyses,
        context=context,
        fallback_summary=fallback_summary,
    )
