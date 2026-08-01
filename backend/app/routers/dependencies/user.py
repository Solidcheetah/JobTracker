from typing import Annotated

from fastapi import Depends


from app.services.user import UserService
from app.routers.dependencies.auth import SessionDep


def get_user_service(session: SessionDep):
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
