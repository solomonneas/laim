"""
LAIM - Lab Asset Inventory Manager
Background Task Scheduler for device sync operations
"""

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import AsyncSessionLocal
from app.integrations.sync import DeviceSyncService

logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler()


def get_sync_interval_hours() -> int:
    """Get sync interval from environment variable."""
    try:
        return int(os.getenv("SYNC_INTERVAL_HOURS", "6"))
    except ValueError:
        return 6


def is_sync_enabled() -> bool:
    """Check if sync is enabled from environment variable."""
    return os.getenv("SYNC_ENABLED", "true").lower() in ("true", "1", "yes")


async def run_scheduled_sync():
    """
    Execute scheduled device sync from all sources.

    This function is called by APScheduler at the configured interval.
    """
    logger.info("Starting scheduled device sync...")

    try:
        async with AsyncSessionLocal() as db:
            service = DeviceSyncService(db)
            sync_log, result = await service.sync_all()

            logger.info(
                f"Scheduled sync completed: "
                f"found={result.devices_found}, "
                f"created={result.created}, "
                f"updated={result.updated}, "
                f"skipped={result.skipped}, "
                f"errors={len(result.errors)}"
            )

    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")


def start_scheduler():
    """
    Start the background scheduler for device sync.

    The scheduler runs at the interval specified by SYNC_INTERVAL_HOURS
    environment variable (default: 6 hours).
    """
    if not is_sync_enabled():
        logger.info("Device sync is disabled (SYNC_ENABLED=false)")
        return

    interval_hours = get_sync_interval_hours()

    scheduler.add_job(
        run_scheduled_sync,
        IntervalTrigger(hours=interval_hours),
        id="device_sync",
        name="Device Sync from Netdisco/LibreNMS",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started - sync will run every {interval_hours} hours")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def trigger_sync_now():
    """
    Trigger an immediate sync (bypasses scheduler interval).

    Returns:
        Tuple of (SyncLog, SyncResult)
    """
    logger.info("Manual sync triggered")
    async with AsyncSessionLocal() as db:
        service = DeviceSyncService(db)
        return await service.sync_all()
