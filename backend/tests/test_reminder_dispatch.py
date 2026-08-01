"""Tests for the worker-side reminder state machine.

Scope note: these run on SQLite, which ignores `FOR UPDATE SKIP LOCKED`. So they
prove the state transitions — a reminder is claimed once, a stale lease comes
back, an exhausted one is abandoned — but they do *not* prove that two concurrent
scanners cannot claim the same row. That guarantee is Postgres-specific and can
only be verified against a real database.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.database.models.reminder_status import ReminderStatus
from app.services.reminder_dispatch import ReminderDispatchService

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


def _minutes(n: int) -> timedelta:
    return timedelta(minutes=n)


@pytest.fixture
def dispatch(session):
    return ReminderDispatchService(
        session, batch_size=10, lease_seconds=120, max_attempts=3
    )


class TestClaimDue:
    async def test_claims_a_due_reminder(self, dispatch, make_reminder, session):
        reminder = await make_reminder(remind_at=NOW - _minutes(1))

        claimed = await dispatch.claim_due(NOW)

        assert [c.id for c in claimed] == [reminder.id]
        assert claimed[0].content == "Follow up"
        assert claimed[0].attempt_count == 1

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued
        assert reminder.claimed_at is not None

    async def test_second_claim_does_not_return_it_again(
        self, dispatch, make_reminder
    ):
        """The property the whole design exists to provide: no double publish."""
        await make_reminder(remind_at=NOW - _minutes(1))

        first = await dispatch.claim_due(NOW)
        second = await dispatch.claim_due(NOW)

        assert len(first) == 1
        assert second == []

    async def test_ignores_reminders_not_yet_due(self, dispatch, make_reminder):
        await make_reminder(remind_at=NOW + _minutes(1))
        assert await dispatch.claim_due(NOW) == []

    async def test_claims_one_due_exactly_now(self, dispatch, make_reminder):
        await make_reminder(remind_at=NOW)
        assert len(await dispatch.claim_due(NOW)) == 1

    @pytest.mark.parametrize(
        "status",
        [
            ReminderStatus.queued,
            ReminderStatus.delivered,
            ReminderStatus.failed,
            ReminderStatus.cancelled,
        ],
    )
    async def test_only_pending_is_eligible(self, dispatch, make_reminder, status):
        await make_reminder(remind_at=NOW - _minutes(5), status=status)
        assert await dispatch.claim_due(NOW) == []

    async def test_cancelled_reminder_is_never_delivered(
        self, dispatch, make_reminder
    ):
        """A user who cancels before the due date should hear nothing."""
        await make_reminder(
            remind_at=NOW - _minutes(30), status=ReminderStatus.cancelled
        )
        assert await dispatch.claim_due(NOW) == []

    async def test_respects_batch_size(self, dispatch, make_reminder):
        for i in range(15):
            await make_reminder(remind_at=NOW - _minutes(i + 1))

        assert len(await dispatch.claim_due(NOW)) == 10  # batch_size
        assert len(await dispatch.claim_due(NOW)) == 5

    async def test_claims_the_oldest_when_the_backlog_exceeds_the_batch(
        self, session, make_reminder
    ):
        """No starvation: the longest-overdue reminders go out first.

        Asserted on *which* rows are claimed, not the order they come back in —
        `RETURNING` makes no promise about that, and nothing downstream needs it,
        since each claimed reminder is published on its own.
        """
        dispatch = ReminderDispatchService(session, batch_size=2)

        oldest = await make_reminder(remind_at=NOW - _minutes(90))
        middle = await make_reminder(remind_at=NOW - _minutes(30))
        await make_reminder(remind_at=NOW - _minutes(1))

        claimed = await dispatch.claim_due(NOW)

        assert {c.id for c in claimed} == {oldest.id, middle.id}

    async def test_claims_across_owners(
        self, dispatch, make_reminder, user, other_user
    ):
        """The scanner is not scoped to one user, unlike the request-time service."""
        await make_reminder(owner=user, remind_at=NOW - _minutes(1))
        await make_reminder(owner=other_user, remind_at=NOW - _minutes(1))

        claimed = await dispatch.claim_due(NOW)

        assert {c.owner_id for c in claimed} == {user.id, other_user.id}


class TestMarkDelivered:
    async def test_closes_out_a_queued_reminder(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        assert await dispatch.mark_delivered(reminder.id) is True

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.delivered
        assert reminder.claimed_at is None

    async def test_is_idempotent(self, dispatch, make_reminder):
        """A redelivered message must not resurrect a finished reminder."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        assert await dispatch.mark_delivered(reminder.id) is True
        assert await dispatch.mark_delivered(reminder.id) is False

    async def test_will_not_deliver_a_cancelled_reminder(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(status=ReminderStatus.cancelled)

        assert await dispatch.mark_delivered(reminder.id) is False

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.cancelled


class TestRelease:
    async def test_returns_reminder_to_pending(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(
            status=ReminderStatus.queued, claimed_at=NOW, attempt_count=1
        )

        assert await dispatch.release(reminder.id) is True

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.pending
        assert reminder.claimed_at is None

    async def test_keeps_attempt_count(self, dispatch, make_reminder, session):
        """Otherwise a reliably-failing reminder retries forever."""
        reminder = await make_reminder(
            status=ReminderStatus.queued, claimed_at=NOW, attempt_count=2
        )

        await dispatch.release(reminder.id)

        await session.refresh(reminder)
        assert reminder.attempt_count == 2

    async def test_released_reminder_is_claimable_again(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(remind_at=NOW - _minutes(1))

        first = await dispatch.claim_due(NOW)
        await dispatch.release(reminder.id)
        second = await dispatch.claim_due(NOW)

        assert first[0].attempt_count == 1
        assert second[0].attempt_count == 2, "each claim should count as an attempt"


class TestMarkFailed:
    async def test_abandons_a_queued_reminder(self, dispatch, make_reminder, session):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        assert await dispatch.mark_failed(reminder.id) is True

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.failed


class TestReapStaleLeases:
    async def test_requeues_a_lease_that_expired(
        self, dispatch, make_reminder, session
    ):
        """The crash-recovery path: a worker died between claiming and publishing."""
        reminder = await make_reminder(
            status=ReminderStatus.queued,
            claimed_at=NOW - _minutes(10),  # lease is 120s
            attempt_count=1,
        )

        result = await dispatch.reap_stale_leases(NOW)

        assert result.requeued == [reminder.id]
        assert result.abandoned == []

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.pending
        assert reminder.claimed_at is None

    async def test_leaves_a_fresh_lease_alone(self, dispatch, make_reminder, session):
        """A scanner still working through its batch must not have rows yanked."""
        reminder = await make_reminder(
            status=ReminderStatus.queued, claimed_at=NOW - timedelta(seconds=30)
        )

        result = await dispatch.reap_stale_leases(NOW)

        assert result.requeued == []
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued

    async def test_abandons_a_reminder_that_exhausted_its_attempts(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(
            status=ReminderStatus.queued,
            claimed_at=NOW - _minutes(10),
            attempt_count=3,  # max_attempts
        )

        result = await dispatch.reap_stale_leases(NOW)

        assert result.abandoned == [reminder.id]
        assert result.requeued == [], "an abandoned reminder must not also be requeued"

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.failed

    async def test_ignores_pending_and_delivered(self, dispatch, make_reminder):
        await make_reminder(status=ReminderStatus.pending)
        await make_reminder(status=ReminderStatus.delivered)

        result = await dispatch.reap_stale_leases(NOW)

        assert result.requeued == []
        assert result.abandoned == []

    async def test_reaped_reminder_is_claimable_again(
        self, dispatch, make_reminder, session
    ):
        reminder = await make_reminder(
            remind_at=NOW - _minutes(30),
            status=ReminderStatus.queued,
            claimed_at=NOW - _minutes(10),
            attempt_count=1,
        )

        await dispatch.reap_stale_leases(NOW)
        claimed = await dispatch.claim_due(NOW)

        assert [c.id for c in claimed] == [reminder.id]
        assert claimed[0].attempt_count == 2

    async def test_repeated_failure_converges_on_failed(
        self, dispatch, make_reminder, session
    ):
        """Walk a reminder through its whole retry budget and off the end."""
        reminder = await make_reminder(remind_at=NOW - _minutes(1))
        now = NOW

        for expected_attempt in (1, 2, 3):
            claimed = await dispatch.claim_due(now)
            assert [c.id for c in claimed] == [reminder.id]
            assert claimed[0].attempt_count == expected_attempt

            # Simulate the worker dying before publishing, every time.
            now = now + _minutes(5)
            await dispatch.reap_stale_leases(now)

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.failed
        assert await dispatch.claim_due(now) == []


class TestPendingBacklog:
    async def test_counts_only_due_pending(self, dispatch, make_reminder):
        await make_reminder(remind_at=NOW - _minutes(1))
        await make_reminder(remind_at=NOW - _minutes(2))
        await make_reminder(remind_at=NOW + _minutes(5))
        await make_reminder(remind_at=NOW - _minutes(3), status=ReminderStatus.queued)

        assert await dispatch.pending_backlog(NOW) == 2
