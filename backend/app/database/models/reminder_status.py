from enum import Enum


class ReminderStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    delivered = "delivered"
    failed = "failed"
    cancelled = "cancelled"
