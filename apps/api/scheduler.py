from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.api.dependencies import get_config

logger = logging.getLogger(__name__)


def create_scheduler(scan_callback) -> AsyncIOScheduler:  # type: ignore[type-arg]
    """Create an APScheduler that triggers scans on US trading days."""
    config = get_config()
    scheduler = AsyncIOScheduler()

    if config.schedule.mode == "market_close_plus":
        # Schedule at fixed Israel time or minutes after close
        hour, minute = map(int, config.schedule.fixed_time_israel.split(":"))

        scheduler.add_job(
            _maybe_run_scan,
            "cron",
            hour=hour,
            minute=minute,
            timezone="Asia/Jerusalem",
            args=[scan_callback],
            id="daily_scan",
            name="Daily market scan",
        )

    return scheduler


async def _maybe_run_scan(scan_callback) -> None:  # type: ignore[type-arg]
    """Run scan only on US trading days."""
    config = get_config()

    if config.schedule.only_us_trading_days:
        try:
            import pandas_market_calendars as mcal

            nyse = mcal.get_calendar("NYSE")
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = nyse.schedule(start_date=today, end_date=today)
            if schedule.empty:
                logger.info("Not a US trading day, skipping scan")
                return
        except Exception:
            logger.warning("Market calendar check failed, running scan anyway", exc_info=True)

    logger.info("Triggering scheduled scan")
    await scan_callback()
