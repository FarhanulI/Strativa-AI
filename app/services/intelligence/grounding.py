from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.content_profile import ContentProfile
from app.models.intelligence_analysis import GroundingBasis


@dataclass
class GroundingResult:
    """What a domain reasoner needs to run, or refuse to run, for a profile.

    `grounded_on` and `fingerprint` are computed here, deterministically,
    from real record ids and timestamps — never from anything the LLM
    returns — so lineage can't be fabricated and staleness can be detected
    by comparing fingerprints without an event hook on every domain CRUD
    service.

    `grounding_basis` records whether the grounding data came from onboarding
    -stated profile fields (`stated`), accumulated signal/record data
    (`observed`), or both (`mixed`). It is only meaningful when `sufficient`
    is True — Brand analysis doesn't distinguish the two (its data is
    already always profile-stated), so only Audience and Market grounding
    set it.
    """

    sufficient: bool
    grounded_on: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    fallback_summary: str = ""
    grounding_basis: GroundingBasis | None = None


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


def _stated_audience_fields(profile: ContentProfile) -> dict[str, Any]:
    """Onboarding-captured data that describes the intended audience
    independent of any observed engagement/persona-building work: the
    profile's own stated target-audience description, plus the audience
    intelligence root's stated summary/geography/language/demographics/
    psychographics fields (all filled during onboarding, not derived from
    accumulated personas/pain points/etc.).
    """
    fields: dict[str, Any] = {}
    if profile.description:
        fields["profile.description"] = profile.description
    if profile.goals:
        fields["profile.goals"] = profile.goals
    audience = profile.audience_intelligence
    if audience is not None:
        if audience.summary:
            fields["audience.summary"] = audience.summary
        if audience.geography:
            fields["audience.geography"] = audience.geography
        if audience.language:
            fields["audience.language"] = audience.language
        if audience.demographics:
            fields["audience.demographics"] = audience.demographics
        if audience.psychographics:
            fields["audience.psychographics"] = audience.psychographics
    return fields


def audience_grounding(profile: ContentProfile) -> GroundingResult:
    audience = profile.audience_intelligence
    personas = audience.personas if audience else []
    pain_points = audience.pain_points if audience else []
    desires = audience.desires if audience else []
    questions = audience.questions if audience else []
    objections = audience.objections if audience else []
    observed_sufficient = len(personas) >= 1 and len(pain_points) >= 1

    stated_fields = _stated_audience_fields(profile)
    stated_sufficient = len(stated_fields) >= 1

    sufficient = observed_sufficient or stated_sufficient
    if observed_sufficient and stated_sufficient:
        grounding_basis = GroundingBasis.MIXED
    elif observed_sufficient:
        grounding_basis = GroundingBasis.OBSERVED
    elif stated_sufficient:
        grounding_basis = GroundingBasis.STATED
    else:
        grounding_basis = None

    all_records = [*personas, *pain_points, *desires, *questions, *objections]
    grounded_on = [
        *([str(audience.id)] if audience is not None else []),
        *(str(record.id) for record in all_records),
        *(f"stated:{key}" for key in stated_fields),
    ]
    fingerprint = {
        "root_updated_at": _iso(audience.updated_at) if audience else None,
        "record_count": len(all_records),
        "max_record_updated_at": _iso(_max_updated_at(all_records)),
        "profile_updated_at": _iso(profile.updated_at),
        "stated_fields": sorted(stated_fields.keys()),
    }

    if not sufficient:
        return GroundingResult(
            sufficient=False,
            grounded_on=grounded_on,
            fingerprint=fingerprint,
            fallback_summary=(
                f"Audience intelligence currently has {len(personas)} persona(s) and "
                f"{len(pain_points)} pain point(s), and no stated target-audience "
                "description has been recorded on the profile yet. AI-generated "
                "audience insights require either at least one persona and one pain "
                "point, or a stated target audience (profile description, goals, or "
                "an audience summary/geography/demographics)."
            ),
        )

    context: dict[str, Any] = {
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
    }
    if stated_fields:
        context["stated"] = stated_fields

    return GroundingResult(
        sufficient=True,
        grounded_on=grounded_on,
        fingerprint=fingerprint,
        grounding_basis=grounding_basis,
        fallback_summary=(
            f"Audience intelligence includes {len(personas)} persona(s), "
            f"{len(pain_points)} pain point(s), {len(desires)} desire(s), "
            f"{len(questions)} question(s), and {len(objections)} objection(s) "
            f"({'plus stated onboarding data' if stated_fields else 'no stated data'}), "
            "but AI-generated synthesis is currently unavailable. Review these "
            "records directly for audience needs."
        ),
        context=context,
    )


