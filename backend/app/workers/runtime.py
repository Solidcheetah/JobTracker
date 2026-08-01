"""Shared process plumbing for the standalone workers."""

import asyncio
import logging
import signal


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{name}] %(levelname)s %(name)s: %(message)s",
    )
    # The API's engine is created with echo=True, which would put every statement
    # this process runs into the log at INFO. Fine for a request handler you are
    # debugging, unreadable for a loop that runs forever.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    return logging.getLogger(name)


def install_signal_handlers() -> asyncio.Event:
    """Return an Event that is set when the process is asked to stop.

    Docker sends SIGTERM and then waits before escalating to SIGKILL. Catching it
    lets a scan in progress finish and its claims commit; without this the process
    dies mid-tick and leaves rows in `queued` for the reaper to clean up minutes
    later, which shows up as reminders that arrive late for no visible reason.
    """
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:  # pragma: no cover - Windows
            signal.signal(sig, lambda *_: stopping.set())

    return stopping


async def sleep_or_stop(stopping: asyncio.Event, seconds: float) -> None:
    """Wait out the poll interval, but wake immediately on shutdown.

    A plain `asyncio.sleep` would make shutdown take up to a full interval.
    """
    try:
        await asyncio.wait_for(stopping.wait(), timeout=seconds)
    except (asyncio.TimeoutError, TimeoutError):
        pass
