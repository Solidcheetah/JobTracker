"""ApplicationService: creation, retrieval, ownership, updates and deletion."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.database.models import ApplicationStatusHistory
from app.schemas.application import (
    ApplicationCreateSchema,
    ApplicationUpdateSchema,
)


def new_payload(**overrides) -> ApplicationCreateSchema:
    data = {
        "company": "Acme",
        "role": "Engineer",
        "status": "applied",
        "source_url": None,
        "note": None,
        "applied_at": date(2026, 6, 1),
    }
    data.update(overrides)
    return ApplicationCreateSchema(**data)


class TestAdd:
    async def test_creates_an_application_owned_by_the_caller(self, service, user):
        created = await service.add(new_payload())

        assert created.id is not None
        assert created.owner_id == user.id
        assert created.company == "Acme"

    async def test_sets_created_at(self, service):
        created = await service.add(new_payload())

        assert created.created_at is not None

    async def test_records_the_initial_status_in_history(self, service, session):
        created = await service.add(new_payload(status="wishlist"))
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == created.id
                )
            )
        ).all()

        assert len(history) == 1
        assert history[0].status == "wishlist"

    async def test_optional_fields_round_trip(self, service):
        created = await service.add(
            new_payload(source_url="https://jobs.example.com/1", note="Referred")
        )

        assert created.source_url == "https://jobs.example.com/1"
        assert created.note == "Referred"


class TestGet:
    async def test_returns_an_owned_application(self, service, make_application):
        existing = await make_application()

        assert (await service.get(existing.id)).id == existing.id

    async def test_unknown_id_is_404(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.get(uuid4())

        assert exc.value.status_code == 404

    async def test_another_users_application_is_403(
        self, service, make_application, other_user
    ):
        """Ownership is enforced in the service, not only by Postgres RLS."""
        theirs = await make_application(owner=other_user)

        with pytest.raises(HTTPException) as exc:
            await service.get(theirs.id)

        assert exc.value.status_code == 403


class TestListApplications:
    async def test_returns_only_the_callers_applications(
        self, service, make_application, other_user
    ):
        await make_application(company="Mine")
        await make_application(company="Theirs", owner=other_user)

        items, total = await service.list_applications()

        assert total == 1
        assert [a.company for a in items] == ["Mine"]

    async def test_empty_when_the_user_has_none(self, service):
        items, total = await service.list_applications()

        assert items == []
        assert total == 0

    async def test_orders_by_applied_date_descending(self, service, make_application):
        await make_application(company="Older", applied_at=date(2026, 1, 1))
        await make_application(company="Newer", applied_at=date(2026, 6, 1))

        items, _ = await service.list_applications()

        assert [a.company for a in items] == ["Newer", "Older"]


class TestUpdateApplication:
    async def test_updates_the_given_fields(self, service, make_application):
        existing = await make_application(company="Old", role="Old Role")

        updated = await service.update_application(
            existing.id,
            ApplicationUpdateSchema(
                company="New",
                role="New Role",
                status="screen",
                source_url=None,
                note=None,
                applied_at=date(2026, 6, 2),
            ),
        )

        assert updated.company == "New"
        assert updated.role == "New Role"
        assert updated.status == "screen"

    async def test_records_history_when_the_status_changes(
        self, service, make_application, session
    ):
        existing = await make_application(status="applied")

        await service.update_application(
            existing.id,
            ApplicationUpdateSchema(
                company="Acme",
                role="Engineer",
                status="offer",
                source_url=None,
                note=None,
                applied_at=date(2026, 6, 1),
            ),
        )
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == existing.id
                )
            )
        ).all()

        assert [h.status for h in history] == ["offer"]

    async def test_no_history_when_the_status_is_unchanged(
        self, service, make_application, session
    ):
        existing = await make_application(status="applied")

        await service.update_application(
            existing.id,
            ApplicationUpdateSchema(
                company="Renamed",
                role="Engineer",
                status="applied",
                source_url=None,
                note=None,
                applied_at=date(2026, 6, 1),
            ),
        )
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == existing.id
                )
            )
        ).all()

        assert history == []

    async def test_cannot_update_another_users_application(
        self, service, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        with pytest.raises(HTTPException) as exc:
            await service.update_application(
                theirs.id,
                ApplicationUpdateSchema(
                    company="Hijacked",
                    role="R",
                    status="offer",
                    source_url=None,
                    note=None,
                    applied_at=date(2026, 6, 1),
                ),
            )

        assert exc.value.status_code == 403


class TestUpdateStatus:
    async def test_changes_the_status(self, service, make_application):
        existing = await make_application(status="applied")

        updated = await service.update_status(existing.id, "onsite")

        assert updated.status == "onsite"

    async def test_records_one_history_row_per_change(
        self, service, make_application, session
    ):
        existing = await make_application(status="applied")

        await service.update_status(existing.id, "screen")
        await service.update_status(existing.id, "onsite")
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == existing.id
                )
            )
        ).all()

        assert sorted(h.status.value for h in history) == ["onsite", "screen"]

    async def test_setting_the_same_status_records_nothing(
        self, service, make_application, session
    ):
        existing = await make_application(status="applied")

        await service.update_status(existing.id, "applied")
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == existing.id
                )
            )
        ).all()

        assert history == []

    async def test_cannot_change_another_users_status(
        self, service, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        with pytest.raises(HTTPException) as exc:
            await service.update_status(theirs.id, "offer")

        assert exc.value.status_code == 403


class TestUpdateNote:
    async def test_sets_a_note(self, service, make_application):
        existing = await make_application()

        assert (await service.update_note(existing.id, "Follow up")).note == "Follow up"

    async def test_clears_a_note(self, service, make_application):
        existing = await make_application(note="Old note")

        assert (await service.update_note(existing.id, None)).note is None

    async def test_updating_a_note_records_no_status_history(
        self, service, make_application, session
    ):
        existing = await make_application()

        await service.update_note(existing.id, "Just a note")
        await session.commit()

        history = (
            await session.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == existing.id
                )
            )
        ).all()

        assert history == []

    async def test_cannot_note_another_users_application(
        self, service, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        with pytest.raises(HTTPException) as exc:
            await service.update_note(theirs.id, "nosy")

        assert exc.value.status_code == 403


class TestDelete:
    async def test_removes_the_application(self, service, make_application, session):
        existing = await make_application()

        await service.delete_application(existing.id)
        await session.commit()

        items, total = await service.list_applications()
        assert total == 0

    async def test_unknown_id_is_404(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.delete_application(uuid4())

        assert exc.value.status_code == 404

    async def test_cannot_delete_another_users_application(
        self, service, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        with pytest.raises(HTTPException) as exc:
            await service.delete_application(theirs.id)

        assert exc.value.status_code == 403


class TestGetByStatus:
    async def test_returns_only_that_status(self, service, make_application):
        await make_application(company="A", status="applied")
        await make_application(company="B", status="offer")

        result = await service.get_by_status("offer")

        assert [a.company for a in result] == ["B"]

    async def test_scoped_to_the_caller(self, service, make_application, other_user):
        await make_application(company="Theirs", status="offer", owner=other_user)

        assert await service.get_by_status("offer") == []


class TestGetRecent:
    async def test_returns_at_most_five(self, service, make_application):
        for day in range(1, 9):
            await make_application(company=f"C{day}", applied_at=date(2026, 6, day))

        assert len(await service.get_recent_application()) == 5

    async def test_returns_the_most_recent_first(self, service, make_application):
        await make_application(company="Old", applied_at=date(2026, 1, 1))
        await make_application(company="New", applied_at=date(2026, 6, 1))

        result = await service.get_recent_application()

        assert [a.company for a in result] == ["New", "Old"]

    async def test_scoped_to_the_caller(self, service, make_application, other_user):
        await make_application(owner=other_user)

        assert await service.get_recent_application() == []
