"""Filtering and pagination on GET /application/all.

The HTTP-level status tests here are regression cover for a bug where the filter
model was bound with ``Depends()`` instead of ``Query()``. FastAPI then treated
the ``list[ApplicationStatus]`` field as a nested body model and never read the
repeated ``?status=`` values, so filters silently returned everything with a 200.
Service-level tests alone would not have caught it — the break was in binding.
"""

from datetime import date

import pytest


class TestFilterByStatus:
    async def test_single_status(self, service, make_application):
        await make_application(company="Applied", status="applied")
        await make_application(company="Offer", status="offer")

        items, total = await service.list_applications(
            filters=_filters(status=["offer"])
        )

        assert total == 1
        assert [a.company for a in items] == ["Offer"]

    async def test_multiple_statuses_are_an_or(self, service, make_application):
        await make_application(company="A", status="applied")
        await make_application(company="B", status="offer")
        await make_application(company="C", status="rejected")

        items, total = await service.list_applications(
            filters=_filters(status=["applied", "offer"])
        )

        assert total == 2
        assert sorted(a.company for a in items) == ["A", "B"]

    async def test_no_status_filter_returns_everything(self, service, make_application):
        await make_application(status="applied")
        await make_application(status="offer")

        _, total = await service.list_applications(filters=_filters())

        assert total == 2


class TestFilterBySearch:
    async def test_matches_company(self, service, make_application):
        await make_application(company="Acme Corp", role="Engineer")
        await make_application(company="Globex", role="Designer")

        items, _ = await service.list_applications(filters=_filters(search="Acme"))

        assert [a.company for a in items] == ["Acme Corp"]

    async def test_matches_role(self, service, make_application):
        await make_application(company="Acme", role="Backend Engineer")
        await make_application(company="Globex", role="Designer")

        items, _ = await service.list_applications(filters=_filters(search="Backend"))

        assert [a.role for a in items] == ["Backend Engineer"]

    async def test_is_case_insensitive(self, service, make_application):
        await make_application(company="Acme Corp")

        items, _ = await service.list_applications(filters=_filters(search="acme"))

        assert len(items) == 1

    async def test_matches_a_substring(self, service, make_application):
        await make_application(company="Microsoft")

        items, _ = await service.list_applications(filters=_filters(search="cros"))

        assert len(items) == 1

    async def test_no_match_returns_empty(self, service, make_application):
        await make_application(company="Acme")

        items, total = await service.list_applications(
            filters=_filters(search="Nonexistent")
        )

        assert items == []
        assert total == 0


class TestFilterByDate:
    async def test_applied_from_is_inclusive(self, service, make_application):
        await make_application(company="On", applied_at=date(2026, 6, 1))
        await make_application(company="Before", applied_at=date(2026, 5, 1))

        items, _ = await service.list_applications(
            filters=_filters(applied_from=date(2026, 6, 1))
        )

        assert [a.company for a in items] == ["On"]

    async def test_applied_to_is_inclusive(self, service, make_application):
        await make_application(company="On", applied_at=date(2026, 6, 1))
        await make_application(company="After", applied_at=date(2026, 7, 1))

        items, _ = await service.list_applications(
            filters=_filters(applied_to=date(2026, 6, 1))
        )

        assert [a.company for a in items] == ["On"]

    async def test_a_range_bounds_both_ends(self, service, make_application):
        await make_application(company="Before", applied_at=date(2026, 1, 1))
        await make_application(company="Inside", applied_at=date(2026, 6, 15))
        await make_application(company="After", applied_at=date(2026, 12, 1))

        items, _ = await service.list_applications(
            filters=_filters(applied_from=date(2026, 6, 1), applied_to=date(2026, 6, 30))
        )

        assert [a.company for a in items] == ["Inside"]


class TestCombinedFilters:
    async def test_filters_are_combined_with_and(self, service, make_application):
        await make_application(company="Acme", status="applied", applied_at=date(2026, 6, 1))
        await make_application(company="Acme", status="offer", applied_at=date(2026, 6, 1))
        await make_application(company="Globex", status="applied", applied_at=date(2026, 6, 1))

        items, total = await service.list_applications(
            filters=_filters(status=["applied"], search="Acme")
        )

        assert total == 1
        assert items[0].company == "Acme"
        assert items[0].status == "applied"

    async def test_filters_never_cross_users(
        self, service, make_application, other_user
    ):
        await make_application(company="Acme", status="offer", owner=other_user)

        items, total = await service.list_applications(
            filters=_filters(status=["offer"], search="Acme")
        )

        assert items == []
        assert total == 0


