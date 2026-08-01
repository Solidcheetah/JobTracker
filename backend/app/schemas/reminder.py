from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.database.models.reminder_status import ReminderStatus


class ReminderCreateSchema(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    remind_at: datetime

    @field_validator("remind_at")
    @classmethod
    def check_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("remind_at must include a timezone offset")
        if value <= datetime.now(timezone.utc):
            raise ValueError("remind_at must be in the future")
        return value


class ReminderUpdateSchema(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=500)
    remind_at: datetime | None = None

    _validate = field_validator("remind_at")(ReminderCreateSchema.check_future.__func__)


class ReminderReadSchema(BaseModel):
    id: UUID
    content: str
    remind_at: datetime
    status: ReminderStatus


class ReminderPaginatedReadSchema(BaseModel):
    items: list[ReminderReadSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReminderFilterParams(BaseModel):
    status: list[ReminderStatus] | None = None
    due_before: datetime | None = None
