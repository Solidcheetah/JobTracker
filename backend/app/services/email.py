"""SMTP delivery.

Wraps `aiosmtplib` with one job: send a message, and be precise about whether a
failure is worth retrying. That distinction is the whole reason this is not three
inline lines in the notifier — the reminder state machine treats the two cases
completely differently, so getting the classification wrong either burns a
reminder that would have gone out on the next attempt, or retries something that
will be refused every time.

The rule is SMTP's own: a 4xx reply means try later, a 5xx means do not. Two
exceptions to that, both deliberate, are documented in `_classify`.
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import email_settings

logger = logging.getLogger(__name__)


class EmailRejected(Exception):
    """The server refused the message and sending it again will not help.

    Raised for a bad recipient or any other permanent (5xx) refusal. Transient
    problems are *not* wrapped in this — they propagate as the original
    `aiosmtplib` error so the caller can retry them.
    """


class EmailNotConfigured(Exception):
    """No SMTP credentials are set, so nothing can be sent."""


def build_message(
    *, to: str, subject: str, text_body: str, html_body: str | None = None
) -> EmailMessage:
    """Assemble the MIME message.

    Split out from sending so tests can assert on headers and bodies without a
    server, and so a caller can inspect what would go out.
    """
    message = EmailMessage()
    message["From"] = f"{email_settings.MAIL_FROM_NAME} <{email_settings.MAIL_FROM}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)

    # A plain-text alternative always goes first, so a client that cannot render
    # HTML still shows something readable rather than markup.
    if html_body:
        message.add_alternative(html_body, subtype="html")

    return message


def _classify(error: Exception) -> Exception:
    """Decide whether `error` is permanent, returning what to raise.

    Returns an `EmailRejected` for permanent failures and the original error for
    transient ones, rather than raising, so the call site reads as a single
    `raise _classify(err) from err`.
    """
    # A refused recipient is the one unambiguously permanent case: the address is
    # wrong and no amount of retrying will make it right.
    if isinstance(error, aiosmtplib.SMTPRecipientsRefused):
        return EmailRejected(f"recipient refused: {error}")

    # Authentication failures come back as 5xx, which by the general rule below
    # would make them permanent — and that is the wrong call. Bad credentials are
    # an operator mistake affecting *every* reminder, so treating them as
    # permanent would quietly mark the whole backlog `failed` with no way back.
    # Transient means they retry, stay noisy in the logs, and recover once the
    # credentials are fixed.
    if isinstance(error, aiosmtplib.SMTPAuthenticationError):
        return error

    # Same reasoning for a refused sender: that is `MAIL_FROM` being wrong, which
    # is configuration, not the reminder's fault.
    if isinstance(error, aiosmtplib.SMTPSenderRefused):
        return error

    if isinstance(error, aiosmtplib.SMTPResponseException):
        if 500 <= error.code < 600:
            return EmailRejected(f"server refused the message ({error.code}): {error}")
        return error

    # Connection errors, timeouts, disconnects: all worth another go.
    return error


async def send_email(
    *, to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    """Send one message, raising `EmailRejected` only for permanent failures.

    Opens a connection per message. That is a real cost, but a reminder send is
    infrequent and bursty, and a pooled long-lived SMTP connection would need its
    own health checking and reconnection logic to survive the idle gaps between
    bursts. Worth revisiting if volume ever justifies it.
    """
    if not email_settings.configured:
        raise EmailNotConfigured(
            "MAIL_SERVER, MAIL_USERNAME and MAIL_PASSWORD must all be set"
        )

    message = build_message(
        to=to, subject=subject, text_body=text_body, html_body=html_body
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=email_settings.MAIL_SERVER,
            port=email_settings.MAIL_PORT,
            username=email_settings.MAIL_USERNAME,
            password=email_settings.MAIL_PASSWORD,
            start_tls=email_settings.MAIL_START_TLS,
            use_tls=email_settings.MAIL_SSL_TLS,
            timeout=email_settings.MAIL_TIMEOUT,
        )
    except Exception as error:
        raise _classify(error) from error

    logger.info("sent mail to %s: %s", to, subject)