class TestPagination:
    async def test_total_counts_all_matches_not_just_the_page(
        self, service, make_application
    ):
        for day in range(1, 8):
            await make_application(company=f"C{day}", applied_at=date(2026, 6, day))

        items, total = await service.list_applications(page=1, page_size=5)

        assert len(items) == 5
        assert total == 7

    async def test_second_page_returns_the_remainder(self, service, make_application):
        for day in range(1, 8):
            await make_application(company=f"C{day}", applied_at=date(2026, 6, day))

        items, total = await service.list_applications(page=2, page_size=5)

        assert len(items) == 2
        assert total == 7

    async def test_pages_do_not_overlap(self, service, make_application):
        for day in range(1, 8):
            await make_application(company=f"C{day}", applied_at=date(2026, 6, day))

        first, _ = await service.list_applications(page=1, page_size=5)
        second, _ = await service.list_applications(page=2, page_size=5)

        assert set(a.id for a in first).isdisjoint(a.id for a in second)

    async def test_page_beyond_the_end_is_empty(self, service, make_application):
        await make_application()

        items, total = await service.list_applications(page=10, page_size=5)

        assert items == []
        assert total == 1

    async def test_total_reflects_the_filter(self, service, make_application):
        for day in range(1, 6):
            await make_application(status="applied", applied_at=date(2026, 6, day))
        await make_application(status="offer", applied_at=date(2026, 6, 6))

        _, total = await service.list_applications(
            page=1, page_size=2, filters=_filters(status=["offer"])
        )

        assert total == 1


class TestFilteringOverHttp:
    """Regression cover for the Depends()/Query() binding bug."""

    async def test_repeated_status_params_are_applied(self, client, make_application):
        await make_application(company="Applied", status="applied")
        await make_application(company="Offer", status="offer")
        await make_application(company="Rejected", status="rejected")

        response = await client.get("/application/all?status=applied&status=offer")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 2, "repeated ?status= values were not applied"
        assert sorted(i["company"] for i in body["items"]) == ["Applied", "Offer"]

    async def test_a_single_status_param_is_applied(self, client, make_application):
        await make_application(company="Applied", status="applied")
        await make_application(company="Offer", status="offer")

        response = await client.get("/application/all?status=offer")

        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1

    async def test_bracketed_array_syntax_is_not_silently_accepted(
        self, client, make_application
    ):
        """status[]=… is what axios sends by default; it must not read as a filter.

        Documents why the frontend serializer emits repeated keys instead. The
        param is ignored, so the response is unfiltered rather than an error.
        """
        await make_application(company="Applied", status="applied")
        await make_application(company="Offer", status="offer")

        response = await client.get("/application/all?status[]=offer")

        assert response.status_code == 200
        assert response.json()["total"] == 2

    async def test_search_is_applied(self, client, make_application):
        await make_application(company="Acme")
        await make_application(company="Globex")

        response = await client.get("/application/all?search=Acme")

        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1

    async def test_date_range_is_applied(self, client, make_application):
        await make_application(company="Inside", applied_at=date(2026, 6, 15))
        await make_application(company="Outside", applied_at=date(2026, 1, 1))

        response = await client.get(
            "/application/all?applied_from=2026-06-01&applied_to=2026-06-30"
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["company"] == "Inside"

    async def test_status_and_search_combine(self, client, make_application):
        await make_application(company="Acme", status="applied")
        await make_application(company="Acme", status="offer")
        await make_application(company="Globex", status="applied")

        response = await client.get("/application/all?status=applied&search=Acme")

        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1

    async def test_an_invalid_status_is_rejected(self, client):
        response = await client.get("/application/all?status=not-a-status")

        assert response.status_code == 422

    async def test_no_filters_returns_everything(self, client, make_application):
        await make_application(status="applied")
        await make_application(status="offer")

        response = await client.get("/application/all")

        assert response.status_code == 200, response.text
        assert response.json()["total"] == 2

    async def test_pagination_metadata_is_correct(self, client, make_application):
        for day in range(1, 8):
            await make_application(applied_at=date(2026, 6, day))

        response = await client.get("/application/all?page=2&page_size=5")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["page"] == 2
        assert body["page_size"] == 5
        assert body["total"] == 7
        assert body["total_pages"] == 2
        assert len(body["items"]) == 2

    async def test_total_pages_when_the_result_is_empty(self, client):
        response = await client.get("/application/all")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 0
        assert body["total_pages"] == 0

    async def test_filters_and_pagination_combine(self, client, make_application):
        for day in range(1, 8):
            await make_application(status="applied", applied_at=date(2026, 6, day))
        await make_application(status="offer", applied_at=date(2026, 6, 8))

        response = await client.get("/application/all?status=applied&page=2&page_size=5")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 7
        assert len(body["items"]) == 2
        assert all(i["status"] == "applied" for i in body["items"])

    @pytest.mark.parametrize(
        "query",
        ["page=0", "page=-1", "page_size=0", "page_size=101"],
        ids=["page-zero", "page-negative", "size-zero", "size-over-max"],
    )
    async def test_invalid_pagination_is_rejected(self, client, query):
        response = await client.get(f"/application/all?{query}")

        assert response.status_code == 422


def _filters(**kwargs):
    from app.schemas.application import ApplicationFilterParams

    return ApplicationFilterParams(**kwargs)
