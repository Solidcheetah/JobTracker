from uuid import UUID

from fastapi import HTTPException, status
from pwdlib import PasswordHash
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.schemas.user import UserCreateSchema, UserReadSchema
from app.utils import generate_access_token

password_hasher = PasswordHash.recommended()


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_user(self, payload: UserCreateSchema) -> User:
        new_user = User(
            **payload.model_dump(exclude={"password"}),
            password_hash=password_hasher.hash(payload.password),
        )

        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)

        return new_user

    async def get_user(self, id: UUID) -> User:
        user = await self.session.get(User, id)
        if user:
            return user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with id does not exist",
        )

    async def get_by_email(self, email: str):
        return await self.session.scalar(select(User).where(User.email == email))

    async def generate_user_token(self, email: EmailStr, password: str) -> str:
        user = await self.get_by_email(email)

        if not user or not password_hasher.verify(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or Password is incorrect!",
            )

        token = generate_access_token(data={"sub": str(user.id), "name": user.name})

        return token
