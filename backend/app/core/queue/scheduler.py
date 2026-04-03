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
        self._tasks["rss_sync"] = asyncio.create_task(self._rss_sync_loop())
        self._tasks["plex_notify"] = asyncio.create_task(self._plex_notify_loop())

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

    async def _rss_sync_loop(self):
        """Search indexers for monitored movies/series that are missing files. Every 15 minutes."""
        from sqlalchemy import select
        from app.db.session import async_session_factory
        from app.db.models import Movie, Series, Indexer
        from app.core.search.indexer_search import indexer_engine
        from app.core.decision.engine import decision_engine
        from app.core.download.qbit_client import qbit

        while self._running:
            try:
                await asyncio.sleep(900)  # 15 minutes
                async with async_session_factory() as db:
                    # Get wanted movies (monitored, no file)
                    result = await db.execute(
                        select(Movie).where(Movie.monitored == True, Movie.has_file == False)
                    )
                    wanted_movies = result.scalars().all()

                    # Get indexers
                    idx_result = await db.execute(select(Indexer).where(Indexer.enabled == True))
                    indexers = [
                        {"name": i.name, "url": i.url, "api_key": i.api_key, "enabled": True, "indexer_type": i.indexer_type}
                        for i in idx_result.scalars().all()
                    ]

                    if not indexers or not wanted_movies:
                        self.last_rss_sync = datetime.utcnow().isoformat()
                        continue

                    grabbed = 0
                    for movie in wanted_movies[:5]:  # Max 5 per cycle to avoid hammering
                        search_q = f"{movie.title} {movie.year or ''}"
                        try:
                            results = await indexer_engine.search(indexers, search_q, [2000, 2010, 2020, 2030, 2040, 2045, 2050])
                            for r in results[:3]:  # Check top 3 results
                                decision = decision_engine.evaluate(r.title, r.size, r.quality, r.language)
                                if decision.accepted and decision.score >= 70:
                                    success = await qbit.add_torrent(r.download_url, category="grimmgear-movies")
                                    if success:
                                        grabbed += 1
                                        logger.info(f"RSS auto-grabbed: {r.title} (score={decision.score})")
                                    break  # One grab per movie per cycle
                        except Exception as e:
                            logger.debug(f"RSS search failed for {movie.title}: {e}")
                        await asyncio.sleep(2)  # Rate limit between searches

                    self.last_rss_sync = datetime.utcnow().isoformat()
                    if grabbed > 0:
                        logger.info(f"RSS sync: grabbed {grabbed} releases")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"RSS sync error: {e}")
                await asyncio.sleep(60)

    async def _plex_notify_loop(self):
        """After imports, notify Plex to scan. Checks every 2 minutes."""
        import httpx
        from app.core.config import settings
        from app.core.import_pipeline import import_pipeline

        last_count = import_pipeline.stats.get("imported", 0)

        while self._running:
            try:
                await asyncio.sleep(120)
                current_count = import_pipeline.stats.get("imported", 0)
                if current_count > last_count:
                    # New imports happened — notify Plex
                    last_count = current_count
                    if settings.media_server.type == "plex" and settings.media_server.url and settings.media_server.token:
                        base = settings.media_server.url.rstrip("/")
                        headers = {"X-Plex-Token": settings.media_server.token}
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                resp = await client.get(f"{base}/library/sections/all/refresh", headers=headers)
                                if resp.status_code == 200:
                                    logger.info(f"Plex scan triggered after {current_count - last_count + (current_count - last_count)} new imports")
                        except Exception as e:
                            logger.debug(f"Plex notify failed: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Plex notify error: {e}")
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
