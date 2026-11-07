"""Dedicated background worker: python -m backend.worker"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from backend.config import settings
from backend.db import session_scope
from backend.logging_setup import configure_logging
from backend.scheduler import configure
from backend.sources.registry import sync_registry


def main() -> None:
    configure_logging()
    settings.validate()
    with session_scope() as db:
        logging.getLogger("detectivepm.worker").info("registry synced: %s", sync_registry(db))
    scheduler = BlockingScheduler(timezone="UTC")
    configure(scheduler)
    scheduler.start()


if __name__ == "__main__":
    main()
