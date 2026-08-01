"""/application endpoints."""

from datetime import date
from uuid import uuid4

import pytest


def create_body(**overrides) -> dict:
    body = {
        "company": "Acme",
        "role": "Engineer",
        "status": "applied",
        "source_url": None,
        "note": None,
        "applied_at": "2026-06-01",
    }
    body.update(overrides)
    return body


class TestCreate:
    async def test_creates_and_returns_the_application(self, client, user):
        response = await client.post("/application/", json=create_body())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["company"] == "Acme"
        assert body["owner_id"] == str(user.id)
        assert body["id"]

    async def test_owner_comes_from_the_token_not_the_payload(self, client, user):
        """A client must not be able to create rows owned by someone else."""
        response = await client.post(
            "/application/", json=create_body(owner_id=str(uuid4()))
        )

        assert response.status_code == 200, response.text
        assert response.json()["owner_id"] == str(user.id)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"status": "not-a-status"},
            {"applied_at": "not-a-date"},
            {"company": None},
            {"note": "x" * 2001},
        ],
        ids=["bad-status", "bad-date", "null-company", "note-too-long"],
    )
    async def test_rejects_invalid_payloads(self, client, overrides):
        response = await client.post("/application/", json=create_body(**overrides))

        assert response.status_code == 422

    async def test_requires_the_required_fields(self, client):
        response = await client.post("/application/", json={"company": "Acme"})

        assert response.status_code == 422


