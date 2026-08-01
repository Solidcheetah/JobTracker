from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Application
from app.schemas.application import (
    ApplicationCreateSchema,
    ApplicationFilterParams,
    ApplicationReadSchema,
    ApplicationStatsReadSchema,
    ApplicationUpdateSchema,
)
from app.database.models.application_status import ApplicationStatus
from app.database.models.application_status_history import ApplicationStatusHistory


class ApplicationService:
    def __init__(self, session: AsyncSession, user_id: UUID):
        self.session = session
        self.user_id = user_id

    async def get(self, id: UUID) -> ApplicationReadSchema:
        application = await self.session.get(Application, id)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
            )

        if application.owner_id != self.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is forbidden from accessing",
            )
        return application

    async def add(self, payload: ApplicationCreateSchema) -> ApplicationReadSchema:
        new_application = Application(
            **payload.model_dump(),
            owner_id=self.user_id,
        )

        self.session.add(new_application)
        await self.session.flush()
        await self.session.refresh(new_application)

        self._record_status_change(new_application.id, new_application.status)

        return new_application

    def _build_filters(
        self, filters: ApplicationFilterParams | None
    ) -> list:
        conditions = [Application.owner_id == self.user_id]
        if not filters:
            return conditions

        if filters.status:
            conditions.append(Application.status.in_(filters.status))

        if filters.search:
            pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    Application.company.ilike(pattern),
                    Application.role.ilike(pattern),
                )
            )

        if filters.applied_from:
            conditions.append(Application.applied_at >= filters.applied_from)

        if filters.applied_to:
            conditions.append(Application.applied_at <= filters.applied_to)

        return conditions

    async def list_applications(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: ApplicationFilterParams | None = None,
    ) -> tuple[list[Application], int]:
        offset = (page - 1) * page_size
        conditions = self._build_filters(filters)

        total = await self.session.scalar(
            select(func.count(Application.id)).where(*conditions)
        )

        result = await self.session.scalars(
            select(Application)
            .where(*conditions)
            .order_by(
                Application.applied_at.desc(),
                Application.created_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )

        return list(result.all()), total or 0

    async def delete_application(self, application_id: UUID):
        application = await self.get(application_id)
        if self.user_id != application.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is forbidden from accessing",
            )
        await self.session.delete(application)
        return {"detail": f"Application with id #{application_id} deleted successfully!"}

    async def get_by_status(
        self, application_status: ApplicationStatus
    ) -> list[Application]:
        result = await self.session.scalars(
            select(Application)
            .where(
                Application.owner_id == self.user_id,
                Application.status == application_status,
            )
            .order_by(
                Application.applied_at.desc(),
                Application.created_at.desc(),
            )
        )
        return list(result.all())

    async def get_recent_application(self) -> list[Application]:
        result = await self.session.scalars(
            select(Application)
            .where(
                Application.owner_id == self.user_id,
            )
            .order_by(
                Application.applied_at.desc(),
                Application.created_at.desc(),
            )
            .limit(5)
        )
        return list(result.all())

    async def get_application_stats(self) -> ApplicationStatsReadSchema:
        rows = await self.session.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.owner_id == self.user_id)
            .group_by(Application.status)
        )

        status_counts = {status.value: 0 for status in ApplicationStatus}
        for status_value, count in rows:
            status_counts[status_value.value] = count

        total = sum(status_counts.values())
        most_common = (
            max(status_counts, key=status_counts.get) if status_counts else None
        )

        return ApplicationStatsReadSchema(
            total=total,
            most_common_status=most_common,
            status_counts=status_counts,
        )

    def _record_status_change(
        self,
        application_id: UUID,
        application_status: ApplicationStatus,
    ) -> None:
        record = ApplicationStatusHistory(
            application_id=application_id,
            status=application_status,
        )
        self.session.add(record)

    async def update_application(
        self,
        application_id: UUID,
        payload: ApplicationUpdateSchema,
    ) -> ApplicationReadSchema:
        application = await self.get(application_id)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and application.status != value:
                self._record_status_change(application_id, value)
            setattr(application, field, value)

        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def update_status(
        self,
        application_id: UUID,
        application_status: ApplicationStatus,
    ) -> ApplicationReadSchema:
        application = await self.get(application_id)
        if application.status != application_status:
            application.status = application_status
            self._record_status_change(application_id, application_status)

        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def update_note(
        self,
        application_id: UUID,
        note: str | None,
    ) -> ApplicationReadSchema:
        application = await self.get(application_id)
        application.note = note

        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def get_status_history(
        self,
        application_id: UUID,
    ) -> list[ApplicationStatusHistory]:
        result = await self.session.scalars(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.changed_at.desc())
        )
        return list(result.all())
