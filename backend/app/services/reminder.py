from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Reminder
from app.database.models.reminder_status import ReminderStatus
from app.schemas.reminder import (
    ReminderCreateSchema,
    ReminderFilterParams,
    ReminderUpdateSchema,
)

_MUTABLE_STATUSES = {ReminderStatus.pending}


class ReminderService:
    def __init__(self, session: AsyncSession, user_id: UUID):
        self.session = session
        self.user_id = user_id

    async def get(self, id: UUID) -> Reminder:
        reminder = await self.session.get(Reminder, id)
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
            )

        if reminder.owner_id != self.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is forbidden from accessing",
            )
        return reminder

    async def add(self, payload: ReminderCreateSchema) -> Reminder:
        new_reminder = Reminder(
            **payload.model_dump(),
            owner_id=self.user_id,
        )

        self.session.add(new_reminder)
        await self.session.flush()
        await self.session.refresh(new_reminder)

        return new_reminder

    def _build_filters(self, filters: ReminderFilterParams | None) -> list:
        conditions = [Reminder.owner_id == self.user_id]
        if not filters:
            return conditions

        if filters.status:
            conditions.append(Reminder.status.in_(filters.status))

        if filters.due_before:
            conditions.append(Reminder.remind_at <= filters.due_before)

        return conditions

    async def list_reminders(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: ReminderFilterParams | None = None,
    ) -> tuple[list[Reminder], int]:
        offset = (page - 1) * page_size
        conditions = self._build_filters(filters)

        total = await self.session.scalar(
            select(func.count(Reminder.id)).where(*conditions)
        )

        result = await self.session.scalars(
            select(Reminder)
            .where(*conditions)
            .order_by(Reminder.remind_at.asc(), Reminder.id.asc())
            .offset(offset)
            .limit(page_size)
        )

        return list(result.all()), total or 0

    async def get_upcoming(self, limit: int = 5) -> list[Reminder]:
        result = await self.session.scalars(
            select(Reminder)
            .where(
                Reminder.owner_id == self.user_id,
                Reminder.status == ReminderStatus.pending,
                Reminder.remind_at > datetime.now(timezone.utc),
            )
            .order_by(Reminder.remind_at.asc(), Reminder.id.asc())
            .limit(limit)
        )
        return list(result.all())

    async def update_reminder(
        self,
        reminder_id: UUID,
        payload: ReminderUpdateSchema,
    ) -> Reminder:
        reminder = await self.get(reminder_id)
        self._assert_mutable(reminder)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reminder, field, value)

        await self.session.flush()
        await self.session.refresh(reminder)
        return reminder

    async def cancel(self, reminder_id: UUID) -> Reminder:
        reminder = await self.get(reminder_id)

        if reminder.status is ReminderStatus.cancelled:
            return reminder

        self._assert_mutable(reminder)
        reminder.status = ReminderStatus.cancelled

        await self.session.flush()
        await self.session.refresh(reminder)
        return reminder

    @staticmethod
    def _assert_mutable(reminder: Reminder) -> None:
        if reminder.status not in _MUTABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Reminder is {reminder.status.value} and can no longer be changed",
            )
