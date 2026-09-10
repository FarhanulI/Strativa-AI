from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_evaluation import ContentEvaluation
from app.models.content_evaluation_finding import ContentEvaluationFinding


class ContentEvaluationRepository:
    """Repository for content evaluation persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_evaluation(
        self,
        profile_id: UUID,
        draft_id: UUID,
        variation_id: UUID | None,
        scores: dict[str, float],
        overall_score: float,
        classification: str,
        generation_source: str,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        prompt_version: str | None = None,
        metadata: dict | None = None,
    ) -> ContentEvaluation:
        """
        Create a new content evaluation.

        Args:
            profile_id: Profile being evaluated
            draft_id: Draft being evaluated
            variation_id: Optional variation being evaluated
            scores: Dictionary of dimension scores
            overall_score: Calculated overall score
            classification: Calculated classification
            generation_source: How evaluation was generated (deterministic/ai/ai_fallback)
            ai_provider: Provider used if AI-generated
            ai_model: Model used if AI-generated
            prompt_version: Prompt version used if AI-generated
            metadata: Additional metadata

        Returns:
            Created ContentEvaluation
        """
        evaluation = ContentEvaluation(
            profile_id=profile_id,
            draft_id=draft_id,
            variation_id=variation_id,
            strategic_alignment_score=scores.get("strategic_alignment_score", 0.0),
            audience_relevance_score=scores.get("audience_relevance_score", 0.0),
            hook_strength_score=scores.get("hook_strength_score", 0.0),
            message_clarity_score=scores.get("message_clarity_score", 0.0),
            narrative_coherence_score=scores.get("narrative_coherence_score", 0.0),
            format_alignment_score=scores.get("format_alignment_score", 0.0),
            emotional_alignment_score=scores.get("emotional_alignment_score", 0.0),
            cta_alignment_score=scores.get("cta_alignment_score", 0.0),
            brand_alignment_score=scores.get("brand_alignment_score", 0.0),
            overall_score=overall_score,
            classification=classification,
            generation_source=generation_source,
            ai_provider=ai_provider,
            ai_model=ai_model,
            prompt_version=prompt_version,
            evaluation_metadata=metadata,
        )
        self.session.add(evaluation)
        await self.session.flush()
        return evaluation

    async def create_findings(
        self, evaluation_id: UUID, findings: list[dict]
    ) -> list[ContentEvaluationFinding]:
        """
        Create findings for an evaluation.

        Args:
            evaluation_id: Evaluation to add findings to
            findings: List of finding dictionaries with dimension, severity, summary, explanation, recommendation

        Returns:
            List of created ContentEvaluationFinding objects
        """
        finding_objs = [
            ContentEvaluationFinding(
                evaluation_id=evaluation_id,
                dimension=finding["dimension"],
                severity=finding["severity"],
                summary=finding["summary"],
                explanation=finding["explanation"],
                recommendation=finding["recommendation"],
            )
            for finding in findings
        ]
        self.session.add_all(finding_objs)
        await self.session.flush()
        return finding_objs

    async def get_evaluation(
        self, evaluation_id: UUID, profile_id: UUID
    ) -> ContentEvaluation | None:
        """
        Get a single evaluation by ID, verifying profile ownership.

        Args:
            evaluation_id: Evaluation to retrieve
            profile_id: Profile that should own the evaluation

        Returns:
            ContentEvaluation or None if not found or ownership mismatch
        """
        result = await self.session.execute(
            select(ContentEvaluation).where(
                ContentEvaluation.id == evaluation_id,
                ContentEvaluation.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_evaluations_for_draft(
        self,
        profile_id: UUID,
        draft_id: UUID,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ContentEvaluation], int]:
        """
        List evaluations for a specific draft with pagination.

        Args:
            profile_id: Profile that should own the draft
            draft_id: Draft to list evaluations for
            sort_by: Field to sort by
            sort_order: Sort direction (asc/desc)
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            Tuple of (list of evaluations, total count)
        """
        # Get total count
        count_result = await self.session.execute(
            select(ContentEvaluation).where(
                ContentEvaluation.profile_id == profile_id,
                ContentEvaluation.draft_id == draft_id,
            )
        )
        total = len(list(count_result.scalars().all()))

        # Build sort order
        sort_column = getattr(ContentEvaluation, sort_by, ContentEvaluation.created_at)
        if sort_order.lower() == "asc":
            order_by = sort_column.asc()
        else:
            order_by = desc(sort_column)

        # Get paginated results
        result = await self.session.execute(
            select(ContentEvaluation)
            .where(
                ContentEvaluation.profile_id == profile_id,
                ContentEvaluation.draft_id == draft_id,
            )
            .order_by(order_by)
            .offset(skip)
            .limit(limit)
        )
        evaluations = list(result.scalars().all())
        return evaluations, total

    async def count_by_draft(self, profile_id: UUID, draft_id: UUID) -> int:
        """Count evaluations for a draft."""
        result = await self.session.execute(
            select(ContentEvaluation).where(
                ContentEvaluation.profile_id == profile_id,
                ContentEvaluation.draft_id == draft_id,
            )
        )
        return len(list(result.scalars().all()))
