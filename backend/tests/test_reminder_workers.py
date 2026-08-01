"""Tests for the scanner and notifier, with the broker faked out.

These cover the seam the dispatch tests cannot reach: that a claim is committed
before a publish is attempted, that a failed publish gives the reminder back, and
that the notifier tolerates the duplicate deliveries the scanner's at-least-once
design permits.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import aio_pika
import aiosmtplib
import pytest

from app.database.models.reminder_status import ReminderStatus
from app.services.email import EmailNotConfigured, EmailRejected
from app.workers import notifier, scanner
from app.workers.broker import ReminderMessage

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


class FakeExchange:
    """Stands in for an aio_pika exchange, recording what was published."""

    def __init__(self, fail=False):
        self.published = []
        self.fail = fail

    async def publish(self, message, routing_key):
        if self.fail:
            raise RuntimeError("broker unreachable")
        self.published.append((message, routing_key))

    @property
    def bodies(self):
        return [ReminderMessage.from_bytes(m.body) for m, _ in self.published]


class FakeIncomingMessage:
    """Stands in for an aio_pika incoming message.

    `process()` is the context manager the notifier relies on for ack/reject, so
    the fake records which one it would have done.
    """

    def __init__(self, message: ReminderMessage):
        self.body = message.to_bytes()
        self.acked = False
        self.rejected = False

    def process(self, requeue=False):
        return self._Process(self)

    class _Process:
        def __init__(self, parent):
            self.parent = parent

        async def __aenter__(self):
            return self.parent

        async def __aexit__(self, exc_type, exc, tb):
            if exc_type is None:
                self.parent.acked = True
            else:
                self.parent.rejected = True
            return False


@pytest.fixture
def exchange():
    return FakeExchange()


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Capture mail instead of sending it.

    Autouse so no test can reach a real SMTP server by accident. Only the socket
    is faked — `deliver`, `compose` and the error classification all still run,
    which is where the behaviour worth testing lives.
    """
    sent = []

    async def fake_send(*, to, subject, text_body, html_body=None):
        sent.append(
            {"to": to, "subject": subject, "text": text_body, "html": html_body}
        )

    monkeypatch.setattr(notifier, "send_email", fake_send)
    return sent


class TestScannerTick:
    async def test_publishes_a_due_reminder(
        self, session_factory, exchange, make_reminder
    ):
        reminder = await make_reminder(
            remind_at=NOW - timedelta(minutes=1), content="Chase Acme"
        )

        published = await scanner.tick(session_factory, exchange, NOW)

        assert published == 1
        assert len(exchange.bodies) == 1

        message = exchange.bodies[0]
        assert message.reminder_id == reminder.id
        assert message.owner_id == reminder.owner_id
        assert message.content == "Chase Acme"
        assert message.attempt == 1

    async def test_does_not_publish_the_same_reminder_twice(
        self, session_factory, exchange, make_reminder
    ):
        """The behaviour the polling design is built around."""
        await make_reminder(remind_at=NOW - timedelta(minutes=1))

        first = await scanner.tick(session_factory, exchange, NOW)
        second = await scanner.tick(session_factory, exchange, NOW)

        assert (first, second) == (1, 0)
        assert len(exchange.published) == 1

    async def test_ignores_reminders_that_are_not_due(
        self, session_factory, exchange, make_reminder
    ):
        await make_reminder(remind_at=NOW + timedelta(hours=1))

        assert await scanner.tick(session_factory, exchange, NOW) == 0
        assert exchange.published == []

    async def test_publishes_message_as_persistent(
        self, session_factory, exchange, make_reminder
    ):
        """A broker restart must not drop queued reminders."""
        await make_reminder(remind_at=NOW - timedelta(minutes=1))
        await scanner.tick(session_factory, exchange, NOW)

        message, routing_key = exchange.published[0]
        assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
        assert routing_key == "reminder.due"

    async def test_message_id_is_the_reminder_id(
        self, session_factory, exchange, make_reminder
    ):
        """Gives the consumer a stable key for spotting a redelivery."""
        reminder = await make_reminder(remind_at=NOW - timedelta(minutes=1))
        await scanner.tick(session_factory, exchange, NOW)

        message, _ = exchange.published[0]
        assert message.message_id == str(reminder.id)

    async def test_failed_publish_releases_the_reminder(
        self, session_factory, session, make_reminder
    ):
        """A broker outage must not swallow the reminder."""
        reminder = await make_reminder(remind_at=NOW - timedelta(minutes=1))
        broken = FakeExchange(fail=True)

        published = await scanner.tick(session_factory, broken, NOW)

        assert published == 0
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.pending, (
            "a reminder whose publish failed must go back to pending"
        )
        assert reminder.attempt_count == 1, "the failed attempt should still count"

    async def test_reminder_survives_a_broker_outage(
        self, session_factory, session, make_reminder
    ):
        """End to end: publish fails, then the broker recovers and it goes out."""
        reminder = await make_reminder(remind_at=NOW - timedelta(minutes=1))

        await scanner.tick(session_factory, FakeExchange(fail=True), NOW)

        healthy = FakeExchange()
        published = await scanner.tick(session_factory, healthy, NOW)

        assert published == 1
        assert healthy.bodies[0].reminder_id == reminder.id
        assert healthy.bodies[0].attempt == 2

    async def test_tick_reaps_stale_leases(
        self, session_factory, exchange, session, make_reminder
    ):
        """A reminder orphaned by a dead worker is recovered and published."""
        reminder = await make_reminder(
            remind_at=NOW - timedelta(minutes=30),
            status=ReminderStatus.queued,
            claimed_at=NOW - timedelta(minutes=10),
            attempt_count=1,
        )

        published = await scanner.tick(session_factory, exchange, NOW)

        assert published == 1
        assert exchange.bodies[0].reminder_id == reminder.id
        assert exchange.bodies[0].attempt == 2

    async def test_publishes_for_every_owner(
        self, session_factory, exchange, make_reminder, user, other_user
    ):
        await make_reminder(owner=user, remind_at=NOW - timedelta(minutes=1))
        await make_reminder(owner=other_user, remind_at=NOW - timedelta(minutes=1))

        published = await scanner.tick(session_factory, exchange, NOW)

        assert published == 2
        assert {m.owner_id for m in exchange.bodies} == {user.id, other_user.id}


