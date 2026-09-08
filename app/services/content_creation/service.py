import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_brief import BriefStatus, ContentBrief
from app.models.content_draft import (
    CompositionMode,
    ContentDraft,
    DraftGenerationSource,
    DraftStatus,
)
from app.repositories.content_brief import ContentBriefRepository
from app.repositories.content_draft import ContentDraftRepository
from app.repositories.content_profile import ContentProfileRepository
from app.services.ai.router import AIRouter
from app.services.content_creation.creator import ContentCreator
from app.services.content_creation.deterministic import DeterministicContentCreator
from app.services.content_creation.prompts import PROMPT_VERSION

logger = logging.getLogger(__name__)


class ContentCreationService:
    def __init__(self, session: AsyncSession, router: AIRouter | None = None):
        self.session = session
        self.repository = ContentDraftRepository(session)
        self.brief_repository = ContentBriefRepository(session)
        self.profile_repository = ContentProfileRepository(session)
        self.deterministic_creator = DeterministicContentCreator()
        self.content_creator = ContentCreator(router)

    async def create(
        self,
        profile_id: UUID,
        brief_id: UUID,
        workspace_id: UUID,
        **values: Any,
    ) -> ContentDraft:
        await self._verify_profile(profile_id, workspace_id)
        brief = await self.brief_repository.get_by_id(profile_id, brief_id)
        if not brief:
            raise ValueError("Content brief not found")
        if brief.status not in {BriefStatus.READY, BriefStatus.APPROVED}:
            raise ValueError("Content brief is not executable")

        mode = values.get("composition_mode", CompositionMode.COMPOSE)
        if mode == CompositionMode.MANUAL:
            content = self._manual_content(values)
            source = DraftGenerationSource.MANUAL
            ai_metadata: dict[str, str | bool] = {}
        else:
            content = self.deterministic_creator.create(brief)
            source = DraftGenerationSource.DETERMINISTIC
            ai_metadata = {}
            if values.get("use_ai", False):
                try:
                    content, result = await self.content_creator.create(brief)
                    source = DraftGenerationSource.AI
                    ai_metadata = {
                        "provider": result.metadata.provider,
                        "model": result.metadata.model,
                        "prompt_version": PROMPT_VERSION,
                    }
                except Exception:
                    logger.exception("Content creation AI failed; using deterministic fallback")
                    source = DraftGenerationSource.AI_FALLBACK
                    ai_metadata = {"fallback": True, "prompt_version": PROMPT_VERSION}

        draft = ContentDraft(
            profile_id=profile_id,
            brief_id=brief.id,
            platform=brief.recommended_platform,
            format=brief.recommended_format or "text_post",
            title=content.title,
            hook=content.hook,
            body=content.body,
            cta=content.cta,
            status=DraftStatus.DRAFT,
            generation_source=source,
            composition_mode=mode,
            ai_provider=ai_metadata.get("provider"),
            ai_model=ai_metadata.get("model"),
            prompt_version=ai_metadata.get("prompt_version"),
            draft_metadata=self._metadata(brief, source, ai_metadata),
        )
        await self.repository.create(draft)
        await self.session.commit()
        return draft

    async def get(
        self, profile_id: UUID, draft_id: UUID, workspace_id: UUID
    ) -> ContentDraft | None:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.get_by_id(profile_id, draft_id)

    async def list(
        self, profile_id: UUID, workspace_id: UUID, **filters: Any
    ) -> list[ContentDraft]:
        await self._verify_profile(profile_id, workspace_id)
        return await self.repository.list_by_profile(profile_id, **filters)

    async def update(
        self, profile_id: UUID, draft_id: UUID, workspace_id: UUID, **values: Any
    ) -> ContentDraft | None:
        await self._verify_profile(profile_id, workspace_id)
        draft = await self.repository.get_by_id(profile_id, draft_id)
        if not draft:
            return None
        if values.get("status") is not None:
            self._validate_status_transition(draft.status, values["status"])
        for field in ("title", "cta"):
            if field in values:
                setattr(draft, field, values[field])
        for field in ("hook", "body"):
            if field in values:
                if values[field] is None:
                    raise ValueError(f"{field} cannot be empty")
                setattr(draft, field, values[field])
        if values.get("status") is not None:
            draft.status = values["status"]
        await self.repository.update(draft)
        await self.session.commit()
        return draft

    async def delete(self, profile_id: UUID, draft_id: UUID, workspace_id: UUID) -> bool:
        await self._verify_profile(profile_id, workspace_id)
        draft = await self.repository.get_by_id(profile_id, draft_id)
        if not draft:
            return False
        await self.repository.delete(draft)
        await self.session.commit()
        return True

    async def _verify_profile(self, profile_id: UUID, workspace_id: UUID):
        profile = await self.profile_repository.get_by_id(profile_id, workspace_id)
        if not profile:
            raise ValueError("Content profile not found")
        return profile

    @staticmethod
    def _manual_content(values: dict[str, Any]):
        if not values.get("hook") or not values.get("body"):
            raise ValueError("Manual drafts require hook and body")
        from app.schemas.content_draft import ContentCreationLLMResult

        return ContentCreationLLMResult(
            title=values.get("title"),
            hook=values["hook"],
            body=values["body"],
            cta=values.get("cta"),
        )

    @staticmethod
    def _metadata(
        brief: ContentBrief,
        source: DraftGenerationSource,
        ai_metadata: dict[str, str | bool],
    ) -> dict[str, Any]:
        opportunity = brief.opportunity
        signal_id = (
            opportunity.market_signal_id
            or opportunity.audience_signal_id
            or opportunity.performance_insight_id
        )
        metadata: dict[str, Any] = {
            "lineage": {
                "brief_id": str(brief.id),
                "opportunity_id": str(brief.opportunity_id),
                "source_signal_type": opportunity.source_signal.value,
                "source_signal_id": str(signal_id) if signal_id else None,
            },
            "creation": {"method": source.value},
        }
        if ai_metadata:
            metadata["ai"] = ai_metadata
        return metadata

    @staticmethod
    def _validate_status_transition(current: DraftStatus, target: DraftStatus):
        allowed = {
            DraftStatus.DRAFT: {DraftStatus.READY},
            DraftStatus.READY: {DraftStatus.APPROVED},
            DraftStatus.APPROVED: {DraftStatus.ARCHIVED},
            DraftStatus.ARCHIVED: set(),
        }
        if target != current and target not in allowed[current]:
            raise ValueError("Invalid draft status transition")
