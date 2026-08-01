"""Worker-side reminder state transitions.

Kept apart from `ReminderService` because the two have opposite security models:
that one is always scoped to one authenticated user, this one deliberately works
across every owner in the table. Mixing them would put a method that ignores
ownership on the same object the request handlers use.

Every method takes an explicit `now` so the caller decides what time it is. That
makes the lease and due-date logic testable without sleeping, and keeps one clock
in play per tick rather than a fresh one per statement.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Reminder
from app.database.models.reminder_status import ReminderStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClaimedReminder:
    """A reminder this process has taken responsibility for publishing.

    Deliberately a plain value rather than a `Reminder` instance: the session it
    was claimed in is closed before publishing starts, and a detached ORM object
    would raise on attribute access at exactly the wrong moment.
    """

    id: UUID
    owner_id: UUID
    content: str
    remind_at: datetime
    attempt_count: int


@dataclass(frozen=True)
class ReapResult:
    requeued: list[UUID]
    abandoned: list[UUID]


class ReminderDispatchService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 100,
        lease_seconds: int = 120,
        max_attempts: int = 5,
    ):
        self.session = session
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    async def claim_due(self, now: datetime | None = None) -> list[ClaimedReminder]:
        """Take ownership of every reminder whose time has come.

        The claim and the status change are one statement on purpose. Reading the
        due rows and then updating them would leave a gap in which a second
        scanner reads the same rows, and both publish. Here the `UPDATE` is what
        selects: a row can only leave `pending` once, so whichever process wins
        gets it and the other sees nothing.

        `FOR UPDATE SKIP LOCKED` is what stops the losing scanner from blocking
        on the winner's locks — it steps over rows already spoken for instead of
        waiting, which is what makes running several scanners useful rather than
        merely safe.
        """
        now = now or utcnow()

        due = (
            select(Reminder.id)
            .where(
                Reminder.status == ReminderStatus.pending,
                Reminder.remind_at <= now,
            )
            .order_by(Reminder.remind_at.asc())
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )

        result = await self.session.execute(
            update(Reminder)
            .where(Reminder.id.in_(due))
            .values(
                status=ReminderStatus.queued,
                claimed_at=now,
                attempt_count=Reminder.attempt_count + 1,
            )
            .returning(
                Reminder.id,
                Reminder.owner_id,
                Reminder.content,
                Reminder.remind_at,
                Reminder.attempt_count,
            )
        )

        return [
            ClaimedReminder(
                id=row.id,
                owner_id=row.owner_id,
                content=row.content,
                remind_at=row.remind_at,
                attempt_count=row.attempt_count,
            )
            for row in result.all()
        ]

    async def mark_delivered(self, reminder_id: UUID, now: datetime | None = None) -> bool:
        """Close out a reminder the notifier successfully handled.

        Scoped to `queued` so a duplicate delivery of an already-closed reminder
        is a no-op returning False, rather than resurrecting a finished row.
        """
        result = await self.session.execute(
            update(Reminder)
            .where(
                Reminder.id == reminder_id,
                Reminder.status == ReminderStatus.queued,
            )
            .values(status=ReminderStatus.delivered, claimed_at=None)
            .returning(Reminder.id)
        )
        return result.first() is not None

    async def release(self, reminder_id: UUID) -> bool:
        """Hand a reminder back after a failed publish or a retryable delivery error.

        Returning it to `pending` immediately means the next tick retries it,
        instead of it sitting in `queued` until the lease expires. `attempt_count`
        is left as the claim incremented it, so repeated failures still converge
        on `failed` rather than looping forever.
        """
        result = await self.session.execute(
            update(Reminder)
            .where(
                Reminder.id == reminder_id,
                Reminder.status == ReminderStatus.queued,
            )
            .values(status=ReminderStatus.pending, claimed_at=None)
            .returning(Reminder.id)
        )
        return result.first() is not None

    async def mark_failed(self, reminder_id: UUID) -> bool:
        """Abandon a reminder permanently. Used for errors a retry cannot fix."""
        result = await self.session.execute(
            update(Reminder)
            .where(
                Reminder.id == reminder_id,
                Reminder.status == ReminderStatus.queued,
            )
            .values(status=ReminderStatus.failed, claimed_at=None)
            .returning(Reminder.id)
        )
        return result.first() is not None

    async def reap_stale_leases(self, now: datetime | None = None) -> ReapResult:
        """Recover reminders whose claimer died before publishing them.

        A process killed between claiming and publishing leaves rows stuck in
        `queued` with nothing on its way to deliver them, and nothing else will
        ever pick them up — `claim_due` only looks at `pending`. This is the only
        thing standing between a crash and a reminder that silently never fires.

        Rows that have burned through `max_attempts` are abandoned rather than
        requeued. Without that, a reminder that reliably kills its worker comes
        back every lease interval forever.
        """
        now = now or utcnow()
        cutoff = now - timedelta(seconds=self.lease_seconds)

        stale = (
            Reminder.status == ReminderStatus.queued,
            Reminder.claimed_at.is_not(None),
            Reminder.claimed_at < cutoff,
        )

        # Order matters: abandon the exhausted rows first, so the requeue below
        # cannot scoop them up and hand them out for another doomed attempt.
        abandoned = await self.session.execute(
            update(Reminder)
            .where(*stale, Reminder.attempt_count >= self.max_attempts)
            .values(status=ReminderStatus.failed, claimed_at=None)
            .returning(Reminder.id)
        )
        abandoned_ids = [row.id for row in abandoned.all()]

        requeued = await self.session.execute(
            update(Reminder)
            .where(*stale)
            .values(status=ReminderStatus.pending, claimed_at=None)
            .returning(Reminder.id)
        )
        requeued_ids = [row.id for row in requeued.all()]

        return ReapResult(requeued=requeued_ids, abandoned=abandoned_ids)

    async def pending_backlog(self, now: datetime | None = None) -> int:
        """Count reminders that are due but not yet claimed. For logging only."""
        now = now or utcnow()
        return (
            await self.session.scalar(
                select(func.count(Reminder.id)).where(
                    Reminder.status == ReminderStatus.pending,
                    Reminder.remind_at <= now,
                )
            )
        ) or 0
