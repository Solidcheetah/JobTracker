from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel
from sqlalchemy.dialects import postgresql

from app.database.models.application_status import ApplicationStatus


class Application(SQLModel, table=True):
    __tablename__ = "application"

    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID,
            default=uuid4,
            primary_key=True,
        )
    )

    owner_id: UUID = Field(foreign_key="user.id")

    company: str
    role: str
    status: ApplicationStatus
    source_url: str | None = Field(default=None)
    note: str | None = Field(
        default=None, sa_column=Column(String(2000), nullable=True)
    )
    applied_at: date
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
