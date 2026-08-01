"""Shared fixtures.

Tests run against an in-memory SQLite database so the suite needs no
Postgres or Redis. Two consequences are worth knowing:

- Row-level security is a Postgres feature, so the ``application_owner_isolation``
  policy is not active here. Ownership tests therefore assert on the checks the
  service layer makes itself, which is the layer we can exercise portably.
- ``get_db`` normally opens a user-scoped session that sets
  ``app.current_user_id``. It is overridden with a plain session.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

import app.database.models  # noqa: F401  (registers tables on SQLModel.metadata)
from app.database.models import Application, Reminder, User
from app.database.models.reminder_status import ReminderStatus
from app.main import app as fastapi_app
from app.routers.dependencies.auth import get_current_user, get_db, get_session
from app.services.application import ApplicationService
from app.services.user import UserService, password_hasher


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncSession:
    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def user(session) -> User:
    user = User(
        id=uuid4(),
        name="Ada",
        email="ada@example.com",
        password_hash=password_hasher.hash("correct-horse"),
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def other_user(session) -> User:
    user = User(
        id=uuid4(),
        name="Grace",
        email="grace@example.com",
        password_hash=password_hasher.hash("battery-staple"),
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
def service(session, user) -> ApplicationService:
    return ApplicationService(session, user.id)


@pytest.fixture
def other_service(session, other_user) -> ApplicationService:
    return ApplicationService(session, other_user.id)


@pytest.fixture
def user_service(session) -> UserService:
    return UserService(session)


@pytest.fixture
def make_application(session, user):
    """Insert an application directly, bypassing the service layer."""

    async def _make(
        owner=None,
        company="Acme",
        role="Engineer",
        status="applied",
        applied_at=None,
        note=None,
        source_url=None,
    ):
        application = Application(
            id=uuid4(),
            owner_id=owner.id if owner is not None else user.id,
            company=company,
            role=role,
            status=status,
            note=note,
            source_url=source_url,
            applied_at=applied_at or date(2026, 6, 1),
        )
        session.add(application)
        await session.commit()
        return application

    return _make


@pytest.fixture
def session_factory(engine):
    """A factory rather than a session, for code that opens its own.

    The workers manage their own session lifetimes — they are not request-scoped
    and have no dependency injection to hook — so they take a factory. This one is
    bound to the same in-memory engine as the `session` fixture, so rows inserted
    through either are visible to both.
    """
    return sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def make_reminder(session, user):
    """Insert a reminder directly, bypassing the service layer.

    Takes `status`, `attempt_count` and `claimed_at` because the worker tests need
    to set up states the API refuses to create — a half-delivered reminder, or one
    whose lease went stale.
    """

    async def _make(
        owner=None,
        content="Follow up",
        remind_at=None,
        status=ReminderStatus.pending,
        attempt_count=0,
        claimed_at=None,
    ):
        reminder = Reminder(
            id=uuid4(),
            owner_id=owner.id if owner is not None else user.id,
            content=content,
            remind_at=remind_at or (datetime.now(timezone.utc) + timedelta(hours=1)),
            status=status,
            attempt_count=attempt_count,
            claimed_at=claimed_at,
        )
        session.add(reminder)
        await session.commit()
        return reminder

    return _make


@pytest.fixture
async def client(session, user):
    """HTTP client with the DB and the authenticated user overridden."""
    fastapi_app.dependency_overrides[get_db] = lambda: session
    fastapi_app.dependency_overrides[get_session] = lambda: session
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.id

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def anon_client(session):
    """HTTP client with no authenticated user, for auth-failure paths."""
    fastapi_app.dependency_overrides[get_session] = lambda: session

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def today() -> date:
    return date(2026, 6, 15)


@pytest.fixture
def days_ago(today):
    def _days_ago(n: int) -> date:
        return today - timedelta(days=n)

    return _days_ago
