from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import Column
from sqlmodel import SQLModel, Field
from sqlalchemy.dialects import postgresql


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID,
            default=uuid4,
            primary_key=True,
        )
    )
    name: str
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str
