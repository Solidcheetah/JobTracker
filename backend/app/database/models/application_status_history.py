from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects import postgresql
from sqlmodel import Field, SQLModel

from app.database.models.application_status import ApplicationStatus


class ApplicationStatusHistory(SQLModel, table=True):
    __tablename__ = "application_status_history"

    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID,
            default=uuid4,
            primary_key=True,
        )
    )

    application_id: UUID = Field(foreign_key="application.id")
    status: ApplicationStatus
    changed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
