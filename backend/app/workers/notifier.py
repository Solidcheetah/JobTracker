"""Reminder notifier: consumes due reminders and delivers them.

Run standalone:

    python -m app.workers.notifier

Replicate freely — each message goes to exactly one consumer, so adding replicas
adds throughput without adding duplicate notifications.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from aio_pika.abc import AbstractIncomingMessage

from app.config import broker_settings, email_settings, security_settings
from app.database.models import User
from app.database.session import admin_session_factory, dispose_admin_engine
from app.services.email import EmailNotConfigured, EmailRejected, send_email
from app.services.reminder_dispatch import ReminderDispatchService
from app.workers.broker import ReminderMessage, connect, declare_topology, parse
from app.workers.runtime import install_signal_handlers, setup_logging

logger = setup_logging("notifier")


class UndeliverableReminder(Exception):
    """Raised for a reminder that no amount of retrying will fix.

    Distinct from an ordinary failure so `handle` can close the row out as
    `failed` instead of leaving it to be retried until it exhausts its attempts.
    """


@dataclass(frozen=True)
class Recipient:
    name: str
    email: str


async def resolve_recipient(session_factory, owner_id: UUID) -> Recipient | None:
    """Look up who to mail, or None if the owner no longer exists.

    The published message carries only `owner_id`, not an address. Resolving it
    here rather than at publish time keeps the address out of the broker, and
    means a user who changes their email between the scan and the delivery gets
    the mail at the new one.
    """
    async with session_factory() as session:
        user = await session.get(User, owner_id)
        if user is None:
            return None
        return Recipient(name=user.name, email=str(user.email))


def compose(message: ReminderMessage, recipient: Recipient) -> tuple[str, str, str]:
    """Build the (subject, text, html) for one reminder.

    Times are shown in UTC and labelled as such. There is nowhere to get the
    user's timezone from — no column stores it, and the message carries only an
    instant — so an unlabelled local-looking time would just be wrong for most
    people. Worth revisiting if a timezone ever lands on the user row.
    """
    when = message.remind_at.strftime("%d %b %Y at %H:%M UTC")

    # Long reminders would otherwise produce a subject line that mail clients
    # truncate mid-word anyway.
    summary = message.content
    if len(summary) > 60:
        summary = f"{summary[:57]}…"

    subject = f"Reminder: {summary}"

    text_body = (
        f"Hi {recipient.name},\n\n"
        f"You asked to be reminded:\n\n"
        f"    {message.content}\n\n"
        f"This was set for {when}.\n\n"
        f"Your applications: {security_settings.FRONTEND_ORIGIN}/dashboard\n\n"
        f"— JobTracker\n"
    )

    html_body = (
        '<div style="font-family:Inter,Helvetica,Arial,sans-serif;'
        'font-size:15px;color:#12283C;line-height:1.5">'
        f"<p>Hi {recipient.name},</p>"
        "<p>You asked to be reminded:</p>"
        '<blockquote style="margin:0;padding:12px 16px;background:#F4F6F9;'
        'border-left:3px solid #059669;border-radius:6px">'
        f"{message.content}"
        "</blockquote>"
        f'<p style="color:#64748B;font-size:13px">This was set for {when}.</p>'
        f'<p><a href="{security_settings.FRONTEND_ORIGIN}/dashboard" '
        'style="color:#059669">View your applications</a></p>'
        '<p style="color:#94A3B8;font-size:12px">— JobTracker</p>'
        "</div>"
    )

    return subject, text_body, html_body


async def deliver(message: ReminderMessage, recipient: Recipient) -> None:
    """Notify the user by email.

    `EmailRejected` means the address or the message itself was permanently
    refused, so it becomes `UndeliverableReminder` and the row is closed out as
    `failed`. Everything else — timeouts, connection failures, 4xx replies, bad
    credentials — propagates, which dead-letters the message and leaves the row
    `queued` for the scanner's reaper to retry.

    Note the at-least-once consequence: a redelivery sends the mail again. The
    row-level guard in `mark_delivered` prevents the *bookkeeping* from running
    twice, but it runs after this, so a duplicate message on the queue does mean
    a duplicate email. Acceptable for a reminder; it would not be for anything
    with side effects beyond a notification.
    """
    subject, text_body, html_body = compose(message, recipient)

    try:
        await send_email(
            to=recipient.email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    except EmailRejected as error:
        raise UndeliverableReminder(str(error)) from error
    except EmailNotConfigured:
        # Nothing is configured, so this is not the reminder's fault and marking
        # it failed would destroy it. Let it propagate and be retried.
        logger.error(
            "no SMTP credentials configured — cannot deliver reminder %s",
            message.reminder_id,
        )
        raise

    logger.info(
        "emailed reminder %s to %s (owner=%s, attempt %d)",
        message.reminder_id,
        recipient.email,
        message.owner_id,
        message.attempt,
    )


async def handle(raw: AbstractIncomingMessage, session_factory) -> None:
    """Process one message.

    `requeue=False` sends failures to the dead-letter queue rather than back onto
    the work queue. Requeueing looks kinder but produces a hot loop: a message
    that fails deterministically would be redelivered as fast as the broker can
    manage, forever.

    Dead-lettering is not the same as losing the reminder. The row is still
    `queued`, so the scanner's reaper returns it to `pending` once the lease
    expires and it gets published again on a later tick. The dead-letter queue is
    therefore a diagnostic record, not a graveyard — the retry is the database's
    job, not the broker's.
    """
    async with raw.process(requeue=False):
        message = parse(raw)

        try:
            recipient = await resolve_recipient(session_factory, message.owner_id)
            if recipient is None:
                # The account was deleted between the scan and now. The reminder
                # row is gone too (owner_id cascades), so this is only reachable
                # for a message already in flight — there is nobody to mail and
                # nothing to update.
                raise UndeliverableReminder(f"no user for owner {message.owner_id}")

            await deliver(message, recipient)
        except UndeliverableReminder:
            logger.exception(
                "reminder %s is permanently undeliverable", message.reminder_id
            )
            async with session_factory() as session:
                async with session.begin():
                    await ReminderDispatchService(session).mark_failed(
                        message.reminder_id
                    )
            return

        async with session_factory() as session:
            async with session.begin():
                closed = await ReminderDispatchService(session).mark_delivered(
                    message.reminder_id
                )

        if closed:
            logger.info("delivered reminder %s", message.reminder_id)
        else:
            # The update is scoped to `queued`, so this means the row had already
            # moved on — a redelivery of something already handled. Acking it and
            # doing nothing is the correct response, and is exactly the
            # idempotency the at-least-once scanner requires.
            logger.info(
                "reminder %s was already closed out, ignoring redelivery",
                message.reminder_id,
            )


async def _consume_until_stopped(messages, session_factory, stopping) -> None:
    """Consume messages until SIGTERM, without hanging on an idle queue.

    The obvious `async for raw in messages` cannot be shut down: it blocks inside
    `__anext__` waiting for the next delivery, so on a quiet queue — which is the
    normal state, since reminders arrive in bursts — nothing ever wakes it to
    notice the stop flag. The process then sits there until Docker gives up
    waiting and SIGKILLs it, which is both slow and an unclean exit.

    So each fetch is raced against the stop event. Only the *waiting* fetch is
    ever cancelled; a message already being handled runs to completion, which is
    what stops a shutdown from tearing down a half-finished delivery.
    """
    stopper = asyncio.ensure_future(stopping.wait())

    try:
        while not stopping.is_set():
            fetch = asyncio.ensure_future(messages.__anext__())
            done, _ = await asyncio.wait(
                {fetch, stopper}, return_when=asyncio.FIRST_COMPLETED
            )

            if fetch not in done:
                fetch.cancel()
                logger.info("stop requested while idle")
                return

            try:
                raw = fetch.result()
            except StopAsyncIteration:
                return

            await handle(raw, session_factory)

        logger.info("stop requested, finished in-flight message")
    finally:
        stopper.cancel()


async def run() -> None:
    stopping = install_signal_handlers()
    session_factory = admin_session_factory()

    # Said once at boot rather than only on the first delivery. Without this, a
    # misconfigured notifier looks perfectly healthy right up until a reminder
    # comes due, which could be hours later.
    if email_settings.configured:
        logger.info(
            "mail via %s:%d as %s, from %s",
            email_settings.MAIL_SERVER,
            email_settings.MAIL_PORT,
            email_settings.MAIL_USERNAME,
            email_settings.MAIL_FROM,
        )
    else:
        logger.error(
            "MAIL_USERNAME/MAIL_PASSWORD are not set — every delivery will fail "
            "until they are"
        )

    connection = await connect()
    channel = await connection.channel()

    # Without a prefetch limit RabbitMQ hands the entire backlog to whichever
    # consumer connects first, so extra replicas sit idle while one works through
    # everything.
    await channel.set_qos(prefetch_count=broker_settings.REMINDER_PREFETCH)
    _, queue = await declare_topology(channel)

    logger.info(
        "consuming %s (prefetch %d)",
        broker_settings.REMINDER_QUEUE,
        broker_settings.REMINDER_PREFETCH,
    )

    try:
        async with queue.iterator() as messages:
            await _consume_until_stopped(messages, session_factory, stopping)
    finally:
        logger.info("shutting down")
        await connection.close()
        await dispose_admin_engine()


if __name__ == "__main__":
    asyncio.run(run())