def _stated_market_fields(profile: ContentProfile) -> dict[str, Any]:
    """Onboarding-captured data that describes the external environment
    independent of any accumulated topics/signals/competitors: the
    profile's own stated topics, expertise, and positioning.
    """
    fields: dict[str, Any] = {}
    if profile.topics:
        fields["profile.topics"] = profile.topics
    if profile.expertise:
        fields["profile.expertise"] = profile.expertise
    if profile.positioning:
        fields["profile.positioning"] = profile.positioning
    market = profile.market_intelligence
    if market is not None and market.summary:
        fields["market.summary"] = market.summary
    return fields


def market_grounding(profile: ContentProfile) -> GroundingResult:
    market = profile.market_intelligence
    topics = market.topics if market else []
    signals = market.market_signals if market else []
    competitors = market.competitors if market else []
    observed_sufficient = len(topics) >= 1 and len(signals) >= 1

    stated_fields = _stated_market_fields(profile)
    stated_sufficient = len(stated_fields) >= 1

    sufficient = observed_sufficient or stated_sufficient
    if observed_sufficient and stated_sufficient:
        grounding_basis = GroundingBasis.MIXED
    elif observed_sufficient:
        grounding_basis = GroundingBasis.OBSERVED
    elif stated_sufficient:
        grounding_basis = GroundingBasis.STATED
    else:
        grounding_basis = None

    all_records = [*topics, *signals, *competitors]
    grounded_on = [
        *([str(market.id)] if market is not None else []),
        *(str(record.id) for record in all_records),
        *(f"stated:{key}" for key in stated_fields),
    ]
    fingerprint = {
        "root_updated_at": _iso(market.updated_at) if market else None,
        "record_count": len(all_records),
        "max_record_updated_at": _iso(_max_updated_at(all_records)),
        "profile_updated_at": _iso(profile.updated_at),
        "stated_fields": sorted(stated_fields.keys()),
    }

    if not sufficient:
        return GroundingResult(
            sufficient=False,
            grounded_on=grounded_on,
            fingerprint=fingerprint,
            fallback_summary=(
                f"Market intelligence currently has {len(topics)} topic(s) and "
                f"{len(signals)} market signal(s), and no stated topics, expertise, "
                "or positioning has been recorded on the profile yet. AI-generated "
                "market insights require either at least one topic and one market "
                "signal, or stated profile topics/expertise/positioning to reason "
                "about the external environment."
            ),
        )

    context: dict[str, Any] = {
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
    }
    if stated_fields:
        context["stated"] = stated_fields

    return GroundingResult(
        sufficient=True,
        grounded_on=grounded_on,
        fingerprint=fingerprint,
        grounding_basis=grounding_basis,
        fallback_summary=(
            f"Market intelligence includes {len(topics)} topic(s), {len(signals)} "
            f"market signal(s), and {len(competitors)} competitor(s) "
            f"({'plus stated onboarding data' if stated_fields else 'no stated data'}), "
            "but AI-generated synthesis is currently unavailable. Review these "
            "records directly for market context."
        ),
        context=context,
    )
