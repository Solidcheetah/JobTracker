"""Stats aggregation and status history."""

from datetime import date

from app.database.models.application_status import ApplicationStatus


class TestStats:
    async def test_counts_every_status_even_at_zero(self, service):
        """The dashboard chart reads every key, so none may be missing."""
        stats = await service.get_application_stats()

        assert set(stats.status_counts) == {s.value for s in ApplicationStatus}
        assert all(count == 0 for count in stats.status_counts.values())

    async def test_total_is_zero_with_no_applications(self, service):
        assert (await service.get_application_stats()).total == 0

    async def test_counts_per_status(self, service, make_application):
        await make_application(status="applied")
        await make_application(status="applied")
        await make_application(status="offer")

        stats = await service.get_application_stats()

        assert stats.status_counts["applied"] == 2
        assert stats.status_counts["offer"] == 1
        assert stats.status_counts["rejected"] == 0

    async def test_total_is_the_sum_of_the_counts(self, service, make_application):
        await make_application(status="applied")
        await make_application(status="offer")
        await make_application(status="wishlist")

        stats = await service.get_application_stats()

        assert stats.total == 3
        assert stats.total == sum(stats.status_counts.values())

    async def test_most_common_status(self, service, make_application):
        await make_application(status="rejected")
        await make_application(status="rejected")
        await make_application(status="applied")

        assert (await service.get_application_stats()).most_common_status == "rejected"

    async def test_stats_exclude_other_users(
        self, service, make_application, other_user
    ):
        await make_application(status="applied")
        await make_application(status="offer", owner=other_user)
        await make_application(status="offer", owner=other_user)

        stats = await service.get_application_stats()

        assert stats.total == 1
        assert stats.status_counts["offer"] == 0

    async def test_most_common_is_still_set_when_all_counts_are_zero(self, service):
        """max() over an all-zero dict returns a key rather than None."""
        stats = await service.get_application_stats()

        assert stats.total == 0
        assert stats.most_common_status is not None


class TestStatusHistory:
    async def test_newly_created_application_has_one_entry(
        self, service, make_application, session
    ):
        from app.schemas.application import ApplicationCreateSchema

        created = await service.add(
            ApplicationCreateSchema(
                company="Acme",
                role="Engineer",
                status="wishlist",
                applied_at=date(2026, 6, 1),
            )
        )
        await session.commit()

        history = await service.get_status_history(created.id)

        assert [h.status for h in history] == ["wishlist"]

    async def test_returns_newest_first(self, service, make_application, session):
        existing = await make_application(status="applied")
        await service.update_status(existing.id, "screen")
        await service.update_status(existing.id, "onsite")
        await session.commit()

        history = await service.get_status_history(existing.id)

        assert len(history) == 2
        assert history[0].changed_at >= history[1].changed_at

    async def test_empty_for_an_application_with_no_recorded_changes(
        self, service, make_application
    ):
        existing = await make_application()

        assert await service.get_status_history(existing.id) == []

    async def test_history_of_another_users_application_is_readable(
        self, client, make_application, other_user, other_service, session
    ):
        """KNOWN ISSUE: /application/history does not check ownership.

        Every other application route funnels through ``ApplicationService.get``,
        which raises 403 for a non-owner. ``get_status_history`` queries
        ``application_status_history`` directly by id, and the RLS policy added in
        migration 5a63a33e7313 covers only the ``application`` table — so nothing
        stops user A reading user B's status timeline.

        This test asserts the CURRENT behaviour so the suite stays honest. When
        the ownership check is added, flip it to expect 403.
        """
        theirs = await make_application(owner=other_user, status="applied")
        await other_service.update_status(theirs.id, "offer")
        await session.commit()

        blocked = await client.get("/application/", params={"id": str(theirs.id)})
        assert blocked.status_code == 403, "the application itself should be protected"

        leaked = await client.get("/application/history", params={"id": str(theirs.id)})
        assert leaked.status_code == 200
        assert leaked.json() != [], "documents the leak: another user's history is returned"


class TestStatsAndRecentOverHttp:
    async def test_stats_endpoint(self, client, make_application):
        await make_application(status="applied")
        await make_application(status="offer")

        response = await client.get("/application/stats")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 2
        assert body["status_counts"]["applied"] == 1

    async def test_recent_endpoint_caps_at_five(self, client, make_application):
        for day in range(1, 9):
            await make_application(applied_at=date(2026, 6, day))

        response = await client.get("/application/recent")

        assert response.status_code == 200, response.text
        assert len(response.json()) == 5

    async def test_history_endpoint(self, client, make_application, session):
        existing = await make_application(status="applied")

        patch = await client.patch(
            "/application/status", params={"id": str(existing.id)}, json={"status": "offer"}
        )
        assert patch.status_code == 200, patch.text

        response = await client.get("/application/history", params={"id": str(existing.id)})

        assert response.status_code == 200, response.text
        assert [h["status"] for h in response.json()] == ["offer"]