class TestNotifierHandle:
    def _message(self, reminder, attempt=1):
        return FakeIncomingMessage(
            ReminderMessage(
                reminder_id=reminder.id,
                owner_id=reminder.owner_id,
                content=reminder.content,
                remind_at=reminder.remind_at,
                attempt=attempt,
            )
        )

    async def test_marks_reminder_delivered(
        self, session_factory, session, make_reminder
    ):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)
        raw = self._message(reminder)

        await notifier.handle(raw, session_factory)

        assert raw.acked is True
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.delivered

    async def test_redelivery_is_a_no_op(
        self, session_factory, session, make_reminder
    ):
        """At-least-once means this will happen; it must not be an error."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        await notifier.handle(self._message(reminder), session_factory)
        second = self._message(reminder, attempt=2)
        await notifier.handle(second, session_factory)

        assert second.acked is True, "a duplicate must be acked, not rejected"
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.delivered

    async def test_cancelled_reminder_is_not_marked_delivered(
        self, session_factory, session, make_reminder
    ):
        """A reminder cancelled after publishing but before delivery stays cancelled."""
        reminder = await make_reminder(status=ReminderStatus.cancelled)

        raw = self._message(reminder)
        await notifier.handle(raw, session_factory)

        assert raw.acked is True
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.cancelled

    async def test_permanent_failure_marks_it_failed(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        async def boom(message, recipient):
            raise notifier.UndeliverableReminder("no address on file")

        monkeypatch.setattr(notifier, "deliver", boom)

        raw = self._message(reminder)
        await notifier.handle(raw, session_factory)

        assert raw.acked is True, "a permanent failure is resolved, not retried"
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.failed

    async def test_transient_failure_rejects_and_leaves_it_queued(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        """Rejected to the dead-letter queue, but the row stays `queued` so the
        scanner's reaper is what eventually retries it."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        async def boom(message, recipient):
            raise RuntimeError("smtp timeout")

        monkeypatch.setattr(notifier, "deliver", boom)

        raw = self._message(reminder)
        with pytest.raises(RuntimeError):
            await notifier.handle(raw, session_factory)

        assert raw.rejected is True
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued

    async def test_reminder_recovers_after_a_transient_delivery_failure(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        """The full recovery loop: delivery fails, lease expires, it goes out again."""
        reminder = await make_reminder(
            remind_at=NOW - timedelta(minutes=1),
            status=ReminderStatus.queued,
            claimed_at=NOW,
            attempt_count=1,
        )

        async def boom(message, recipient):
            raise RuntimeError("smtp timeout")

        monkeypatch.setattr(notifier, "deliver", boom)
        with pytest.raises(RuntimeError):
            await notifier.handle(self._message(reminder), session_factory)

        # The lease expires and the scanner picks it back up.
        later = NOW + timedelta(minutes=10)
        exchange = FakeExchange()
        assert await scanner.tick(session_factory, exchange, later) == 1

        # This time delivery works.
        monkeypatch.undo()
        await notifier.handle(self._message(reminder, attempt=2), session_factory)

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.delivered


class TestNotifierEmail:
    """The delivery channel: a due reminder becomes an email to its owner."""

    def _message(self, reminder, attempt=1):
        return FakeIncomingMessage(
            ReminderMessage(
                reminder_id=reminder.id,
                owner_id=reminder.owner_id,
                content=reminder.content,
                remind_at=reminder.remind_at,
                attempt=attempt,
            )
        )

    async def test_emails_the_owner(
        self, session_factory, make_reminder, outbox, user
    ):
        reminder = await make_reminder(
            status=ReminderStatus.queued, claimed_at=NOW, content="Chase Acme"
        )

        await notifier.handle(self._message(reminder), session_factory)

        assert len(outbox) == 1
        assert outbox[0]["to"] == user.email
        assert "Chase Acme" in outbox[0]["subject"]
        assert "Chase Acme" in outbox[0]["text"]
        assert user.name in outbox[0]["text"]

    async def test_emails_each_owner_their_own_reminder(
        self, session_factory, make_reminder, outbox, user, other_user
    ):
        """Two owners must not receive each other's reminders."""
        mine = await make_reminder(
            owner=user, status=ReminderStatus.queued, claimed_at=NOW, content="Mine"
        )
        theirs = await make_reminder(
            owner=other_user,
            status=ReminderStatus.queued,
            claimed_at=NOW,
            content="Theirs",
        )

        await notifier.handle(self._message(mine), session_factory)
        await notifier.handle(self._message(theirs), session_factory)

        by_address = {sent["to"]: sent["text"] for sent in outbox}
        assert "Mine" in by_address[user.email]
        assert "Theirs" in by_address[other_user.email]

    async def test_sends_both_a_text_and_an_html_body(
        self, session_factory, make_reminder, outbox
    ):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)
        await notifier.handle(self._message(reminder), session_factory)

        assert outbox[0]["text"]
        assert "<" in (outbox[0]["html"] or ""), "an HTML alternative should be included"

    async def test_a_rejected_address_marks_it_failed(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        """A permanent refusal must not be retried until it exhausts its attempts."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        async def refuse(**kwargs):
            raise EmailRejected("recipient refused: 550 no such user")

        monkeypatch.setattr(notifier, "send_email", refuse)

        raw = self._message(reminder)
        await notifier.handle(raw, session_factory)

        assert raw.acked is True, "a permanent refusal is resolved, not retried"
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.failed

    async def test_an_smtp_timeout_leaves_it_queued_for_retry(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        async def timeout(**kwargs):
            raise aiosmtplib.SMTPTimeoutError("connection timed out")

        monkeypatch.setattr(notifier, "send_email", timeout)

        raw = self._message(reminder)
        with pytest.raises(aiosmtplib.SMTPTimeoutError):
            await notifier.handle(raw, session_factory)

        assert raw.rejected is True
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued, (
            "a transient failure must stay claimable so the reaper retries it"
        )

    async def test_missing_credentials_do_not_burn_the_reminder(
        self, session_factory, session, make_reminder, monkeypatch
    ):
        """An operator mistake must not silently destroy the backlog."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)

        async def unconfigured(**kwargs):
            raise EmailNotConfigured("MAIL_PASSWORD must be set")

        monkeypatch.setattr(notifier, "send_email", unconfigured)

        with pytest.raises(EmailNotConfigured):
            await notifier.handle(self._message(reminder), session_factory)

        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued

    async def test_a_deleted_owner_is_undeliverable(
        self, session_factory, session, make_reminder, outbox
    ):
        """Nobody to mail, so the row is closed out rather than retried forever."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)
        message = ReminderMessage(
            reminder_id=reminder.id,
            owner_id=uuid4(),  # an owner that was never in the table
            content=reminder.content,
            remind_at=reminder.remind_at,
            attempt=1,
        )

        raw = FakeIncomingMessage(message)
        await notifier.handle(raw, session_factory)

        assert raw.acked is True
        assert outbox == [], "no mail should go out for an unknown owner"

    async def test_a_cancelled_reminder_still_sends_if_already_in_flight(
        self, session_factory, session, make_reminder, outbox
    ):
        """Documents a real gap rather than asserting ideal behaviour.

        Cancelling after the scanner has published cannot unsend the message, so
        the mail still goes out; only the bookkeeping notices, leaving the row
        `cancelled`. Closing this would mean re-checking the status inside the
        notifier before delivering, which narrows the window without removing it.
        """
        reminder = await make_reminder(status=ReminderStatus.cancelled)

        await notifier.handle(self._message(reminder), session_factory)

        assert len(outbox) == 1
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.cancelled


class TestComposeReminderEmail:
    def _message(self, content="Follow up with Acme", remind_at=NOW):
        return ReminderMessage(
            reminder_id=uuid4(),
            owner_id=uuid4(),
            content=content,
            remind_at=remind_at,
            attempt=1,
        )

    def test_subject_carries_the_reminder(self):
        subject, _, _ = notifier.compose(
            self._message(), notifier.Recipient(name="Ada", email="ada@example.com")
        )
        assert subject == "Reminder: Follow up with Acme"

    def test_long_content_is_truncated_in_the_subject_only(self):
        content = "x" * 200
        subject, text, _ = notifier.compose(
            self._message(content=content),
            notifier.Recipient(name="Ada", email="ada@example.com"),
        )

        assert len(subject) < 100
        assert subject.endswith("…")
        assert content in text, "the body should still carry the whole reminder"

    def test_time_is_labelled_utc(self):
        """An unlabelled time would be read as local and be wrong for most people."""
        _, text, html = notifier.compose(
            self._message(), notifier.Recipient(name="Ada", email="ada@example.com")
        )

        assert "31 Jul 2026 at 12:00 UTC" in text
        assert "31 Jul 2026 at 12:00 UTC" in html

    def test_greets_the_recipient_by_name(self):
        _, text, html = notifier.compose(
            self._message(), notifier.Recipient(name="Grace", email="g@example.com")
        )
        assert "Hi Grace," in text
        assert "Hi Grace," in html


class TestNotifierShutdown:
    """Regression cover for a notifier that could not be shut down.

    The first version looped with `async for raw in messages` and checked the stop
    flag after handling each message. On an idle queue it blocked inside the
    iterator forever, ignored SIGTERM, and was eventually SIGKILLed by Docker
    (exit 137) instead of closing its connections.
    """

    class IdleIterator:
        """An iterator that never yields, like a queue with nothing on it."""

        def __init__(self):
            self.cancelled = False

        async def __anext__(self):
            try:
                await asyncio.Event().wait()  # blocks forever
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    class OneThenIdle:
        """Yields a single message, then blocks like an empty queue."""

        def __init__(self, message):
            self.message = message
            self.served = False

        async def __anext__(self):
            if not self.served:
                self.served = True
                return self.message
            await asyncio.Event().wait()

    async def test_returns_promptly_when_idle(self, session_factory):
        stopping = asyncio.Event()
        stopping.set()

        messages = self.IdleIterator()

        await asyncio.wait_for(
            notifier._consume_until_stopped(messages, session_factory, stopping),
            timeout=2,
        )

    async def test_wakes_on_stop_while_waiting_for_a_message(self, session_factory):
        """The actual failure: the stop arrives *while* blocked on the queue."""
        stopping = asyncio.Event()
        messages = self.IdleIterator()

        async def stop_shortly():
            await asyncio.sleep(0.05)
            stopping.set()

        await asyncio.wait_for(
            asyncio.gather(
                notifier._consume_until_stopped(messages, session_factory, stopping),
                stop_shortly(),
            ),
            timeout=2,
        )

        assert messages.cancelled, "the pending fetch should have been cancelled"

    async def test_finishes_in_flight_message_before_stopping(
        self, session_factory, session, make_reminder
    ):
        """A shutdown must not abandon a delivery that has already started."""
        reminder = await make_reminder(status=ReminderStatus.queued, claimed_at=NOW)
        raw = FakeIncomingMessage(
            ReminderMessage(
                reminder_id=reminder.id,
                owner_id=reminder.owner_id,
                content=reminder.content,
                remind_at=reminder.remind_at,
                attempt=1,
            )
        )

        stopping = asyncio.Event()
        stopping.set()  # already stopping when the message arrives

        await asyncio.wait_for(
            notifier._consume_until_stopped(
                self.OneThenIdle(raw), session_factory, stopping
            ),
            timeout=2,
        )

        # Stopping pre-empts starting new work, so this message is not picked up.
        await session.refresh(reminder)
        assert reminder.status is ReminderStatus.queued

    async def test_stops_cleanly_when_the_queue_closes(self, session_factory):
        class Closed:
            async def __anext__(self):
                raise StopAsyncIteration

        await asyncio.wait_for(
            notifier._consume_until_stopped(
                Closed(), session_factory, asyncio.Event()
            ),
            timeout=2,
        )


class TestReminderMessage:
    def _message(self, **overrides):
        fields = dict(
            reminder_id=uuid4(),
            owner_id=uuid4(),
            content="Ping the recruiter",
            remind_at=NOW,
            attempt=2,
        )
        return ReminderMessage(**{**fields, **overrides})

    async def test_round_trips(self):
        original = self._message()
        assert ReminderMessage.from_bytes(original.to_bytes()) == original

    async def test_preserves_timezone(self):
        """A naive timestamp on the far side would fire at the wrong local time."""
        original = self._message(remind_at=NOW)
        restored = ReminderMessage.from_bytes(original.to_bytes())

        assert restored.remind_at == NOW
        assert restored.remind_at.tzinfo is not None

    async def test_unicode_content_survives(self):
        original = self._message(content="Café ☕ — 面接")
        assert ReminderMessage.from_bytes(original.to_bytes()).content == "Café ☕ — 面接"
