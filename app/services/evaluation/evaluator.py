"""
Content evaluation service.

Orchestrates evaluation of content drafts against their strategic briefs.
Supports both deterministic and AI-powered evaluation with fallback behavior.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_brief import ContentBrief
from app.models.content_draft import ContentDraft
from app.models.content_draft_variation import ContentDraftVariation
from app.models.content_evaluation import ContentEvaluation, EvaluationDimension
from app.models.content_profile import ContentProfile
from app.repositories.content_brief import ContentBriefRepository
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_draft_variation import ContentDraftVariationRepository
from app.repositories.content_evaluation import ContentEvaluationRepository
from app.repositories.content_profile import ContentProfileRepository
from app.schemas.content_evaluation import (
    ContentEvaluationLLMResult,
    ContentEvaluationResponse,
    EvaluationFindingResult,
    ScoreResult,
)
from app.services.ai.router import AIRouter
from app.services.ai.tasks.types import AITask
from app.services.evaluation.scoring import calculate_overall_score, classify_score


class ContentEvaluationService:
    """Service for evaluating content drafts against their briefs."""

    def __init__(
        self,
        session: AsyncSession,
        profile_repository: ContentProfileRepository,
        draft_repository: ContentDraftRepository,
        brief_repository: ContentBriefRepository,
        variation_repository: ContentDraftVariationRepository,
        evaluation_repository: ContentEvaluationRepository,
        ai_router: AIRouter | None = None,
    ):
        self.session = session
        self.profile_repository = profile_repository
        self.draft_repository = draft_repository
        self.brief_repository = brief_repository
        self.variation_repository = variation_repository
        self.evaluation_repository = evaluation_repository
        self.ai_router = ai_router or AIRouter()

    async def evaluate_draft(
        self,
        profile_id: UUID,
        workspace_id: UUID,
        draft_id: UUID,
        variation_id: UUID | None = None,
        use_ai: bool = True,
    ) -> ContentEvaluationResponse:
        """
        Evaluate a content draft against its brief.

        Two-stage evaluation:
        - Stage A: Deterministic evaluation (always succeeds)
        - Stage B: Optional AI enrichment (falls back to Stage A if unavailable)

        Args:
            profile_id: Profile that owns the draft
            workspace_id: Workspace containing the profile
            draft_id: Draft to evaluate
            variation_id: Optional specific variation to evaluate
            use_ai: Whether to attempt AI enrichment

        Returns:
            ContentEvaluationResponse with scores, classification, and findings

        Raises:
            ValueError: If profile, draft, brief not found or ownership mismatch
        """
        # Verify profile ownership
        profile = await self._verify_profile(profile_id, workspace_id)

        # Load draft and verify it belongs to profile
        draft = await self.draft_repository.get_by_id(profile_id, draft_id)
        if not draft:
            raise ValueError("Content draft not found")

        # Load brief and verify it corresponds to draft
        brief = await self.brief_repository.get_by_id(profile_id, draft.brief_id)
        if not brief:
            raise ValueError("Content brief not found")

        # Load variation if specified, verify it belongs to draft
        variation = None
        if variation_id:
            variation = await self.variation_repository.get_by_id(draft_id, variation_id)
            if not variation:
                raise ValueError("Content draft variation not found or does not belong to draft")

        # Stage A: Deterministic evaluation
        scores = self._evaluate_deterministically(profile, draft, brief, variation)
        overall_score = calculate_overall_score(scores)
        classification = classify_score(overall_score)
        findings = self._generate_deterministic_findings()
        generation_source = "deterministic"
        ai_provider = None
        ai_model = None
        prompt_version = None

        # Stage B: Optional AI enrichment
        if use_ai:
            try:
                ai_result = await self._enrich_with_ai(profile, draft, brief, variation)
                scores = self._extract_scores_from_ai(ai_result)
                overall_score = calculate_overall_score(scores)
                classification = classify_score(overall_score)
                findings = self._convert_ai_findings(ai_result.findings)
                generation_source = "ai"
                ai_provider = "gemini"  # Would be dynamic from AIResult metadata
                ai_model = "gemini-2.0-flash"  # Would be dynamic from AIResult metadata
                prompt_version = "content_evaluation_v1"
            except Exception as e:
                # Fallback: use deterministic evaluation as base
                generation_source = "ai_fallback"

        # Persist evaluation and findings
        evaluation = await self.evaluation_repository.create_evaluation(
            profile_id=profile_id,
            draft_id=draft_id,
            variation_id=variation_id,
            scores=scores,
            overall_score=overall_score,
            classification=classification,
            generation_source=generation_source,
            ai_provider=ai_provider,
            ai_model=ai_model,
            prompt_version=prompt_version,
            metadata=None,
        )

        # Create findings
        finding_dicts = [
            {
                "dimension": finding["dimension"],
                "severity": finding["severity"],
                "summary": finding["summary"],
                "explanation": finding["explanation"],
                "recommendation": finding["recommendation"],
            }
            for finding in findings
        ]
        await self.evaluation_repository.create_findings(evaluation.id, finding_dicts)

        # Reload evaluation with findings via repository (ensures relationships are loaded)
        reloaded_evaluation = await self.evaluation_repository.get_evaluation(
            evaluation.id, profile_id
        )
        if not reloaded_evaluation:
            raise ValueError("Failed to reload created evaluation")

        return ContentEvaluationResponse.model_validate(reloaded_evaluation)

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID) -> ContentProfile:
        """Verify profile ownership by workspace."""
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    def _evaluate_deterministically(
        self,
        profile: ContentProfile,
        draft: ContentDraft,
        brief: ContentBrief,
        variation: ContentDraftVariation | None,
    ) -> dict[str, float]:
        """
        Perform deterministic evaluation using heuristics.

        Conservative scoring: basic presence checks and structural validation.
        """
        scores = {}

        # Strategic alignment: brief and draft both exist and correspond
        scores["strategic_alignment_score"] = 0.7 if (brief and draft) else 0.4

        # Audience relevance: brief has target audience/persona
        has_audience = bool(
            getattr(brief, "target_persona_id", None)
            or getattr(brief, "target_audience_question_id", None)
        )
        scores["audience_relevance_score"] = 0.6 if has_audience else 0.3

        # Hook strength: variation or draft has hook
        hook_exists = False
        if variation and getattr(variation, "type", None) == "hook":
            hook_exists = bool(getattr(variation, "content", None))
        elif hasattr(draft, "hook"):
            hook_exists = bool(getattr(draft, "hook", None))
        scores["hook_strength_score"] = 0.6 if hook_exists else 0.3

        # Message clarity: brief has core message and draft has body
        has_message = bool(
            getattr(brief, "core_message", None) and getattr(draft, "body", None)
        )
        scores["message_clarity_score"] = 0.6 if has_message else 0.3

        # Narrative coherence: draft body is present and non-empty
        has_body = bool(getattr(draft, "body", None))
        scores["narrative_coherence_score"] = 0.5 if has_body else 0.2

        # Format alignment: brief format matches draft format
        brief_format = getattr(brief, "recommended_format", None)
        draft_format = getattr(draft, "format", None)
        format_match = brief_format == draft_format if brief_format else False
        scores["format_alignment_score"] = 0.6 if format_match else 0.3

        # Emotional alignment: brief has target emotion
        has_tone = bool(getattr(brief, "tone", None))
        scores["emotional_alignment_score"] = 0.6 if has_tone else 0.3

        # CTA alignment: brief has CTA strategy
        has_cta = bool(getattr(brief, "cta_strategy", None))
        scores["cta_alignment_score"] = 0.6 if has_cta else 0.3

        # Brand alignment: profile exists (basic check)
        # Don't access brand_intelligence as it might not be loaded
        scores["brand_alignment_score"] = 0.6 if profile else 0.3

        return scores

    def _generate_deterministic_findings(self) -> list[dict]:
        """Generate basic findings for deterministic evaluation."""
        return [
            {
                "dimension": EvaluationDimension.STRATEGIC_ALIGNMENT,
                "severity": "positive",
                "summary": "Content is aligned with brief",
                "explanation": "Deterministic evaluation confirmed draft corresponds to brief",
                "recommendation": "Continue to content refinement",
            }
        ]

    async def _enrich_with_ai(
        self,
        profile: ContentProfile,
        draft: ContentDraft,
        brief: ContentBrief,
        variation: ContentDraftVariation | None,
    ) -> ContentEvaluationLLMResult:
        """
        Enrich evaluation with AI analysis.

        Constructs focused context and calls AIRouter for structured evaluation.
        """
        # Build focused evaluation context
        context = {
            "strategic_context": {
                "objective": brief.target_objective if hasattr(brief, "target_objective") else None,
                "topic": brief.title or "",
                "strategic_angle": brief.angle or "",
                "key_message": brief.core_message or "",
                "target_emotion": brief.tone or "",
                "format": brief.recommended_format or draft.format,
                "platform": brief.recommended_platform or draft.platform,
                "cta_strategy": brief.cta_strategy or "",
            },
            "creative_content": {
                "title": draft.title or "",
                "hook": draft.hook or "",
                "body": draft.body or "",
                "cta": draft.cta or "",
                "caption": draft.caption or "",
            },
            "brand_context": {
                "positioning": profile.brand_intelligence.positioning if profile.brand_intelligence else "",
                "voice": profile.brand_intelligence.voice if profile.brand_intelligence else "",
                "tone": brief.voice_guidelines or "",
            },
        }

        # Add variation if provided
        if variation:
            context["selected_variation"] = {
                "type": variation.type,
                "content": variation.content,
            }

        # Call AI Router for structured evaluation
        result = await self.ai_router.generate_structured(
            AITask.CONTENT_EVALUATION,
            context,
            response_model=ContentEvaluationLLMResult,
        )

        return result.output

    def _extract_scores_from_ai(self, ai_result: ContentEvaluationLLMResult) -> dict[str, float]:
        """Extract and validate dimension scores from AI result."""
        scores = {
            "strategic_alignment_score": ai_result.strategic_alignment.score,
            "audience_relevance_score": ai_result.audience_relevance.score,
            "hook_strength_score": ai_result.hook_strength.score,
            "message_clarity_score": ai_result.message_clarity.score,
            "narrative_coherence_score": ai_result.narrative_coherence.score,
            "format_alignment_score": ai_result.format_alignment.score,
            "emotional_alignment_score": ai_result.emotional_alignment.score,
            "cta_alignment_score": ai_result.cta_alignment.score,
            "brand_alignment_score": ai_result.brand_alignment.score,
        }

        # Validate all scores are in range
        for dimension, score in scores.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(
                    f"Invalid score from AI for {dimension}: {score}. Must be 0.0-1.0"
                )

        return scores

    def _convert_ai_findings(
        self, ai_findings: list[EvaluationFindingResult]
    ) -> list[dict]:
        """Convert AI findings to internal finding format."""
        return [
            {
                "dimension": finding.dimension,
                "severity": finding.severity,
                "summary": finding.summary,
                "explanation": finding.explanation,
                "recommendation": finding.recommendation,
            }
            for finding in ai_findings
        ]
