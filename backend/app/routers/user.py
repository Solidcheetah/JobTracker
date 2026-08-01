from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from fastapi.security import HTTPAuthorizationCredentials
from app.schemas.user import UserCreateSchema, UserLoginSchema, UserReadSchema
from app.routers.dependencies.user import UserServiceDep
from app.database.redis import add_jti_to_blacklist
from app.utils import decode_access_token
from app.core.security import bearer_scheme


router = APIRouter(prefix="/user", tags=["User"])


@router.post("/register", response_model=UserReadSchema)
async def register_user(user: UserCreateSchema, service: UserServiceDep):
    return await service.add_user(user)


@router.post("/login")
async def login_user(credentials: UserLoginSchema, service: UserServiceDep):
    token = await service.generate_user_token(credentials.email, credentials.password)
    return {"token": token, "type": "jwt"}


@router.post("/logout")
async def logout_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
):
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    await add_jti_to_blacklist(payload["jti"], payload["exp"])
    return {"detail": "logged out"}
