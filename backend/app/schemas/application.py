from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.database.models.application_status import ApplicationStatus


class ApplicationCreateSchema(BaseModel):
    company: str
    role: str
    status: ApplicationStatus
    source_url: str | None = Field(default=None)
    note: str | None = Field(default=None, max_length=2000)
    applied_at: date


class ApplicationReadSchema(BaseModel):
    id: UUID
    owner_id: UUID
    company: str
    role: str
    status: ApplicationStatus
    source_url: str | None
    note: str | None
    applied_at: date
    created_at: datetime


class ApplicationUpdateSchema(BaseModel):
    """A partial update: every field is optional.

    The defaults are what make this a PATCH. `update_application` applies it with
    `exclude_unset=True`, so an omitted field is left alone while an explicit
    `null` still clears the column — a distinction that only works if omitting is
    allowed in the first place.
    """

    company: str | None = Field(default=None)
    role: str | None = Field(default=None)
    status: ApplicationStatus | None = Field(default=None)
    source_url: str | None = Field(default=None)
    note: str | None = Field(default=None, max_length=2000)
    applied_at: date | None = Field(default=None)


class ApplicationNoteUpdateSchema(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ApplicationStatusUpdateSchema(BaseModel):
    status: ApplicationStatus


class ApplicationStatusHistoryReadSchema(BaseModel):
    id: UUID
    application_id: UUID
    status: ApplicationStatus
    changed_at: datetime


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ApplicationFilterParams(BaseModel):
    status: list[ApplicationStatus] | None = Field(default=None)
    search: str | None = Field(default=None, max_length=100)
    applied_from: date | None = Field(default=None)
    applied_to: date | None = Field(default=None)


class ApplicationPaginatedReadSchema(BaseModel):
    items: list[ApplicationReadSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class ApplicationStatsReadSchema(BaseModel):
    total: int
    most_common_status: ApplicationStatus | None
    status_counts: dict[str, int]
