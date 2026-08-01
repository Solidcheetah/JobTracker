from datetime import datetime, timedelta, timezone


def _future(hours=2):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


class TestReminderSmoke:
    async def test_create_get_list(self, client):
        r = await client.post(
            "/reminder/", json={"content": "follow up", "remind_at": _future()}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        rid = body["id"]

        r = await client.get(f"/reminder/?id={rid}")
        assert r.status_code == 200, r.text
        assert r.json()["content"] == "follow up"

        r = await client.get("/reminder/all")
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1
        assert r.json()["total_pages"] == 1

    async def test_status_filter_flattens(self, client):
        await client.post(
            "/reminder/", json={"content": "a", "remind_at": _future()}
        )
        r = await client.get("/reminder/all?status=pending")
        assert r.json()["total"] == 1, r.text
        r = await client.get("/reminder/all?status=delivered")
        assert r.json()["total"] == 0, "status filter was ignored"

    async def test_past_date_rejected(self, client):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        r = await client.post("/reminder/", json={"content": "x", "remind_at": past})
        assert r.status_code == 422, r.text

    async def test_naive_date_rejected(self, client):
        naive = (datetime.now() + timedelta(hours=2)).isoformat()
        r = await client.post("/reminder/", json={"content": "x", "remind_at": naive})
        assert r.status_code == 422, r.text

    async def test_update_then_cancel_then_conflict(self, client):
        rid = (
            await client.post(
                "/reminder/", json={"content": "old", "remind_at": _future()}
            )
        ).json()["id"]

        r = await client.patch(f"/reminder/?id={rid}", json={"content": "new"})
        assert r.status_code == 200, r.text
        assert r.json()["content"] == "new"

        r = await client.delete(f"/reminder/?id={rid}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

        # cancelled is no longer mutable
        r = await client.patch(f"/reminder/?id={rid}", json={"content": "nope"})
        assert r.status_code == 409, r.text

        # cancelling twice is idempotent, not an error
        r = await client.delete(f"/reminder/?id={rid}")
        assert r.status_code == 200, r.text

    async def test_upcoming(self, client):
        await client.post(
            "/reminder/", json={"content": "soon", "remind_at": _future(1)}
        )
        r = await client.get("/reminder/upcoming")
        assert r.status_code == 200, r.text
        assert len(r.json()) == 1

    async def test_missing_is_404(self, client):
        r = await client.get("/reminder/?id=00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404, r.text

    async def test_other_users_reminder_is_403(self, client, session, other_user):
        from uuid import uuid4

        from app.database.models import Reminder

        rid = uuid4()
        session.add(
            Reminder(
                id=rid,
                owner_id=other_user.id,
                content="theirs",
                remind_at=datetime.now(timezone.utc) + timedelta(hours=5),
            )
        )
        await session.commit()

        r = await client.get(f"/reminder/?id={rid}")
        assert r.status_code == 403, r.text
