from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session, user_scoped_session
from app.core.security import bearer_scheme
from app.utils import decode_access_token
from app.database.redis import is_jti_blacklisted

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload or "jti" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if await is_jti_blacklisted(payload["jti"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return UUID(payload["sub"])


CurrentUserDep = Annotated[UUID, Depends(get_current_user)]


async def get_db(user_id: CurrentUserDep):
    async with user_scoped_session(user_id) as session:
        yield session


ScopedSessionDep = Annotated[AsyncSession, Depends(get_db)]
