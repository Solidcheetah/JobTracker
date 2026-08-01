from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import db_settings

engine = create_async_engine(
    url=db_settings.POSTGRES_URL,
    echo=True,
    pool_size=db_settings.POSTGRES_POOL_SIZE,
    pool_pre_ping=db_settings.POSTGRES_POOL_PRE_PING,
)

_session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def user_scoped_session(user_id: UUID):
    async with _session_factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            yield session


# Background workers deliberately connect as the admin role. Every table the API
# touches has FORCE ROW LEVEL SECURITY with a policy keyed on
# `app.current_user_id`, and a scanner works across all owners, so it has no
# single user id to set. Connecting as the app role instead would not error — the
# policy would simply match nothing and every scan would report zero due
# reminders, which is the quietest possible way for this to break.
#
# Built lazily so importing this module does not open a pool in the API process,
# which has no use for it.
_admin_engine = None
_admin_session_factory = None


def admin_session_factory():
    global _admin_engine, _admin_session_factory

    if _admin_session_factory is None:
        _admin_engine = create_async_engine(
            url=db_settings.POSTGRES_ADMIN_URL,
            pool_size=db_settings.POSTGRES_POOL_SIZE,
            pool_pre_ping=db_settings.POSTGRES_POOL_PRE_PING,
        )
        _admin_session_factory = sessionmaker(
            bind=_admin_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _admin_session_factory


async def dispose_admin_engine():
    if _admin_engine is not None:
        await _admin_engine.dispose()
