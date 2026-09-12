from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob, JobStatus


class AIJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: AIJob) -> AIJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: UUID) -> AIJob | None:
        result = await self.session.execute(select(AIJob).where(AIJob.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: UUID,
        status: JobStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AIJob]:
        statement = select(AIJob).where(AIJob.profile_id == profile_id)
        if status is not None:
            statement = statement.where(AIJob.status == status)
        result = await self.session.execute(
            statement.order_by(AIJob.submitted_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, job: AIJob) -> AIJob:
        await self.session.flush()
        return job
