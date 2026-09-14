from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.content_profile import ContentProfile


@dataclass
class GroundingResult:
    """What a domain reasoner needs to run, or refuse to run, for a profile.

    `grounded_on` and `fingerprint` are computed here, deterministically,
    from real record ids and timestamps — never from anything the LLM
    returns — so lineage can't be fabricated and staleness can be detected
    by comparing fingerprints without an event hook on every domain CRUD
    service.
    """

    sufficient: bool
    grounded_on: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    fallback_summary: str = ""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _max_updated_at(items: list[Any]) -> datetime | None:
    timestamps = [item.updated_at for item in items if getattr(item, "updated_at", None)]
    return max(timestamps) if timestamps else None


def brand_grounding(profile: ContentProfile) -> GroundingResult:
    brand = profile.brand
    if brand is None:
        return GroundingResult(
            sufficient=False,
            fallback_summary=(
                "No brand intelligence has been recorded for this profile yet. "
                "Add positioning, mission, or voice/tone to enable AI-generated "
                "brand insights."
            ),
        )

    narrative_fields = {
        "positioning": brand.positioning,
        "mission": brand.mission,
        "vision": brand.vision,
        "unique_selling_proposition": brand.unique_selling_proposition,
        "voice": brand.voice,
        "tone": brand.tone,
    }
    filled = {key: value for key, value in narrative_fields.items() if value}
    sufficient = len(filled) >= 1

    fingerprint = {"root_updated_at": _iso(brand.updated_at)}
    if not sufficient:
        return GroundingResult(
            sufficient=False,
            grounded_on=[str(brand.id)],
            fingerprint=fingerprint,
            fallback_summary=(
                "Brand intelligence exists but no positioning, mission, vision, USP, "
                "voice, or tone has been defined yet. AI-generated brand insights "
                "require at least one of these fields to reason about."
            ),
        )

    return GroundingResult(
        sufficient=True,
        grounded_on=[str(brand.id)],
        fingerprint=fingerprint,
        fallback_summary=(
            f"Brand intelligence is populated ({len(filled)} of "
            f"{len(narrative_fields)} core fields defined: "
            f"{', '.join(filled.keys())}), but AI-generated strategic analysis is "
            "currently unavailable. Review these fields directly for brand strategy."
        ),
        context={
            "positioning": brand.positioning,
            "mission": brand.mission,
            "vision": brand.vision,
            "unique_selling_proposition": brand.unique_selling_proposition,
            "voice": brand.voice,
            "tone": brand.tone,
            "values": brand.values,
            "personality": brand.personality,
            "profile": {
                "topics": profile.topics or [],
                "expertise": profile.expertise or [],
                "goals": profile.goals or [],
            },
        },
    )


def audience_grounding(profile: ContentProfile) -> GroundingResult:
    audience = profile.audience_intelligence
    if audience is None:
        return GroundingResult(
            sufficient=False,
            fallback_summary=(
                "No audience intelligence has been recorded for this profile yet. "
                "Add at least one persona and one pain point to enable AI-generated "
                "audience insights."
            ),
        )

    personas = audience.personas
    pain_points = audience.pain_points
    desires = audience.desires
    questions = audience.questions
    objections = audience.objections
    sufficient = len(personas) >= 1 and len(pain_points) >= 1

    all_records = [*personas, *pain_points, *desires, *questions, *objections]
    grounded_on = [str(audience.id), *(str(record.id) for record in all_records)]
    fingerprint = {
        "root_updated_at": _iso(audience.updated_at),
        "record_count": len(all_records),
        "max_record_updated_at": _iso(_max_updated_at(all_records)),
    }

    if not sufficient:
        return GroundingResult(
            sufficient=False,
            grounded_on=grounded_on,
            fingerprint=fingerprint,
            fallback_summary=(
                f"Audience intelligence currently has {len(personas)} persona(s) and "
                f"{len(pain_points)} pain point(s). AI-generated audience insights "
                "require at least one of each to synthesize audience needs."
            ),
        )

    return GroundingResult(
        sufficient=True,
        grounded_on=grounded_on,
        fingerprint=fingerprint,
        fallback_summary=(
            f"Audience intelligence includes {len(personas)} persona(s), "
            f"{len(pain_points)} pain point(s), {len(desires)} desire(s), "
            f"{len(questions)} question(s), and {len(objections)} objection(s), but "
            "AI-generated synthesis is currently unavailable. Review these records "
            "directly for audience needs."
        ),
        context={
            "personas": [
                {"name": p.name, "description": p.description, "goals": p.goals or []}
                for p in personas
            ],
            "pain_points": [
                {"title": p.title, "description": p.description, "severity": p.severity}
                for p in pain_points
            ],
            "desires": [
                {"title": d.title, "description": d.description, "importance": d.importance}
                for d in desires
            ],
            "questions": [
                {"question": q.question, "context": q.context, "frequency": q.frequency}
                for q in questions
            ],
            "objections": [{"title": o.title, "description": o.description} for o in objections],
        },
    )


def market_grounding(profile: ContentProfile) -> GroundingResult:
    market = profile.market_intelligence
    if market is None:
        return GroundingResult(
            sufficient=False,
            fallback_summary=(
                "No market intelligence has been recorded for this profile yet. "
                "Add at least one topic and one market signal to enable "
                "AI-generated market insights."
            ),
        )

    topics = market.topics
    signals = market.market_signals
    competitors = market.competitors
    sufficient = len(topics) >= 1 and len(signals) >= 1

    all_records = [*topics, *signals, *competitors]
    grounded_on = [str(market.id), *(str(record.id) for record in all_records)]
    fingerprint = {
        "root_updated_at": _iso(market.updated_at),
        "record_count": len(all_records),
        "max_record_updated_at": _iso(_max_updated_at(all_records)),
    }

    if not sufficient:
        return GroundingResult(
            sufficient=False,
            grounded_on=grounded_on,
            fingerprint=fingerprint,
            fallback_summary=(
                f"Market intelligence currently has {len(topics)} topic(s) and "
                f"{len(signals)} market signal(s). AI-generated market insights "
                "require at least one of each to reason about the external "
                "environment."
            ),
        )

    return GroundingResult(
        sufficient=True,
        grounded_on=grounded_on,
        fingerprint=fingerprint,
        fallback_summary=(
            f"Market intelligence includes {len(topics)} topic(s), {len(signals)} "
            f"market signal(s), and {len(competitors)} competitor(s), but "
            "AI-generated synthesis is currently unavailable. Review these records "
            "directly for market context."
        ),
        context={
            "topics": [
                {"name": t.name, "description": t.description, "relevance_score": t.relevance_score}
                for t in topics
            ],
            "market_signals": [
                {
                    "title": s.title,
                    "signal_type": s.signal_type,
                    "velocity_score": s.velocity_score,
                    "engagement_score": s.engagement_score,
                    "relevance_score": s.relevance_score,
                }
                for s in signals
            ],
            "competitors": [
                {
                    "name": c.name,
                    "description": c.description,
                    "niche": c.niche,
                }
                for c in competitors
            ],
            "profile": {
                "positioning": profile.positioning,
                "topics": profile.topics or [],
                "goals": profile.goals or [],
            },
        },
    )
