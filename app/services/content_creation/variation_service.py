import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_draft import ContentDraft
from app.models.content_draft_variation import (
    ContentDraftVariation,
    VariationGenerationSource,
    VariationType,
)
from app.repositories.content_brief import ContentBriefRepository
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_draft_variation import ContentDraftVariationRepository
from app.repositories.content_profile import ContentProfileRepository
from app.services.content_creation.variation_deterministic import DeterministicVariationGenerator
from app.services.content_creation.variation_generator import ContentDraftVariationGenerator
from app.services.content_creation.variation_prompts import (
    CAPTION_PROMPT_VERSION,
    HOOK_PROMPT_VERSION,
)
from app.services.content_library import invalidate_library_cache

logger = logging.getLogger(__name__)

_PROMPT_VERSION_BY_TYPE = {
    VariationType.HOOK: HOOK_PROMPT_VERSION,
    VariationType.CAPTION: CAPTION_PROMPT_VERSION,
}


class ContentDraftVariationService:
    def __init__(
        self,
        session: AsyncSession,
        generator: ContentDraftVariationGenerator | None = None,
    ):
        self.session = session
        self.repository = ContentDraftVariationRepository(session)
        self.draft_repository = ContentDraftRepository(session)
        self.brief_repository = ContentBriefRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.ai_generator = generator or ContentDraftVariationGenerator()
        self.deterministic_generator = DeterministicVariationGenerator()

    async def generate(
        self,
        profile_id: UUID,
        draft_id: UUID,
        workspace_id: UUID,
        variation_type: VariationType,
        count: int,
        use_ai: bool,
    ) -> list[ContentDraftVariation]:
        draft = await self._load_draft(profile_id, draft_id, workspace_id)
        brief = await self.brief_repository.get_by_id(profile_id, draft.brief_id)
        if not brief:
            raise ValueError("Content brief not found")

        ai_items: list = []
        ai_metadata: dict[str, str] = {}
        if use_ai:
            try:
                result, ai_result = await self.ai_generator.generate(
                    variation_type, count, brief, draft
                )
                ai_items = self._validate_ai_items(result.variations)
                if ai_items:
                    ai_metadata = {
                        "provider": ai_result.metadata.provider,
                        "model": ai_result.metadata.model,
                    }
            except Exception:
                logger.exception("Variation generation AI failed; using deterministic fallback")

        # (item, is_ai) pairs: AI items first, deterministic fallback fills any shortfall
        pairs = [(item, True) for item in ai_items[:count]]
        shortfall = count - len(pairs)
        if shortfall > 0:
            deterministic_items = self.deterministic_generator.generate(
                variation_type, shortfall, brief, draft
            )
            pairs += [(item, False) for item in deterministic_items[:shortfall]]

        start_index = await self.repository.max_index(draft_id, variation_type) + 1
        prompt_version = _PROMPT_VERSION_BY_TYPE[variation_type]

        created: list[ContentDraftVariation] = []
        for offset, (item, is_ai) in enumerate(pairs):
            variation = ContentDraftVariation(
                draft_id=draft_id,
                variation_type=variation_type,
                variation_index=start_index + offset,
                content=item.content,
                rationale=item.rationale,
                generation_source=(
                    VariationGenerationSource.AI
                    if is_ai
                    else VariationGenerationSource.DETERMINISTIC
                ),
                ai_provider=ai_metadata.get("provider") if is_ai else None,
                ai_model=ai_metadata.get("model") if is_ai else None,
                prompt_version=prompt_version if is_ai else None,
            )
            created.append(variation)

        try:
            for variation in created:
                await self.repository.create(variation)
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ValueError("Concurrent variation generation conflict; please retry") from error
        return created

    async def list(
        self,
        profile_id: UUID,
        draft_id: UUID,
        workspace_id: UUID,
        variation_type: VariationType | None = None,
    ) -> list[ContentDraftVariation]:
        await self._load_draft(profile_id, draft_id, workspace_id)
        return await self.repository.list_by_draft(draft_id, variation_type)

    async def select(
        self,
        profile_id: UUID,
        draft_id: UUID,
        variation_id: UUID,
        workspace_id: UUID,
        is_selected: bool,
    ) -> ContentDraftVariation:
        draft = await self._load_draft(profile_id, draft_id, workspace_id)
        variation = await self.repository.get_by_id(draft_id, variation_id)
        if not variation:
            raise ValueError("Content draft variation not found")
        if not is_selected:
            raise ValueError("Variations can only be selected, not unselected directly")

        existing = await self.repository.get_selected(draft_id, variation.variation_type)
        if existing and existing.id != variation.id:
            existing.is_selected = False
            await self.repository.update(existing)

        variation.is_selected = True
        await self.repository.update(variation)
        self._synchronize_draft(draft, variation)
        await self.draft_repository.update(draft)
        await self.session.commit()
        await invalidate_library_cache(workspace_id)
        return variation

    async def _load_draft(
        self, profile_id: UUID, draft_id: UUID, workspace_id: UUID
    ) -> ContentDraft:
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        draft = await self.draft_repository.get_by_id(profile_id, draft_id)
        if not draft:
            raise ValueError("Content draft not found")
        return draft

    @staticmethod
    def _validate_ai_items(items: list) -> list:
        valid = []
        for item in items:
            if item.content and item.content.strip() and item.rationale and item.rationale.strip():
                valid.append(item)
        return valid

    @staticmethod
    def _synchronize_draft(draft: ContentDraft, variation: ContentDraftVariation) -> None:
        if variation.variation_type == VariationType.HOOK:
            draft.hook = variation.content
        elif variation.variation_type == VariationType.CAPTION:
            draft.caption = variation.content