class TestRead:
    async def test_returns_an_owned_application(self, client, make_application):
        existing = await make_application()

        response = await client.get("/application/", params={"id": str(existing.id)})

        assert response.status_code == 200, response.text
        assert response.json()["id"] == str(existing.id)

    async def test_unknown_id_is_404(self, client):
        response = await client.get("/application/", params={"id": str(uuid4())})

        assert response.status_code == 404

    async def test_another_users_application_is_403(
        self, client, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        response = await client.get("/application/", params={"id": str(theirs.id)})

        assert response.status_code == 403

    async def test_a_malformed_id_is_422(self, client):
        response = await client.get("/application/", params={"id": "not-a-uuid"})

        assert response.status_code == 422


class TestList:
    async def test_returns_the_paginated_envelope(self, client, make_application):
        await make_application()

        response = await client.get("/application/all")

        assert response.status_code == 200, response.text
        assert set(response.json()) == {
            "items",
            "total",
            "page",
            "page_size",
            "total_pages",
        }

    async def test_excludes_other_users_applications(
        self, client, make_application, other_user
    ):
        await make_application(company="Mine")
        await make_application(company="Theirs", owner=other_user)

        response = await client.get("/application/all")

        assert response.status_code == 200, response.text
        assert [i["company"] for i in response.json()["items"]] == ["Mine"]


class TestUpdateStatusEndpoint:
    async def test_updates_the_status(self, client, make_application):
        existing = await make_application(status="applied")

        response = await client.patch(
            "/application/status",
            params={"id": str(existing.id)},
            json={"status": "onsite"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "onsite"

    async def test_rejects_an_invalid_status(self, client, make_application):
        existing = await make_application()

        response = await client.patch(
            "/application/status",
            params={"id": str(existing.id)},
            json={"status": "nonsense"},
        )

        assert response.status_code == 422

    async def test_cannot_update_another_users_application(
        self, client, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        response = await client.patch(
            "/application/status",
            params={"id": str(theirs.id)},
            json={"status": "offer"},
        )

        assert response.status_code == 403


class TestUpdateNoteEndpoint:
    async def test_sets_a_note(self, client, make_application):
        existing = await make_application()

        response = await client.patch(
            "/application/note",
            params={"id": str(existing.id)},
            json={"note": "Follow up next week"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["note"] == "Follow up next week"

    async def test_clears_a_note(self, client, make_application):
        existing = await make_application(note="Old")

        response = await client.patch(
            "/application/note", params={"id": str(existing.id)}, json={"note": None}
        )

        assert response.status_code == 200, response.text
        assert response.json()["note"] is None

    async def test_rejects_an_overlong_note(self, client, make_application):
        existing = await make_application()

        response = await client.patch(
            "/application/note",
            params={"id": str(existing.id)},
            json={"note": "x" * 2001},
        )

        assert response.status_code == 422

    async def test_cannot_note_another_users_application(
        self, client, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        response = await client.patch(
            "/application/note", params={"id": str(theirs.id)}, json={"note": "nosy"}
        )

        assert response.status_code == 403


class TestUpdateEndpoint:
    async def test_full_update_succeeds(self, client, make_application):
        existing = await make_application(company="Old")

        response = await client.patch(
            "/application/",
            params={"id": str(existing.id)},
            json=create_body(company="New", status="screen"),
        )

        assert response.status_code == 200, response.text
        assert response.json()["company"] == "New"

    async def test_partial_update_changes_only_what_was_sent(
        self, client, make_application
    ):
        """A PATCH with one field leaves the others alone.

        This is the dashboard table's edit control, which sends just status and
        note. It used to 422: the schema's fields were ``T | None`` with no
        default, which Pydantic v2 reads as required-but-nullable.
        """
        existing = await make_application(company="Original", note="keep me")

        response = await client.patch(
            "/application/",
            params={"id": str(existing.id)},
            json={"status": "offer"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "offer"
        assert body["company"] == "Original"
        assert body["note"] == "keep me"

    async def test_explicit_null_clears_a_field(self, client, make_application):
        """Sending ``null`` is different from omitting the field.

        `exclude_unset=True` is what draws the distinction — omitted means "leave
        it", null means "clear it".
        """
        existing = await make_application(note="delete me")

        response = await client.patch(
            "/application/",
            params={"id": str(existing.id)},
            json={"note": None},
        )

        assert response.status_code == 200, response.text
        assert response.json()["note"] is None

    async def test_empty_patch_is_a_no_op(self, client, make_application):
        existing = await make_application(company="Untouched")

        response = await client.patch(
            "/application/", params={"id": str(existing.id)}, json={}
        )

        assert response.status_code == 200, response.text
        assert response.json()["company"] == "Untouched"

    async def test_note_over_max_length_is_rejected(self, client, make_application):
        """The 2000-char cap is the column width, so it has to fail validation.

        Without it the request reaches Postgres and fails there instead, which
        surfaces as a 500 rather than a 422.
        """
        existing = await make_application()

        response = await client.patch(
            "/application/",
            params={"id": str(existing.id)},
            json={"note": "x" * 2001},
        )

        assert response.status_code == 422

    async def test_cannot_update_another_users_application(
        self, client, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        response = await client.patch(
            "/application/", params={"id": str(theirs.id)}, json=create_body()
        )

        assert response.status_code == 403


class TestDeleteEndpoint:
    async def test_deletes_an_owned_application(self, client, make_application):
        existing = await make_application()

        response = await client.delete(
            "/application/", params={"application_id": str(existing.id)}
        )

        assert response.status_code == 200, response.text

        listed = await client.get("/application/all")
        assert listed.json()["total"] == 0

    async def test_unknown_id_is_404(self, client):
        response = await client.delete(
            "/application/", params={"application_id": str(uuid4())}
        )

        assert response.status_code == 404

    async def test_cannot_delete_another_users_application(
        self, client, make_application, other_user
    ):
        theirs = await make_application(owner=other_user)

        response = await client.delete(
            "/application/", params={"application_id": str(theirs.id)}
        )

        assert response.status_code == 403


class TestByStatusEndpoint:
    async def test_filters_by_a_single_status(self, client, make_application):
        await make_application(company="A", status="applied")
        await make_application(company="B", status="offer")

        response = await client.get(
            "/application/status", params={"application_status": "offer"}
        )

        assert response.status_code == 200, response.text
        assert [a["company"] for a in response.json()] == ["B"]

    async def test_rejects_an_invalid_status(self, client):
        response = await client.get(
            "/application/status", params={"application_status": "nonsense"}
        )

        assert response.status_code == 422


class TestAuthenticationIsRequired:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/application/all"),
            ("get", "/application/stats"),
            ("get", "/application/recent"),
            ("post", "/application/"),
        ],
        ids=["list", "stats", "recent", "create"],
    )
    async def test_unauthenticated_requests_are_401(self, anon_client, method, path):
        response = await getattr(anon_client, method)(path)

        assert response.status_code == 401

    async def test_a_garbage_token_is_401(self, anon_client):
        response = await anon_client.get(
            "/application/all", headers={"Authorization": "Bearer not-a-jwt"}
        )

        assert response.status_code == 401
