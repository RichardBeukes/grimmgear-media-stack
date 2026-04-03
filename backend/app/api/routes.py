"""
GrimmGear — API Routes
All routes prefixed with /api.
Module-specific routes are conditionally mounted based on enabled modules.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.modules.registry import registry

api_router = APIRouter()


# ============================================================
# System endpoints (always available)
# ============================================================

@api_router.get("/system/status")
async def system_status():
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "modules": registry.status(),
        "database": settings.database.url.split("://")[0],
        "media_root": str(settings.paths.media_root),
        "download_dir": str(settings.paths.download_dir),
        "media_server": settings.media_server.type,
    }


@api_router.get("/system/health")
async def system_health(db: AsyncSession = Depends(get_db)):
    health = {"status": "healthy", "checks": {}}

    # Database check
    try:
        await db.execute("SELECT 1")
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["status"] = "unhealthy"
        health["checks"]["database"] = str(e)

    # Module check
    enabled = registry.get_enabled()
    health["checks"]["modules"] = {
        "total": len(registry.get_all()),
        "enabled": len(enabled),
        "names": [m.name for m in enabled],
    }

    return health


@api_router.get("/modules")
async def list_modules():
    return registry.status()


@api_router.post("/modules/{name}/enable")
async def enable_module(name: str):
    success = registry.enable(name)
    return {"module": name, "enabled": success}


@api_router.post("/modules/{name}/disable")
async def disable_module(name: str):
    success = registry.disable(name)
    return {"module": name, "disabled": success}


# ============================================================
# Movies endpoints (when enabled)
# ============================================================

@api_router.get("/movies")
async def list_movies(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.db.models import Movie
    result = await db.execute(select(Movie).order_by(Movie.title))
    return [
        {
            "id": m.id, "title": m.title, "year": m.year,
            "tmdb_id": m.tmdb_id, "has_file": m.has_file,
            "monitored": m.monitored, "poster_url": m.poster_url,
        }
        for m in result.scalars().all()
    ]


@api_router.get("/movies/{movie_id}")
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    from app.db.models import Movie
    movie = await db.get(Movie, movie_id)
    if not movie:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


# ============================================================
# TV endpoints (when enabled)
# ============================================================

@api_router.get("/series")
async def list_series(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.db.models import Series
    result = await db.execute(select(Series).order_by(Series.title))
    return [
        {
            "id": s.id, "title": s.title, "year": s.year,
            "tvdb_id": s.tvdb_id, "monitored": s.monitored,
            "series_type": s.series_type, "poster_url": s.poster_url,
        }
        for s in result.scalars().all()
    ]


# ============================================================
# Queue / Downloads
# ============================================================

@api_router.get("/queue")
async def get_queue(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.db.models import DownloadQueueItem
    result = await db.execute(
        select(DownloadQueueItem).order_by(DownloadQueueItem.id.desc())
    )
    return [
        {
            "id": q.id, "title": q.title, "media_type": q.media_type,
            "status": q.status, "progress": q.progress,
            "quality": q.quality, "language": q.language,
        }
        for q in result.scalars().all()
    ]


# ============================================================
# Quality Profiles
# ============================================================

@api_router.get("/qualityprofiles")
async def list_quality_profiles(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.db.models import QualityProfile
    result = await db.execute(select(QualityProfile))
    return [
        {
            "id": p.id, "name": p.name, "language": p.language,
            "cutoff": p.cutoff, "upgrade_allowed": p.upgrade_allowed,
        }
        for p in result.scalars().all()
    ]


# ============================================================
# Indexers
# ============================================================

@api_router.get("/indexers")
async def list_indexers(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.db.models import Indexer
    result = await db.execute(select(Indexer))
    return [
        {
            "id": i.id, "name": i.name, "url": i.url,
            "enabled": i.enabled, "type": i.indexer_type,
            "use_flaresolverr": i.use_flaresolverr,
        }
        for i in result.scalars().all()
    ]
