from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.routers.dependencies.reminder import ReminderServiceDep
from app.schemas.application import PaginationParams
from app.schemas.reminder import (
    ReminderCreateSchema,
    ReminderFilterParams,
    ReminderPaginatedReadSchema,
    ReminderReadSchema,
    ReminderUpdateSchema,
)

router = APIRouter(prefix="/reminder", tags=["Reminder"])


@router.post("/", response_model=ReminderReadSchema)
async def create_reminder(payload: ReminderCreateSchema, service: ReminderServiceDep):
    return await service.add(payload)


@router.get("/", response_model=ReminderReadSchema)
async def get_reminder(id: UUID, service: ReminderServiceDep):
    return await service.get(id)


@router.get("/all", response_model=ReminderPaginatedReadSchema)
async def get_all_reminders(
    pagination: Annotated[PaginationParams, Depends()],
    filters: Annotated[ReminderFilterParams, Query()],
    service: ReminderServiceDep,
):
    items, total = await service.list_reminders(
        page=pagination.page,
        page_size=pagination.page_size,
        filters=filters,
    )
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total_pages": (total + pagination.page_size - 1) // pagination.page_size,
    }


@router.get("/upcoming", response_model=list[ReminderReadSchema])
async def get_upcoming_reminders(
    service: ReminderServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
):
    return await service.get_upcoming(limit)


@router.patch("/", response_model=ReminderReadSchema)
async def update_reminder(
    id: UUID,
    payload: ReminderUpdateSchema,
    service: ReminderServiceDep,
):
    return await service.update_reminder(id, payload)


# Soft delete: the row survives as `cancelled`. A hard delete would strand any
# message the scanner has already published, leaving a consumer to look up a row
# that no longer exists.
@router.delete("/", response_model=ReminderReadSchema)
async def cancel_reminder(id: UUID, service: ReminderServiceDep):
    return await service.cancel(id)
