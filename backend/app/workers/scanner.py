"""Reminder scanner: polls for due reminders and publishes them.

Run standalone:

    python -m app.workers.scanner

Safe to run more than one replica. `claim_due` uses `FOR UPDATE SKIP LOCKED`, so
concurrent scanners partition the due rows between themselves rather than both
publishing the same reminder. (This is the one guarantee the test suite cannot
prove — SQLite ignores SKIP LOCKED. It only holds against Postgres.)
"""

import asyncio

from aio_pika.abc import AbstractRobustExchange

from app.config import broker_settings, reminder_worker_settings
from app.database.session import admin_session_factory, dispose_admin_engine
from app.services.reminder_dispatch import (
    ClaimedReminder,
    ReminderDispatchService,
    utcnow,
)
from app.workers.broker import ReminderMessage, connect, declare_topology, publish
from app.workers.runtime import install_signal_handlers, setup_logging, sleep_or_stop

logger = setup_logging("scanner")


def _dispatch(session) -> ReminderDispatchService:
    return ReminderDispatchService(
        session,
        batch_size=reminder_worker_settings.REMINDER_BATCH_SIZE,
        lease_seconds=reminder_worker_settings.REMINDER_LEASE_SECONDS,
        max_attempts=reminder_worker_settings.REMINDER_MAX_ATTEMPTS,
    )


async def tick(session_factory, exchange: AbstractRobustExchange, now=None) -> int:
    """One scan. Returns how many reminders were published.

    The ordering here is the whole design, and it is deliberately not the obvious
    one. The claim is committed *before* anything is published, which means a
    crash between the two leaves a reminder marked `queued` that no message was
    ever sent for — recovered by the reaper on a later tick.

    Publishing first would be worse in a way that cannot be recovered from: the
    message goes out, the commit fails, the row stays `pending`, and the next tick
    publishes it again. Between sending a reminder twice and sending it a couple
    of minutes late, late is the easier failure to live with. That choice is what
    makes this at-least-once rather than at-most-once, and it is why the notifier
    has to tolerate seeing the same reminder more than once.
    """
    now = now or utcnow()

    async with session_factory() as session:
        service = _dispatch(session)

        async with session.begin():
            reaped = await service.reap_stale_leases(now)

        if reaped.requeued:
            logger.warning(
                "requeued %d reminder(s) abandoned by a dead worker: %s",
                len(reaped.requeued),
                ", ".join(str(i) for i in reaped.requeued),
            )
        if reaped.abandoned:
            logger.error(
                "gave up on %d reminder(s) after %d attempts: %s",
                len(reaped.abandoned),
                reminder_worker_settings.REMINDER_MAX_ATTEMPTS,
                ", ".join(str(i) for i in reaped.abandoned),
            )

        async with session.begin():
            claimed = await service.claim_due(now)

    if not claimed:
        return 0

    logger.info("claimed %d due reminder(s)", len(claimed))

    published = 0
    for reminder in claimed:
        if await _publish_one(session_factory, exchange, reminder):
            published += 1

    return published


async def _publish_one(
    session_factory, exchange: AbstractRobustExchange, reminder: ClaimedReminder
) -> bool:
    try:
        await publish(
            exchange,
            ReminderMessage(
                reminder_id=reminder.id,
                owner_id=reminder.owner_id,
                content=reminder.content,
                remind_at=reminder.remind_at,
                attempt=reminder.attempt_count,
            ),
        )
    except Exception:
        # Hand the row straight back rather than leaving it for the reaper. The
        # reaper would fix it eventually, but only after the lease expires; this
        # gets it retried on the very next tick.
        logger.exception("publish failed for reminder %s, releasing it", reminder.id)
        async with session_factory() as session:
            async with session.begin():
                await _dispatch(session).release(reminder.id)
        return False

    logger.info(
        "published reminder %s (attempt %d)", reminder.id, reminder.attempt_count
    )
    return True


async def run() -> None:
    stopping = install_signal_handlers()
    session_factory = admin_session_factory()

    connection = await connect()
    # Publisher confirms make `publish` wait for the broker to acknowledge the
    # message. Without them a publish into a broker that is going down looks
    # like a success, and the reminder is marked `queued` for something that was
    # never queued at all.
    channel = await connection.channel(publisher_confirms=True)
    exchange, _ = await declare_topology(channel)

    logger.info(
        "scanning every %.1fs (batch %d, lease %ds, max attempts %d) -> %s",
        reminder_worker_settings.REMINDER_POLL_INTERVAL,
        reminder_worker_settings.REMINDER_BATCH_SIZE,
        reminder_worker_settings.REMINDER_LEASE_SECONDS,
        reminder_worker_settings.REMINDER_MAX_ATTEMPTS,
        broker_settings.REMINDER_QUEUE,
    )

    try:
        while not stopping.is_set():
            try:
                await tick(session_factory, exchange)
            except Exception:
                # One bad tick must not kill the loop, or a transient database
                # blip becomes a permanently stopped reminder system.
                logger.exception("scan failed, continuing")

            await sleep_or_stop(
                stopping, reminder_worker_settings.REMINDER_POLL_INTERVAL
            )
    finally:
        logger.info("shutting down")
        await connection.close()
        await dispose_admin_engine()


if __name__ == "__main__":
    asyncio.run(run())
