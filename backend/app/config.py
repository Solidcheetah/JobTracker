from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_base_config = SettingsConfigDict(
    env_file="./.env", env_ignore_empty=True, extra="ignore"
)


class DatabaseSettings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_ADMIN_USER: str
    POSTGRES_ADMIN_PASSWORD: str
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_POOL_PRE_PING: bool = True

    REDIS_HOST: str
    REDIS_PORT: int

    model_config = _base_config

    def _url(self, user: str, password: str, db: str) -> str:
        return f"postgresql+asyncpg://{user}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{db}"

    @property
    def POSTGRES_URL(self) -> str:
        return self._url(self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_DB)

    @property
    def POSTGRES_ADMIN_URL(self) -> str:
        return self._url(
            self.POSTGRES_ADMIN_USER, self.POSTGRES_ADMIN_PASSWORD, self.POSTGRES_DB
        )


class SecuritySettings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    model_config = _base_config


class BrokerSettings(BaseSettings):
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"

    REMINDER_EXCHANGE: str = "reminders"
    REMINDER_QUEUE: str = "reminders.notify"
    REMINDER_ROUTING_KEY: str = "reminder.due"

    # How many messages one notifier holds at a time. Without this, RabbitMQ
    # pushes the whole queue at the first consumer to connect and the other
    # replicas sit idle.
    REMINDER_PREFETCH: int = 10

    model_config = _base_config

    @property
    def RABBITMQ_URL(self) -> str:
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
        )


class ReminderWorkerSettings(BaseSettings):
    # Seconds between scans. This is also the worst-case lateness of a reminder,
    # since a row that comes due just after a scan waits for the next one.
    REMINDER_POLL_INTERVAL: float = 10.0

    # Rows claimed per scan. Caps how much one tick can lose if the process dies
    # mid-publish, and keeps the claiming UPDATE short.
    REMINDER_BATCH_SIZE: int = 100

    # How long a claim is honoured before a reaper assumes the claimer died.
    # Must comfortably exceed the time to publish one batch, or the reaper will
    # yank rows out from under a scanner that is still working.
    REMINDER_LEASE_SECONDS: int = 120

    # Claims per reminder before it is abandoned as failed.
    REMINDER_MAX_ATTEMPTS: int = 5

    model_config = _base_config


class EmailSettings(BaseSettings):
    MAIL_SERVER: str = "sandbox.smtp.mailtrap.io"
    MAIL_PORT: int = 2525
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "reminders@jobtracker.local"
    MAIL_FROM_NAME: str = "JobTracker"

    # STARTTLS on the submission ports (587, 2525); implicit TLS only on 465.
    # Setting both is a configuration error — they are different handshakes.
    MAIL_START_TLS: bool = True
    MAIL_SSL_TLS: bool = False

    # Bounds how long one delivery can hold a notifier slot. Comfortably under
    # REMINDER_LEASE_SECONDS so a slow provider cannot outlast the lease.
    MAIL_TIMEOUT: float = 20.0

    model_config = _base_config

    @property
    def configured(self) -> bool:
        """Whether there is enough here to attempt a send at all."""
        return bool(self.MAIL_SERVER and self.MAIL_USERNAME and self.MAIL_PASSWORD)


db_settings = DatabaseSettings()
security_settings = SecuritySettings()
broker_settings = BrokerSettings()
reminder_worker_settings = ReminderWorkerSettings()
email_settings = EmailSettings()
