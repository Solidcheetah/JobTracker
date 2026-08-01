"""Tests for the SMTP layer.

The interesting behaviour here is not "does it send" — that is `aiosmtplib`'s job —
but the classification of failures. Getting it wrong is expensive in both
directions: a permanent error treated as transient wastes a reminder's whole retry
budget, and a transient error treated as permanent destroys a reminder that would
have gone out a minute later.
"""

import aiosmtplib
import pytest

from app.config import email_settings
from app.services.email import (
    EmailNotConfigured,
    EmailRejected,
    _classify,
    build_message,
    send_email,
)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(email_settings, "MAIL_SERVER", "smtp.example.com")
    monkeypatch.setattr(email_settings, "MAIL_USERNAME", "user")
    monkeypatch.setattr(email_settings, "MAIL_PASSWORD", "secret")
    monkeypatch.setattr(email_settings, "MAIL_FROM", "reminders@example.com")
    monkeypatch.setattr(email_settings, "MAIL_FROM_NAME", "JobTracker")


class TestBuildMessage:
    def test_sets_the_headers(self, configured):
        message = build_message(
            to="ada@example.com", subject="Reminder: ping", text_body="body"
        )

        assert message["To"] == "ada@example.com"
        assert message["Subject"] == "Reminder: ping"
        assert message["From"] == "JobTracker <reminders@example.com>"

    def test_text_only_is_not_multipart(self, configured):
        message = build_message(to="a@b.com", subject="s", text_body="just text")

        assert message.is_multipart() is False
        assert "just text" in message.get_content()

    def test_html_is_added_as_an_alternative(self, configured):
        """Text must come first so a plain-text client shows prose, not markup."""
        message = build_message(
            to="a@b.com", subject="s", text_body="plain", html_body="<p>rich</p>"
        )

        assert message.is_multipart() is True
        subtypes = [part.get_content_subtype() for part in message.iter_parts()]
        assert subtypes == ["plain", "html"]

    def test_unicode_survives(self, configured):
        message = build_message(
            to="a@b.com", subject="Reminder: café ☕", text_body="面接 at 3pm"
        )

        assert "café ☕" in str(message["Subject"])
        assert "面接" in message.get_content()


class TestClassify:
    def test_a_refused_recipient_is_permanent(self):
        error = aiosmtplib.SMTPRecipientsRefused([])
        assert isinstance(_classify(error), EmailRejected)

    def test_a_5xx_reply_is_permanent(self):
        error = aiosmtplib.SMTPResponseException(550, "mailbox unavailable")
        assert isinstance(_classify(error), EmailRejected)

    def test_a_4xx_reply_is_transient(self):
        """451/452 mean the server is asking us to come back later."""
        error = aiosmtplib.SMTPResponseException(451, "try again later")
        assert _classify(error) is error

    def test_bad_credentials_are_transient(self):
        """A 5xx, but an operator mistake — retrying keeps it recoverable.

        If this were permanent, wrong credentials would mark every reminder in the
        backlog `failed` with no way to get them back.
        """
        error = aiosmtplib.SMTPAuthenticationError(535, "authentication failed")
        assert _classify(error) is error

    def test_a_refused_sender_is_transient(self):
        """Also configuration — a wrong MAIL_FROM, not a bad reminder."""
        error = aiosmtplib.SMTPSenderRefused(553, "sender rejected", "bad@from")
        assert _classify(error) is error

    def test_a_timeout_is_transient(self):
        error = aiosmtplib.SMTPTimeoutError("timed out")
        assert _classify(error) is error

    def test_a_connection_failure_is_transient(self):
        error = aiosmtplib.SMTPConnectError("connection refused")
        assert _classify(error) is error

    def test_an_unexpected_error_is_transient(self):
        """Unknown failures get the benefit of the doubt rather than a dead row."""
        error = RuntimeError("something else went wrong")
        assert _classify(error) is error


class TestSendEmail:
    async def test_refuses_to_send_with_no_credentials(self, monkeypatch):
        monkeypatch.setattr(email_settings, "MAIL_USERNAME", "")
        monkeypatch.setattr(email_settings, "MAIL_PASSWORD", "")

        with pytest.raises(EmailNotConfigured):
            await send_email(to="a@b.com", subject="s", text_body="b")

    async def test_passes_the_connection_settings_through(self, configured, monkeypatch):
        captured = {}

        async def fake_send(message, **kwargs):
            captured["message"] = message
            captured.update(kwargs)

        monkeypatch.setattr(aiosmtplib, "send", fake_send)
        monkeypatch.setattr(email_settings, "MAIL_PORT", 2525)
        monkeypatch.setattr(email_settings, "MAIL_START_TLS", True)
        monkeypatch.setattr(email_settings, "MAIL_SSL_TLS", False)

        await send_email(to="ada@example.com", subject="s", text_body="b")

        assert captured["hostname"] == "smtp.example.com"
        assert captured["port"] == 2525
        assert captured["username"] == "user"
        assert captured["start_tls"] is True
        assert captured["use_tls"] is False
        assert captured["message"]["To"] == "ada@example.com"

    async def test_wraps_a_permanent_failure(self, configured, monkeypatch):
        async def fake_send(message, **kwargs):
            raise aiosmtplib.SMTPResponseException(550, "mailbox unavailable")

        monkeypatch.setattr(aiosmtplib, "send", fake_send)

        with pytest.raises(EmailRejected):
            await send_email(to="a@b.com", subject="s", text_body="b")

    async def test_lets_a_transient_failure_through_unchanged(
        self, configured, monkeypatch
    ):
        async def fake_send(message, **kwargs):
            raise aiosmtplib.SMTPTimeoutError("timed out")

        monkeypatch.setattr(aiosmtplib, "send", fake_send)

        with pytest.raises(aiosmtplib.SMTPTimeoutError):
            await send_email(to="a@b.com", subject="s", text_body="b")
