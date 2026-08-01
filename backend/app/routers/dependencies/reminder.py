from typing import Annotated

from fastapi import Depends

from app.routers.dependencies.auth import CurrentUserDep, ScopedSessionDep
from app.services.reminder import ReminderService


def get_reminder_service(
    session: ScopedSessionDep, user_id: CurrentUserDep
) -> ReminderService:
    return ReminderService(session, user_id)


ReminderServiceDep = Annotated[ReminderService, Depends(get_reminder_service)]
