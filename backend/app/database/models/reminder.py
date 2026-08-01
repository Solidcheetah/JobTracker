from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects import postgresql
from sqlmodel import Field, SQLModel

from app.database.models.reminder_status import ReminderStatus


class Reminder(SQLModel, table=True):
    __tablename__ = "reminder"

    id: UUID = Field(sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True))

    # Spelled out rather than Field(foreign_key=...) because that shorthand
    # cannot express ON DELETE, and a DB-side cascade the model does not declare
    # is something autogenerate keeps proposing to drop.
    owner_id: UUID = Field(
        sa_column=Column(
            Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    content: str = Field(sa_column=Column(String(500), nullable=False))

    remind_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    status: ReminderStatus = Field(default=ReminderStatus.pending)

    attempt_count: int = Field(
        sa_column=Column(Integer, nullable=False, server_default="0")
    )
    claimed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
