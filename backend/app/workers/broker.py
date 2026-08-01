"""RabbitMQ connection, topology and message shape for reminder delivery.

Both the scanner and the notifier declare the full topology on startup. Declaring
is idempotent in AMQP, and doing it from both sides means neither process depends
on the other having booted first — whichever arrives first creates the exchange
and queue, and the second finds them already there.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import aio_pika
from aio_pika.abc import (
    AbstractIncomingMessage,
    AbstractRobustChannel,
    AbstractRobustConnection,
    AbstractRobustExchange,
    AbstractRobustQueue,
)

from app.config import broker_settings

logger = logging.getLogger(__name__)

DEAD_LETTER_EXCHANGE = f"{broker_settings.REMINDER_EXCHANGE}.dlx"
DEAD_LETTER_QUEUE = f"{broker_settings.REMINDER_QUEUE}.dead"


@dataclass(frozen=True)
class ReminderMessage:
    """The delivery payload.

    Carries the reminder's content rather than just its id so the notifier can do
    its job with one message and no database read. `attempt` is included mainly so
    logs can distinguish a first delivery from a retry.
    """

    reminder_id: UUID
    owner_id: UUID
    content: str
    remind_at: datetime
    attempt: int

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "reminder_id": str(self.reminder_id),
                "owner_id": str(self.owner_id),
                "content": self.content,
                "remind_at": self.remind_at.isoformat(),
                "attempt": self.attempt,
            }
        ).encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ReminderMessage":
        data = json.loads(raw)
        return cls(
            reminder_id=UUID(data["reminder_id"]),
            owner_id=UUID(data["owner_id"]),
            content=data["content"],
            remind_at=datetime.fromisoformat(data["remind_at"]),
            attempt=int(data["attempt"]),
        )


async def connect() -> AbstractRobustConnection:
    """Open a connection that reconnects on its own.

    `connect_robust` is doing real work here: RabbitMQ and these workers start at
    the same time under compose, and the broker is routinely not accepting
    connections yet when the first attempt lands. A plain `connect` would crash
    the process on boot and rely on the restart policy to paper over it.
    """
    return await aio_pika.connect_robust(broker_settings.RABBITMQ_URL)


async def declare_topology(
    channel: AbstractRobustChannel,
) -> tuple[AbstractRobustExchange, AbstractRobustQueue]:
    """Create the exchange, the work queue, and the dead-letter path behind it."""

    # Anything the notifier rejects lands here instead of vanishing. Without a
    # dead-letter path, a message that always fails to parse is either lost on
    # first reject or requeued forever — both bad, in different ways.
    dlx = await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True
    )
    dead_queue = await channel.declare_queue(DEAD_LETTER_QUEUE, durable=True)
    await dead_queue.bind(dlx)

    exchange = await channel.declare_exchange(
        broker_settings.REMINDER_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True
    )
    queue = await channel.declare_queue(
        broker_settings.REMINDER_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE},
    )
    await queue.bind(exchange, routing_key=broker_settings.REMINDER_ROUTING_KEY)

    return exchange, queue


async def publish(exchange: AbstractRobustExchange, message: ReminderMessage) -> None:
    """Send one reminder to the queue, durably.

    Two settings matter for not losing reminders. PERSISTENT writes the message to
    disk so a broker restart does not drop the queue. And the channel is opened
    with publisher confirms, which makes this `await` mean "the broker has it"
    rather than "it left the socket" — without that, a publish can be reported
    successful into a void.

    `message_id` is the reminder's own id. RabbitMQ does not deduplicate on it,
    but it gives the consumer a stable key for recognising a redelivery.
    """
    await exchange.publish(
        aio_pika.Message(
            body=message.to_bytes(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(message.reminder_id),
        ),
        routing_key=broker_settings.REMINDER_ROUTING_KEY,
    )


def parse(raw: AbstractIncomingMessage) -> ReminderMessage:
    return ReminderMessage.from_bytes(raw.body)
