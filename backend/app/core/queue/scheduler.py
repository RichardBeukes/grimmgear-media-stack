"""
GrimmGear Mediarr — Background Scheduler
Runs periodic tasks: import scan, RSS sync, missing search.
No external task queue needed — uses asyncio.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("grimmgear.scheduler")


class Scheduler:
    """Background task scheduler using asyncio."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self.last_import_scan: str = "never"
        self.last_rss_sync: str = "never"

    async def start(self):
        """Start all background tasks."""
        if self._running:
            return
        self._running = True
        logger.info("Scheduler starting...")

        self._tasks["import_scan"] = asyncio.create_task(self._import_scan_loop())
        self._tasks["speed_log"] = asyncio.create_task(self._speed_log_loop())

        logger.info(f"Scheduler started with {len(self._tasks)} tasks")

    async def stop(self):
        """Stop all background tasks."""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def _import_scan_loop(self):
        """Scan for completed downloads every 60 seconds."""
        from app.core.import_pipeline import import_pipeline

        while self._running:
            try:
                await asyncio.sleep(60)  # Wait 60s between scans
                result = await import_pipeline.scan_and_import()
                self.last_import_scan = datetime.utcnow().isoformat()
                if result.get("imported", 0) > 0:
                    logger.info(f"Import scan: {result['imported']} imported, {result['rejected']} rejected")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Import scan error: {e}")
                await asyncio.sleep(30)

    async def _speed_log_loop(self):
        """Log download speed periodically (every 5 minutes)."""
        from app.core.download import qbit

        while self._running:
            try:
                await asyncio.sleep(300)
                info = await qbit.get_transfer_info()
                dl = info.get("dl_info_speed", 0) / 1048576
                ul = info.get("up_info_speed", 0) / 1048576
                if dl > 0:
                    logger.info(f"Transfer: DL {dl:.1f} MB/s | UL {ul:.1f} MB/s")
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "tasks": list(self._tasks.keys()),
            "last_import_scan": self.last_import_scan,
            "last_rss_sync": self.last_rss_sync,
        }


# Singleton
scheduler = Scheduler()
