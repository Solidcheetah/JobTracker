from typing import Annotated

from fastapi import Depends

from app.routers.dependencies.auth import CurrentUserDep, ScopedSessionDep, SessionDep
from app.services.application import ApplicationService


def get_application_service(
    session: ScopedSessionDep, user_id: CurrentUserDep
) -> ApplicationService:
    return ApplicationService(session, user_id)


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]
