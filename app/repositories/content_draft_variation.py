from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_draft_variation import ContentDraftVariation, VariationType


class ContentDraftVariationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, variation: ContentDraftVariation) -> ContentDraftVariation:
        self.session.add(variation)
        await self.session.flush()
        return variation

    async def get_by_id(self, draft_id: UUID, variation_id: UUID) -> ContentDraftVariation | None:
        result = await self.session.execute(
            select(ContentDraftVariation).where(
                ContentDraftVariation.id == variation_id,
                ContentDraftVariation.draft_id == draft_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_draft(
        self, draft_id: UUID, variation_type: VariationType | None = None
    ) -> list[ContentDraftVariation]:
        statement = select(ContentDraftVariation).where(ContentDraftVariation.draft_id == draft_id)
        if variation_type is not None:
            statement = statement.where(ContentDraftVariation.variation_type == variation_type)
        result = await self.session.execute(
            statement.order_by(
                ContentDraftVariation.variation_type, ContentDraftVariation.variation_index
            )
        )
        return list(result.scalars().all())

    async def max_index(self, draft_id: UUID, variation_type: VariationType) -> int:
        variations = await self.list_by_draft(draft_id, variation_type)
        return max((v.variation_index for v in variations), default=0)

    async def get_selected(
        self, draft_id: UUID, variation_type: VariationType
    ) -> ContentDraftVariation | None:
        result = await self.session.execute(
            select(ContentDraftVariation).where(
                ContentDraftVariation.draft_id == draft_id,
                ContentDraftVariation.variation_type == variation_type,
                ContentDraftVariation.is_selected.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, variation: ContentDraftVariation) -> ContentDraftVariation:
        await self.session.flush()
        return variation
