from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.database.models.application_status import ApplicationStatus
from app.routers.dependencies.application import ApplicationServiceDep
from app.schemas.application import (
    ApplicationCreateSchema,
    ApplicationFilterParams,
    ApplicationNoteUpdateSchema,
    ApplicationPaginatedReadSchema,
    ApplicationReadSchema,
    ApplicationStatsReadSchema,
    ApplicationStatusHistoryReadSchema,
    ApplicationStatusUpdateSchema,
    ApplicationUpdateSchema,
    PaginationParams,
)

router = APIRouter(prefix="/application", tags=["Application"])


@router.post("/", response_model=ApplicationReadSchema)
async def create_application(
    payload: ApplicationCreateSchema, service: ApplicationServiceDep
):
    return await service.add(payload)


@router.get("/", response_model=ApplicationReadSchema)
async def get_application(id: UUID, service: ApplicationServiceDep):
    return await service.get(id)


@router.get("/all", response_model=ApplicationPaginatedReadSchema)
async def get_all_application(
    pagination: Annotated[PaginationParams, Depends()],
    filters: Annotated[ApplicationFilterParams, Query()],
    service: ApplicationServiceDep,
):
    items, total = await service.list_applications(
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


@router.get("/stats", response_model=ApplicationStatsReadSchema)
async def get_application_stats(service: ApplicationServiceDep):
    return await service.get_application_stats()


@router.delete("/")
async def delete_application(application_id: UUID, service: ApplicationServiceDep):
    return await service.delete_application(application_id)


@router.get("/status")
async def get_applications_by_status(
    application_status: ApplicationStatus, service: ApplicationServiceDep
):
    return await service.get_by_status(application_status)


@router.get("/recent")
async def get_recent_application(
    service: ApplicationServiceDep,
):
    return await service.get_recent_application()


@router.patch("/", response_model=ApplicationReadSchema)
async def update_application(
    id: UUID,
    payload: ApplicationUpdateSchema,
    service: ApplicationServiceDep,
):
    return await service.update_application(id, payload)


@router.patch("/status", response_model=ApplicationReadSchema)
async def update_application_status(
    id: UUID,
    payload: ApplicationStatusUpdateSchema,
    service: ApplicationServiceDep,
):
    return await service.update_status(id, payload.status)


@router.patch("/note", response_model=ApplicationReadSchema)
async def update_application_note(
    id: UUID,
    payload: ApplicationNoteUpdateSchema,
    service: ApplicationServiceDep,
):
    return await service.update_note(id, payload.note)


@router.get(
    "/history",
    response_model=list[ApplicationStatusHistoryReadSchema],
)
async def get_application_status_history(
    id: UUID,
    service: ApplicationServiceDep,
):
    return await service.get_status_history(id)
