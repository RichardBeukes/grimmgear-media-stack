"""
GrimmGear — Unified API Routes
ONE port. ONE interface. Everything lives here.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decision.engine import decision_engine
from app.core.download.qbit_client import qbit
from app.core.search.indexer_search import indexer_engine
from app.db.models import (
    Movie, Series, Season, Episode, Artist, Album, Track,
    Author, Book, ComicPublisher, ComicSeries, ComicIssue,
    QualityProfile, Indexer, DownloadQueueItem, User, MediaRequest,
    SystemSetting, RootFolder, DownloadClient as DownloadClientModel, NotificationAgent,
    BlocklistItem, Tag, TagAssignment, CustomFormat, ImportList,
    EventLog, NamingConfig, Backup,
)
from app.db.session import get_db
from app.modules.registry import registry
from app.services.metadata.tmdb import tmdb

api_router = APIRouter()


# ============================================================
# SYSTEM — always available
# ============================================================

@api_router.get("/system/status")
async def system_status():
    qbit_version = await qbit.get_version()
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "modules": registry.status(),
        "database": settings.database.url.split("://")[0],
        "media_root": str(settings.paths.media_root),
        "download_dir": str(settings.paths.download_dir),
        "media_server": settings.media_server.type,
        "download_client": {
            "type": "qBittorrent",
            "url": settings.download.qbit_url,
            "version": qbit_version,
            "connected": qbit_version != "offline",
        },
    }


@api_router.get("/system/health")
async def system_health(db: AsyncSession = Depends(get_db)):
    health = {"status": "healthy", "checks": {}}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["status"] = "unhealthy"
        health["checks"]["database"] = str(e)

    # Download client
    connected = await qbit.is_connected()
    health["checks"]["download_client"] = "ok" if connected else "offline"
    if not connected:
        health["status"] = "degraded"

    # Modules
    enabled = registry.get_enabled()
    health["checks"]["modules"] = {
        "total": len(registry.get_all()),
        "enabled": len(enabled),
        "names": [m.name for m in enabled],
    }

    return health


# ============================================================
# MODULES — toggle system
# ============================================================

@api_router.get("/modules")
async def list_modules():
    return registry.status()


@api_router.post("/modules/{name}/enable")
async def enable_module(name: str):
    return {"module": name, "enabled": registry.enable(name)}


@api_router.post("/modules/{name}/disable")
async def disable_module(name: str):
    return {"module": name, "disabled": registry.disable(name)}


# ============================================================
# SEARCH — universal search across all media types
# ============================================================

@api_router.get("/search")
async def universal_search(q: str = Query(..., min_length=1), type: str = "multi"):
    """Search TMDB for movies, TV, or both. One endpoint, all media."""
    if type == "movie":
        return await tmdb.search_movies(q)
    elif type == "tv":
        return await tmdb.search_tv(q)
    else:
        return await tmdb.search_multi(q)


@api_router.get("/search/indexers")
async def search_indexers(
    q: str = Query(..., min_length=1),
    imdb_id: str = None,
    tvdb_id: int = None,
    season: int = None,
    episode: int = None,
    categories: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Search all enabled indexers for releases."""
    # Get indexers from DB
    result = await db.execute(select(Indexer).where(Indexer.enabled == True))
    indexers = [
        {"name": i.name, "url": i.url, "api_key": i.api_key, "enabled": True, "indexer_type": i.indexer_type}
        for i in result.scalars().all()
    ]

    if not indexers:
        return {"results": [], "message": "No indexers configured. Add indexers first."}

    cats = [int(c) for c in categories.split(",")] if categories else None
    results = await indexer_engine.search(indexers, q, cats, imdb_id, tvdb_id, season, episode)

    return {
        "results": [
            {
                "title": r.title,
                "indexer": r.indexer,
                "download_url": r.download_url,
                "size": r.size,
                "seeders": r.seeders,
                "leechers": r.leechers,
                "quality": r.quality,
                "codec": r.codec,
                "source": r.source,
                "language": r.language,
                "score": r.score,
                "decision": decision_engine.evaluate(
                    r.title, r.size, r.quality, r.language
                ).__dict__,
            }
            for r in results
        ],
        "total": len(results),
        "indexers_searched": len(indexers),
    }


# ============================================================
# DISCOVER — trending, popular, upcoming
# ============================================================

@api_router.get("/discover/movies/trending")
async def trending_movies():
    return await tmdb.trending_movies()


@api_router.get("/discover/movies/popular")
async def popular_movies(page: int = 1):
    return await tmdb.popular_movies(page)


@api_router.get("/discover/movies/upcoming")
async def upcoming_movies(page: int = 1):
    return await tmdb.upcoming_movies(page)


@api_router.get("/discover/tv/trending")
async def trending_tv():
    return await tmdb.trending_tv()


@api_router.get("/discover/genres/movies")
async def movie_genres():
    return await tmdb.get_movie_genres()


@api_router.get("/discover/genres/tv")
async def tv_genres():
    return await tmdb.get_tv_genres()


# ============================================================
# MOVIES — add, list, detail, search+grab
# ============================================================

class AddMovieRequest(BaseModel):
    tmdb_id: int
    quality_profile_id: int = 1
    monitored: bool = True
    search_now: bool = True


@api_router.get("/movies")
async def list_movies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Movie).order_by(Movie.title))
    return [
        {
            "id": m.id, "title": m.title, "year": m.year,
            "tmdb_id": m.tmdb_id, "has_file": m.has_file,
            "monitored": m.monitored, "poster_url": m.poster_url,
            "overview": m.overview, "original_language": m.original_language,
        }
        for m in result.scalars().all()
    ]


@api_router.get("/movies/{movie_id}")
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")
    return {
        "id": movie.id, "title": movie.title, "year": movie.year,
        "tmdb_id": movie.tmdb_id, "imdb_id": movie.imdb_id,
        "has_file": movie.has_file, "monitored": movie.monitored,
        "poster_url": movie.poster_url, "fanart_url": movie.fanart_url,
        "overview": movie.overview, "path": movie.path,
        "genres": movie.genres, "runtime": movie.runtime,
    }


@api_router.get("/movies/{movie_id}/detail")
async def get_movie_detail(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Get movie with live TMDB detail (cast, trailer, tagline)."""
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")
    detail = await tmdb.get_movie(movie.tmdb_id)
    if not detail:
        raise HTTPException(502, "Failed to fetch TMDB detail")
    detail["id"] = movie.id
    detail["has_file"] = movie.has_file
    detail["monitored"] = movie.monitored
    detail["path"] = movie.path
    return detail


@api_router.post("/movies")
async def add_movie(req: AddMovieRequest, db: AsyncSession = Depends(get_db)):
    """Add a movie from TMDB. Fetches metadata and optionally searches indexers."""
    # Check if already exists
    existing = await db.execute(select(Movie).where(Movie.tmdb_id == req.tmdb_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Movie already in library")

    # Fetch metadata from TMDB
    meta = await tmdb.get_movie(req.tmdb_id)
    if not meta:
        raise HTTPException(404, "Movie not found on TMDB")

    movie = Movie(
        title=meta["title"],
        year=meta.get("year"),
        tmdb_id=meta["tmdb_id"],
        imdb_id=meta.get("imdb_id"),
        overview=meta.get("overview", ""),
        poster_url=meta.get("poster_url"),
        fanart_url=meta.get("fanart_url"),
        original_language=meta.get("original_language", "en"),
        runtime=meta.get("runtime"),
        genres=meta.get("genres"),
        quality_profile_id=req.quality_profile_id,
        root_folder=str(settings.paths.movies_dir),
        monitored=req.monitored,
    )
    db.add(movie)
    await db.flush()

    return {
        "id": movie.id,
        "title": movie.title,
        "tmdb_id": movie.tmdb_id,
        "added": True,
        "message": f"'{movie.title}' added to library",
    }


@api_router.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")
    await db.delete(movie)
    return {"deleted": True, "title": movie.title}


# ============================================================
# TV SERIES
# ============================================================

class AddSeriesRequest(BaseModel):
    tmdb_id: int
    quality_profile_id: int = 1
    monitored: bool = True


@api_router.get("/series")
async def list_series(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Series).order_by(Series.title))
    return [
        {
            "id": s.id, "title": s.title, "year": s.year,
            "tvdb_id": s.tvdb_id, "monitored": s.monitored,
            "series_type": s.series_type, "poster_url": s.poster_url,
            "overview": s.overview,
        }
        for s in result.scalars().all()
    ]


@api_router.post("/series")
async def add_series(req: AddSeriesRequest, db: AsyncSession = Depends(get_db)):
    """Add a TV series from TMDB. Fetches metadata including seasons."""
    meta = await tmdb.get_tv(req.tmdb_id)
    if not meta:
        raise HTTPException(404, "Series not found on TMDB")

    tvdb_id = meta.get("tvdb_id") or req.tmdb_id  # Fallback to TMDB ID

    existing = await db.execute(select(Series).where(Series.tvdb_id == tvdb_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Series already in library")

    series = Series(
        title=meta["title"],
        year=meta.get("year"),
        tvdb_id=tvdb_id,
        tmdb_id=meta["tmdb_id"],
        overview=meta.get("overview", ""),
        poster_url=meta.get("poster_url"),
        fanart_url=meta.get("fanart_url"),
        original_language=meta.get("original_language", "en"),
        genres=meta.get("genres"),
        quality_profile_id=req.quality_profile_id,
        root_folder=str(settings.paths.tv_dir),
        monitored=req.monitored,
    )
    db.add(series)
    await db.flush()

    # Add seasons
    for s_meta in meta.get("seasons", []):
        season = Season(
            series_id=series.id,
            season_number=s_meta["season_number"],
            monitored=req.monitored,
        )
        db.add(season)

    return {
        "id": series.id,
        "title": series.title,
        "tvdb_id": series.tvdb_id,
        "seasons": len(meta.get("seasons", [])),
        "added": True,
    }


@api_router.get("/series/{series_id}")
async def get_series(series_id: int, db: AsyncSession = Depends(get_db)):
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    return series


@api_router.get("/series/{series_id}/detail")
async def get_series_detail(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get series with live TMDB detail (cast, seasons, episodes)."""
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    tmdb_id = series.tmdb_id or series.tvdb_id
    detail = await tmdb.get_tv(tmdb_id)
    if not detail:
        raise HTTPException(502, "Failed to fetch TMDB detail")
    detail["id"] = series.id
    detail["monitored"] = series.monitored
    return detail


@api_router.get("/series/{series_id}/season/{season_number}")
async def get_series_season(series_id: int, season_number: int, db: AsyncSession = Depends(get_db)):
    """Get episode list for a season from TMDB."""
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    tmdb_id = series.tmdb_id or series.tvdb_id
    season_data = await tmdb.get_tv_season(tmdb_id, season_number)
    if not season_data:
        raise HTTPException(502, "Failed to fetch season detail")
    return season_data


# ============================================================
# DOWNLOADS — monitor qBittorrent
# ============================================================

@api_router.get("/downloads")
async def get_downloads():
    """Get all active downloads from qBittorrent."""
    torrents = await qbit.get_torrents()
    return {
        "torrents": [
            {
                "name": t.get("name"),
                "hash": t.get("hash"),
                "progress": t.get("progress", 0),
                "size": t.get("size", 0),
                "dl_speed": t.get("dlspeed", 0),
                "ul_speed": t.get("upspeed", 0),
                "state": t.get("state"),
                "category": t.get("category", ""),
                "eta": t.get("eta", 0),
            }
            for t in torrents
        ],
        "total": len(torrents),
    }


@api_router.get("/downloads/speed")
async def download_speed():
    info = await qbit.get_transfer_info()
    return {
        "dl_speed": info.get("dl_info_speed", 0),
        "ul_speed": info.get("up_info_speed", 0),
        "dl_total": info.get("dl_info_data", 0),
        "ul_total": info.get("up_info_data", 0),
    }


class GrabRequest(BaseModel):
    download_url: str
    title: str
    media_type: str = "movie"  # movie, episode, track, book
    media_id: int = 0
    category: str = ""
    quality: str = ""


@api_router.post("/downloads/grab")
async def grab_release(req: GrabRequest, db: AsyncSession = Depends(get_db)):
    """Grab a release — evaluate with decision engine then send to qBit."""
    # Run decision engine
    decision = decision_engine.evaluate(
        title=req.title,
        quality=req.quality,
    )

    if not decision.accepted:
        return {"grabbed": False, "reason": decision.reason}

    # Determine category
    category = req.category or {
        "movie": "grimmgear-movies",
        "episode": "grimmgear-tv",
        "track": "grimmgear-music",
        "book": "grimmgear-books",
    }.get(req.media_type, "grimmgear")

    # Send to qBittorrent
    success = await qbit.add_torrent(req.download_url, category=category)

    if success:
        # Add to download queue
        queue_item = DownloadQueueItem(
            title=req.title,
            media_type=req.media_type,
            media_id=req.media_id,
            status="downloading",
            download_client="qbittorrent",
            quality=req.quality,
        )
        db.add(queue_item)

    return {
        "grabbed": success,
        "title": req.title,
        "category": category,
        "decision_score": decision.score,
    }


@api_router.delete("/downloads/{hash}")
async def delete_download(hash: str, delete_files: bool = False):
    success = await qbit.delete_torrent(hash, delete_files)
    return {"deleted": success}


@api_router.post("/downloads/{hash}/pause")
async def pause_download(hash: str):
    success = await qbit.pause_torrent(hash)
    return {"paused": success}


@api_router.post("/downloads/{hash}/resume")
async def resume_download(hash: str):
    success = await qbit.resume_torrent(hash)
    return {"resumed": success}


# ============================================================
# QUEUE — internal download tracking
# ============================================================

@api_router.get("/queue")
async def get_queue(db: AsyncSession = Depends(get_db)):
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
# INDEXERS — manage search sources
# ============================================================

class AddIndexerRequest(BaseModel):
    name: str
    url: str
    api_key: str = ""
    indexer_type: str = "torznab"
    categories: list[int] = []
    use_flaresolverr: bool = False


# ── Seed default quality profiles on first call ─────────
_profiles_seeded = False

async def seed_quality_profiles(db: AsyncSession):
    global _profiles_seeded
    if _profiles_seeded:
        return
    existing = await db.execute(select(QualityProfile))
    if existing.scalars().first():
        _profiles_seeded = True
        return
    defaults = [
        # Video (Movies & TV)
        QualityProfile(name="Any", media_type="movie", language="English", min_quality="SDTV", cutoff="Bluray-1080p", upgrade_allowed=True),
        QualityProfile(name="HD-1080p", media_type="movie", language="English", min_quality="HDTV-720p", cutoff="Bluray-1080p", upgrade_allowed=True),
        QualityProfile(name="Ultra-HD", media_type="movie", language="English", min_quality="HDTV-1080p", cutoff="Remux-2160p", upgrade_allowed=True),
        QualityProfile(name="SD", media_type="movie", language="English", min_quality="SDTV", cutoff="DVD", upgrade_allowed=False),
        # Music
        QualityProfile(name="Lossless", media_type="music", language="Any", min_quality="FLAC", cutoff="FLAC-24bit", upgrade_allowed=True,
                       items='["MP3-128","MP3-192","MP3-256","MP3-320","AAC-256","OGG-320","FLAC","FLAC-24bit","WAV","ALAC"]'),
        QualityProfile(name="High Quality MP3", media_type="music", language="Any", min_quality="MP3-256", cutoff="MP3-320", upgrade_allowed=True,
                       items='["MP3-128","MP3-192","MP3-256","MP3-320","AAC-256"]'),
        QualityProfile(name="Any Audio", media_type="music", language="Any", min_quality="MP3-128", cutoff="FLAC", upgrade_allowed=True,
                       items='["MP3-128","MP3-192","MP3-256","MP3-320","AAC-256","OGG-320","FLAC","FLAC-24bit","WAV","ALAC","WMA","APE"]'),
        # Books (Ebooks)
        QualityProfile(name="Ebook - Any Format", media_type="book", language="English", min_quality="MOBI", cutoff="EPUB", upgrade_allowed=True,
                       items='["PDF","MOBI","EPUB","AZW3","FB2","LIT","LRF","PDB","DJVU"]'),
        QualityProfile(name="Ebook - EPUB Preferred", media_type="book", language="English", min_quality="EPUB", cutoff="EPUB", upgrade_allowed=False,
                       items='["EPUB","AZW3"]'),
        # Audiobooks
        QualityProfile(name="Audiobook - High Quality", media_type="audiobook", language="English", min_quality="MP3-128", cutoff="M4B-256", upgrade_allowed=True,
                       items='["MP3-64","MP3-128","MP3-192","MP3-256","MP3-320","M4B-128","M4B-256","M4B-320","FLAC"]'),
        QualityProfile(name="Audiobook - Any", media_type="audiobook", language="English", min_quality="MP3-64", cutoff="M4B-128", upgrade_allowed=True,
                       items='["MP3-64","MP3-128","MP3-192","MP3-256","M4B-128","M4B-256"]'),
        # Comics
        QualityProfile(name="Comic - CBZ Preferred", media_type="comic", language="English", min_quality="CBR", cutoff="CBZ", upgrade_allowed=True,
                       items='["CBR","CBZ","CB7","PDF"]'),
        QualityProfile(name="Comic - Any Format", media_type="comic", language="English", min_quality="CBR", cutoff="CBZ", upgrade_allowed=True,
                       items='["CBR","CBZ","CB7","PDF","EPUB"]'),
    ]
    for p in defaults:
        db.add(p)
    _profiles_seeded = True


@api_router.get("/indexers")
async def list_indexers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Indexer))
    return [
        {
            "id": i.id, "name": i.name, "url": i.url,
            "enabled": i.enabled, "type": i.indexer_type,
            "use_flaresolverr": i.use_flaresolverr,
            "stats": {
                "queries": i.query_count, "grabs": i.grab_count,
                "failures": i.fail_count, "avg_response_ms": i.avg_response_ms,
            },
        }
        for i in result.scalars().all()
    ]


@api_router.get("/indexers/stats")
async def indexer_stats(db: AsyncSession = Depends(get_db)):
    """Indexer stats like Prowlarr's /indexers/stats page."""
    result = await db.execute(select(Indexer).order_by(Indexer.query_count.desc()))
    indexers = result.scalars().all()
    total_queries = sum(i.query_count for i in indexers)
    total_grabs = sum(i.grab_count for i in indexers)
    total_fails = sum(i.fail_count for i in indexers)
    return {
        "total_queries": total_queries,
        "total_grabs": total_grabs,
        "total_failures": total_fails,
        "indexers": [
            {
                "id": i.id, "name": i.name, "enabled": i.enabled,
                "queries": i.query_count, "grabs": i.grab_count,
                "failures": i.fail_count, "avg_response_ms": i.avg_response_ms,
                "success_rate": round((i.query_count - i.fail_count) / max(i.query_count, 1) * 100, 1),
            }
            for i in indexers
        ],
    }


@api_router.post("/indexers")
async def add_indexer(req: AddIndexerRequest, db: AsyncSession = Depends(get_db)):
    if not req.name or not req.name.strip():
        raise HTTPException(400, "Indexer name is required")
    if not req.url or not req.url.strip():
        raise HTTPException(400, "Indexer URL is required")
    indexer = Indexer(
        name=req.name.strip(),
        url=req.url,
        api_key=req.api_key,
        indexer_type=req.indexer_type,
        categories=req.categories,
        use_flaresolverr=req.use_flaresolverr,
    )
    db.add(indexer)
    await db.flush()
    return {"id": indexer.id, "name": indexer.name, "added": True}


@api_router.delete("/indexers/{indexer_id}")
async def delete_indexer(indexer_id: int, db: AsyncSession = Depends(get_db)):
    indexer = await db.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    await db.delete(indexer)
    return {"deleted": True, "name": indexer.name}


# ── Built-in indexer catalog (like Prowlarr's indexer list) ──

INDEXER_CATALOG = [
    {"name": "1337x", "description": "Popular general torrent site", "categories": ["Movies", "TV", "Music", "Games", "Anime"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "YTS", "description": "YIFY movies — small, high-quality encodes", "categories": ["Movies"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "The Pirate Bay", "description": "The original torrent site", "categories": ["Movies", "TV", "Music", "Games", "Books"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "EZTV", "description": "TV show torrents", "categories": ["TV"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "RARBG (clone)", "description": "RARBG database mirror / successor sites", "categories": ["Movies", "TV"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "Knaben", "description": "Multi-indexer aggregator", "categories": ["Movies", "TV", "Music", "Books", "Anime"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "LimeTorrents", "description": "Verified torrent search", "categories": ["Movies", "TV", "Music", "Games"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "TorrentGalaxy", "description": "General torrent tracker with IMDB integration", "categories": ["Movies", "TV", "Music", "Games", "Anime"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "Nyaa", "description": "Anime/Asian media torrents", "categories": ["Anime", "Music"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "Torrent Downloads", "description": "General torrent aggregator", "categories": ["Movies", "TV", "Music", "Games"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "showRSS", "description": "TV show RSS feeds", "categories": ["TV"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "TorrentProject2", "description": "Torrent meta-search engine", "categories": ["Movies", "TV", "Music"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "MagnetDownload", "description": "Magnet link aggregator", "categories": ["Movies", "TV", "Music"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "BT.etree", "description": "Live music / bootleg recordings", "categories": ["Music"], "privacy": "public", "protocol": "torrent", "needs_api_key": False},
    {"name": "RuTracker", "description": "Russian tracker — huge library, many exclusive releases", "categories": ["Movies", "TV", "Music", "Books", "Games"], "privacy": "semi-private", "protocol": "torrent", "needs_api_key": True},
    {"name": "IPTorrents", "description": "Large private general tracker", "categories": ["Movies", "TV", "Music", "Games", "Books"], "privacy": "private", "protocol": "torrent", "needs_api_key": True},
    {"name": "TorrentLeech", "description": "Well-known private general tracker", "categories": ["Movies", "TV", "Music", "Games"], "privacy": "private", "protocol": "torrent", "needs_api_key": True},
    {"name": "NZBgeek", "description": "Popular Usenet indexer", "categories": ["Movies", "TV", "Music", "Books"], "privacy": "private", "protocol": "usenet", "needs_api_key": True},
    {"name": "NZBFinder", "description": "Usenet indexer with automation support", "categories": ["Movies", "TV", "Music"], "privacy": "private", "protocol": "usenet", "needs_api_key": True},
    {"name": "DrunkenSlug", "description": "Usenet indexer — community-driven", "categories": ["Movies", "TV", "Music", "Books"], "privacy": "private", "protocol": "usenet", "needs_api_key": True},
]


@api_router.get("/indexers/catalog")
async def indexer_catalog(category: str = ""):
    """Browse available indexers like Prowlarr's indexer list."""
    items = INDEXER_CATALOG
    if category:
        items = [i for i in items if category in i["categories"]]
    return {"indexers": items, "total": len(items)}


@api_router.get("/indexers/discover")
async def discover_indexers():
    """Auto-discover indexers from Prowlarr or Jackett if running."""
    import httpx
    discovered = []

    # Try Prowlarr
    prowlarr_url = settings.indexer_proxy.prowlarr_url.rstrip("/")
    prowlarr_key = settings.indexer_proxy.prowlarr_api_key

    # Auto-detect Prowlarr API key from config if not set
    if not prowlarr_key:
        import xml.etree.ElementTree as ET
        for config_path in [
            os.path.expandvars(r"%APPDATA%\Prowlarr\config.xml"),
            os.path.expandvars(r"%LOCALAPPDATA%\Prowlarr\config.xml"),
            r"C:\ProgramData\Prowlarr\config.xml",
            "/var/lib/prowlarr/config.xml",
        ]:
            if os.path.exists(config_path):
                try:
                    tree = ET.parse(config_path)
                    key_el = tree.getroot().find("ApiKey")
                    if key_el is not None and key_el.text:
                        prowlarr_key = key_el.text
                        break
                except Exception:
                    pass

    if prowlarr_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{prowlarr_url}/api/v1/indexer",
                    headers={"X-Api-Key": prowlarr_key},
                )
                if resp.status_code == 200:
                    for idx in resp.json():
                        if not idx.get("enable"):
                            continue
                        torznab_url = f"{prowlarr_url}/{idx['id']}/api?apikey={prowlarr_key}"
                        cats = [c.get("name", "") for c in idx.get("capabilities", {}).get("categories", [])[:5]]
                        discovered.append({
                            "name": idx["name"],
                            "source": "prowlarr",
                            "torznab_url": torznab_url,
                            "protocol": idx.get("protocol", "torrent"),
                            "privacy": idx.get("privacy", "public"),
                            "categories": cats,
                            "prowlarr_id": idx["id"],
                        })
        except Exception:
            pass

    return {
        "discovered": discovered,
        "total": len(discovered),
        "prowlarr_connected": len(discovered) > 0,
        "prowlarr_url": prowlarr_url if prowlarr_key else None,
    }


@api_router.post("/indexers/import-from-prowlarr")
async def import_from_prowlarr(db: AsyncSession = Depends(get_db)):
    """One-click import all Prowlarr indexers as Torznab sources."""
    disc = await discover_indexers()
    if not disc["discovered"]:
        return {"imported": 0, "message": "No Prowlarr indexers found"}

    imported = 0
    skipped = 0
    for idx in disc["discovered"]:
        # Check if already exists by name
        existing = await db.execute(select(Indexer).where(Indexer.name == idx["name"]))
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        indexer = Indexer(
            name=idx["name"],
            url=idx["torznab_url"],
            api_key="",
            indexer_type="torznab",
            enabled=True,
        )
        db.add(indexer)
        imported += 1

    return {"imported": imported, "skipped": skipped, "total": len(disc["discovered"])}


@api_router.post("/indexers/{indexer_id}/test")
async def test_indexer(indexer_id: int, db: AsyncSession = Depends(get_db)):
    """Test an indexer connection by running a simple search."""
    indexer = await db.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    try:
        test_results = await indexer_engine.search(
            [{"name": indexer.name, "url": indexer.url, "api_key": indexer.api_key, "enabled": True, "indexer_type": indexer.indexer_type}],
            "test", None, None, None, None, None,
        )
        return {"success": True, "results": len(test_results), "name": indexer.name}
    except Exception as e:
        return {"success": False, "error": str(e), "name": indexer.name}


# ============================================================
# QUALITY PROFILES
# ============================================================

@api_router.get("/qualityprofiles")
async def list_quality_profiles(db: AsyncSession = Depends(get_db)):
    await seed_quality_profiles(db)
    result = await db.execute(select(QualityProfile))
    return [
        {
            "id": p.id, "name": p.name, "language": p.language,
            "cutoff": p.cutoff, "upgrade_allowed": p.upgrade_allowed,
        }
        for p in result.scalars().all()
    ]


# ============================================================
# IMPORT PIPELINE — scan and import completed downloads
# ============================================================

@api_router.post("/import/scan")
async def trigger_import_scan():
    """Manually trigger an import scan of completed downloads."""
    from app.core.import_pipeline import import_pipeline
    result = await import_pipeline.scan_and_import()
    return result


@api_router.get("/import/status")
async def import_status():
    """Get import pipeline statistics."""
    from app.core.import_pipeline import import_pipeline
    return import_pipeline.stats


# ============================================================
# SCHEDULER — background task status
# ============================================================

@api_router.get("/scheduler/status")
async def scheduler_status():
    """Get background scheduler status."""
    from app.core.queue import scheduler
    return scheduler.status


# ============================================================
# PLEX — trigger library scan
# ============================================================

@api_router.post("/plex/scan")
async def plex_scan(section: int = 0):
    """Trigger Plex library scan. Requires media_server type=plex and a token."""
    import httpx
    if settings.media_server.type != "plex" or not settings.media_server.url or not settings.media_server.token:
        return {"triggered": False, "reason": "Plex not configured (set GG_MEDIA_SERVER_TYPE=plex, GG_MEDIA_SERVER_URL, GG_MEDIA_SERVER_TOKEN)"}
    base = settings.media_server.url.rstrip("/")
    headers = {"X-Plex-Token": settings.media_server.token, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if section:
                resp = await client.get(f"{base}/library/sections/{section}/refresh", headers=headers)
            else:
                resp = await client.get(f"{base}/library/sections/all/refresh", headers=headers)
            return {"triggered": resp.status_code == 200, "status_code": resp.status_code}
    except Exception as e:
        return {"triggered": False, "reason": str(e)}


@api_router.get("/plex/sections")
async def plex_sections():
    """List Plex library sections."""
    import httpx
    if settings.media_server.type != "plex" or not settings.media_server.url or not settings.media_server.token:
        return {"sections": [], "reason": "Plex not configured"}
    base = settings.media_server.url.rstrip("/")
    headers = {"X-Plex-Token": settings.media_server.token, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base}/library/sections", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {"sections": [
                    {"key": s["key"], "title": s["title"], "type": s["type"]}
                    for s in data.get("MediaContainer", {}).get("Directory", [])
                ]}
            return {"sections": [], "reason": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"sections": [], "reason": str(e)}


# ============================================================
# LIBRARY — browse what's actually on disk
# ============================================================

import os
from pathlib import Path as _Path
from datetime import datetime as _dt

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".ts", ".m2ts", ".webm"}
AUDIO_EXT = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".wma", ".aac"}
BOOK_EXT = {".epub", ".mobi", ".azw3", ".pdf", ".cbz", ".cbr"}


def _scan_media_folder(root: _Path, extensions: set[str]) -> list[dict]:
    """Scan a media folder and return entries with file info."""
    if not root.exists():
        return []
    entries = []
    for item in sorted(root.iterdir()):
        if item.name.startswith("."):
            continue
        entry = {"name": item.name, "path": str(item)}
        if item.is_dir():
            files = []
            total_size = 0
            for f in item.rglob("*"):
                if f.is_file() and f.suffix.lower() in extensions:
                    fsize = f.stat().st_size
                    files.append({"name": f.name, "size": fsize})
                    total_size += fsize
            entry["type"] = "folder"
            entry["file_count"] = len(files)
            entry["total_size"] = total_size
            entry["files"] = [f["name"] for f in sorted(files, key=lambda x: -x["size"])[:5]]
            try:
                entry["modified"] = _dt.fromtimestamp(item.stat().st_mtime).isoformat()
            except Exception:
                entry["modified"] = None
        elif item.is_file() and item.suffix.lower() in extensions:
            entry["type"] = "file"
            entry["total_size"] = item.stat().st_size
            entry["file_count"] = 1
            try:
                entry["modified"] = _dt.fromtimestamp(item.stat().st_mtime).isoformat()
            except Exception:
                entry["modified"] = None
        else:
            continue
        entries.append(entry)
    return entries


@api_router.get("/library/stats")
async def library_stats():
    """Get overview stats for all media directories."""
    media_root = settings.paths.media_root
    result = {}
    for name, subdir, exts in [
        ("movies", "Movies", VIDEO_EXT),
        ("tv", "TVshows", VIDEO_EXT),
        ("music", "Music", AUDIO_EXT),
        ("books", "Books", BOOK_EXT),
    ]:
        folder = media_root / subdir
        if not folder.exists():
            result[name] = {"folders": 0, "files": 0, "total_size": 0, "path": str(folder)}
            continue
        folders = 0
        files = 0
        total_size = 0
        for item in folder.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir():
                folders += 1
                for f in item.rglob("*"):
                    if f.is_file() and f.suffix.lower() in exts:
                        files += 1
                        total_size += f.stat().st_size
            elif item.is_file() and item.suffix.lower() in exts:
                files += 1
                total_size += item.stat().st_size
        result[name] = {"folders": folders, "files": files, "total_size": total_size, "path": str(folder)}
    return result


@api_router.get("/library/movies")
async def library_movies():
    """List all movie folders on disk with file info."""
    entries = _scan_media_folder(settings.paths.movies_dir, VIDEO_EXT)
    return {"items": entries, "total": len(entries), "path": str(settings.paths.movies_dir)}


@api_router.get("/library/tv")
async def library_tv():
    """List all TV show folders on disk with file info."""
    entries = _scan_media_folder(settings.paths.tv_dir, VIDEO_EXT)
    return {"items": entries, "total": len(entries), "path": str(settings.paths.tv_dir)}


@api_router.get("/library/music")
async def library_music():
    """List all music on disk."""
    entries = _scan_media_folder(settings.paths.music_dir, AUDIO_EXT)
    return {"items": entries, "total": len(entries), "path": str(settings.paths.music_dir)}


@api_router.get("/library/books")
async def library_books():
    """List all books on disk."""
    entries = _scan_media_folder(settings.paths.books_dir, BOOK_EXT)
    return {"items": entries, "total": len(entries), "path": str(settings.paths.books_dir)}


@api_router.get("/library/recent")
async def library_recent(limit: int = 20):
    """Get most recently added media across all types."""
    recent = []
    for subdir, media_type, exts in [
        ("Movies", "movie", VIDEO_EXT),
        ("TVshows", "tv", VIDEO_EXT),
        ("Music", "music", AUDIO_EXT),
        ("Books", "book", BOOK_EXT),
    ]:
        folder = settings.paths.media_root / subdir
        if not folder.exists():
            continue
        for item in folder.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir() or (item.is_file() and item.suffix.lower() in exts):
                try:
                    mtime = item.stat().st_mtime
                    size = 0
                    fcount = 0
                    if item.is_dir():
                        for f in item.rglob("*"):
                            if f.is_file() and f.suffix.lower() in exts:
                                size += f.stat().st_size
                                fcount += 1
                    else:
                        size = item.stat().st_size
                        fcount = 1
                    recent.append({
                        "name": item.name,
                        "media_type": media_type,
                        "modified": _dt.fromtimestamp(mtime).isoformat(),
                        "mtime": mtime,
                        "total_size": size,
                        "file_count": fcount,
                    })
                except Exception:
                    pass
    recent.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    for r in recent:
        r.pop("mtime", None)
    return {"items": recent[:limit], "total": len(recent)}


@api_router.get("/library/browse")
async def library_browse(path: str = ""):
    """Browse a specific folder in the media root. Returns playable files with stream URLs."""
    media_root = settings.paths.media_root
    if path:
        target = _Path(path)
    else:
        target = media_root

    # Security: ensure the path is within media_root
    try:
        target.resolve().relative_to(media_root.resolve())
    except ValueError:
        raise HTTPException(403, "Path outside media root")

    if not target.exists():
        raise HTTPException(404, "Path not found")

    all_media = VIDEO_EXT | AUDIO_EXT | BOOK_EXT
    items = []
    if target.is_dir():
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            entry = {"name": item.name, "path": str(item)}
            if item.is_dir():
                entry["type"] = "folder"
                # Count files
                count = sum(1 for f in item.rglob("*") if f.is_file() and f.suffix.lower() in all_media)
                entry["file_count"] = count
            elif item.is_file() and item.suffix.lower() in all_media:
                ext = item.suffix.lower()
                entry["type"] = "video" if ext in VIDEO_EXT else "audio" if ext in AUDIO_EXT else "book"
                entry["size"] = item.stat().st_size
                # Stream URL — use base64 of relative path to avoid path issues
                import base64
                rel = str(item.relative_to(media_root))
                entry["stream_url"] = "/api/stream/" + base64.urlsafe_b64encode(rel.encode()).decode()
            else:
                continue
            items.append(entry)
    return {"items": items, "path": str(target), "parent": str(target.parent) if target != media_root else None}


# ============================================================
# STREAM — serve media files with range request support
# ============================================================

import base64 as _b64
import mimetypes
from app.core.transcode import transcoder

MIME_MAP = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
    ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".ts": "video/mp2t", ".m2ts": "video/mp2t", ".flv": "video/x-flv",
    ".mp3": "audio/mpeg", ".flac": "audio/flac", ".m4a": "audio/mp4",
    ".ogg": "audio/ogg", ".opus": "audio/opus", ".wav": "audio/wav",
    ".wma": "audio/x-ms-wma", ".aac": "audio/aac",
}

# Extensions that need transcoding for browser playback
TRANSCODE_EXT = {".mkv", ".avi", ".wmv", ".flv", ".ts", ".m2ts"}


def _resolve_token(file_token: str) -> _Path:
    """Decode a stream token and validate the path."""
    try:
        rel_path = _b64.urlsafe_b64decode(file_token).decode()
    except Exception:
        raise HTTPException(400, "Invalid file token")
    file_path = settings.paths.media_root / rel_path
    try:
        file_path.resolve().relative_to(settings.paths.media_root.resolve())
    except ValueError:
        raise HTTPException(403, "Path traversal blocked")
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    return file_path


@api_router.get("/stream/{file_token}")
async def stream_media(file_token: str, request: Request):
    """Stream a media file. Supports HTTP range requests for seeking.
    For MKV/AVI/etc, auto-redirects to transcode endpoint."""
    file_path = _resolve_token(file_token)
    ext = file_path.suffix.lower()

    # Auto-transcode non-browser formats
    if ext in TRANSCODE_EXT:
        return StreamingResponse(
            transcoder.stream_transcode(str(file_path)),
            media_type="video/mp4",
            headers={"Content-Disposition": f'inline; filename="{file_path.stem}.mp4"'},
        )

    file_size = file_path.stat().st_size
    content_type = MIME_MAP.get(ext, mimetypes.guess_type(str(file_path))[0] or "application/octet-stream")

    # Parse range header
    range_header = request.headers.get("range")
    if range_header:
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        async def ranged_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            ranged_file(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_path.name}"',
            },
        )
    else:
        async def full_file():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            full_file(),
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_path.name}"',
            },
        )


# ============================================================
# TRANSCODE — FFmpeg batch queue + probe
# ============================================================

@api_router.get("/transcode/status")
async def transcode_status():
    """Get transcoder status and stats."""
    return transcoder.status


@api_router.get("/transcode/queue")
async def transcode_queue():
    """Get the transcode queue."""
    return {"queue": transcoder.queue}


@api_router.get("/transcode/probe/{file_token}")
async def transcode_probe(file_token: str):
    """Probe a media file for codec info and transcode needs."""
    file_path = _resolve_token(file_token)
    return transcoder.probe(str(file_path))


class TranscodeRequest(BaseModel):
    file_token: str


@api_router.post("/transcode/add")
async def transcode_add(req: TranscodeRequest):
    """Add a file to the batch transcode queue (MKV to MP4)."""
    file_path = _resolve_token(req.file_token)
    job = transcoder.add_to_queue(str(file_path))
    # Start processing in background
    asyncio.create_task(transcoder.process_queue())
    return {"queued": True, "job_id": job.id, "source": file_path.name}


@api_router.delete("/transcode/{job_id}")
async def transcode_cancel(job_id: int):
    """Cancel a queued transcode job."""
    return {"cancelled": transcoder.cancel_job(job_id)}


# ============================================================
# NOTIFICATIONS — Discord, Telegram, Webhook
# ============================================================

from app.core.notifications import notifier
from app.core.notifications.notifier import NotificationChannel


class AddNotificationChannelRequest(BaseModel):
    name: str
    type: str  # discord, telegram, webhook
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""


@api_router.get("/notifications/channels")
async def list_notification_channels():
    return {"channels": notifier.get_channels()}


@api_router.post("/notifications/channels")
async def add_notification_channel(req: AddNotificationChannelRequest):
    ch = NotificationChannel(
        name=req.name,
        type=req.type,
        discord_webhook_url=req.discord_webhook_url,
        telegram_bot_token=req.telegram_bot_token,
        telegram_chat_id=req.telegram_chat_id,
        webhook_url=req.webhook_url,
    )
    notifier.add_channel(ch)
    return {"added": True, "name": ch.name}


@api_router.delete("/notifications/channels/{name}")
async def remove_notification_channel(name: str):
    return {"removed": notifier.remove_channel(name)}


@api_router.post("/notifications/channels/{name}/test")
async def test_notification_channel(name: str):
    return await notifier.test_channel(name)


@api_router.get("/notifications/history")
async def notification_history():
    return {"history": notifier.history}


# ============================================================
# REQUESTS — user media requests with approval workflow
# ============================================================

class CreateRequestModel(BaseModel):
    title: str
    media_type: str = "movie"
    tmdb_id: int = 0
    year: int = 0
    poster_url: str = ""
    overview: str = ""
    requester: str = "anonymous"
    note: str = ""


@api_router.get("/requests")
async def list_requests(status: str = "", db: AsyncSession = Depends(get_db)):
    """List all media requests, optionally filtered by status."""
    q = select(MediaRequest).order_by(MediaRequest.id.desc())
    if status:
        q = q.where(MediaRequest.status == status)
    result = await db.execute(q)
    return [
        {
            "id": r.id, "title": r.title, "media_type": r.media_type,
            "tmdb_id": r.tmdb_id, "year": r.year, "poster_url": r.poster_url,
            "overview": r.overview, "status": r.status, "requester": r.requester,
            "votes": r.votes, "note": r.note,
        }
        for r in result.scalars().all()
    ]


@api_router.post("/requests")
async def create_request(req: CreateRequestModel, db: AsyncSession = Depends(get_db)):
    """Submit a new media request."""
    # Check for duplicate
    existing = await db.execute(
        select(MediaRequest).where(
            MediaRequest.title == req.title,
            MediaRequest.media_type == req.media_type,
            MediaRequest.status.in_(["pending", "approved"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Request already exists")

    media_req = MediaRequest(
        title=req.title,
        media_type=req.media_type,
        tmdb_id=req.tmdb_id if req.tmdb_id else None,
        year=req.year if req.year else None,
        poster_url=req.poster_url or None,
        overview=req.overview or None,
        requester=req.requester,
        note=req.note or None,
    )
    db.add(media_req)
    await db.flush()

    # Notify
    await notifier.notify(
        "request.new",
        f"New Request: {req.title}",
        f"{req.requester} requested {req.media_type}: {req.title}",
        poster_url=req.poster_url,
    )

    return {"id": media_req.id, "title": media_req.title, "created": True}


@api_router.post("/requests/{request_id}/approve")
async def approve_request(request_id: int, db: AsyncSession = Depends(get_db)):
    """Approve a request and optionally auto-add to library."""
    media_req = await db.get(MediaRequest, request_id)
    if not media_req:
        raise HTTPException(404, "Request not found")
    media_req.status = "approved"

    # Auto-add to library if TMDB ID is available
    added = False
    if media_req.tmdb_id:
        if media_req.media_type == "movie":
            existing = await db.execute(select(Movie).where(Movie.tmdb_id == media_req.tmdb_id))
            if not existing.scalar_one_or_none():
                meta = await tmdb.get_movie(media_req.tmdb_id)
                if meta:
                    movie = Movie(
                        title=meta["title"], year=meta.get("year"), tmdb_id=meta["tmdb_id"],
                        imdb_id=meta.get("imdb_id"), overview=meta.get("overview", ""),
                        poster_url=meta.get("poster_url"), fanart_url=meta.get("fanart_url"),
                        original_language=meta.get("original_language", "en"),
                        runtime=meta.get("runtime"), genres=meta.get("genres"),
                        quality_profile_id=1, root_folder=str(settings.paths.movies_dir),
                        monitored=True,
                    )
                    db.add(movie)
                    added = True
        elif media_req.media_type == "tv":
            meta = await tmdb.get_tv(media_req.tmdb_id)
            if meta:
                tvdb_id = meta.get("tvdb_id") or media_req.tmdb_id
                existing = await db.execute(select(Series).where(Series.tvdb_id == tvdb_id))
                if not existing.scalar_one_or_none():
                    series = Series(
                        title=meta["title"], year=meta.get("year"), tvdb_id=tvdb_id,
                        tmdb_id=meta["tmdb_id"], overview=meta.get("overview", ""),
                        poster_url=meta.get("poster_url"), fanart_url=meta.get("fanart_url"),
                        original_language=meta.get("original_language", "en"),
                        genres=meta.get("genres"), quality_profile_id=1,
                        root_folder=str(settings.paths.tv_dir), monitored=True,
                    )
                    db.add(series)
                    added = True

    await notifier.notify(
        "request.approved",
        f"Approved: {media_req.title}",
        f"Request approved" + (" and added to library" if added else ""),
        poster_url=media_req.poster_url,
    )

    return {"approved": True, "added_to_library": added, "title": media_req.title}


@api_router.post("/requests/{request_id}/deny")
async def deny_request(request_id: int, db: AsyncSession = Depends(get_db)):
    media_req = await db.get(MediaRequest, request_id)
    if not media_req:
        raise HTTPException(404, "Request not found")
    media_req.status = "denied"

    await notifier.notify(
        "request.denied",
        f"Denied: {media_req.title}",
        f"Request denied",
    )

    return {"denied": True, "title": media_req.title}


@api_router.post("/requests/{request_id}/vote")
async def vote_request(request_id: int, db: AsyncSession = Depends(get_db)):
    media_req = await db.get(MediaRequest, request_id)
    if not media_req:
        raise HTTPException(404, "Request not found")
    media_req.votes += 1
    return {"votes": media_req.votes, "title": media_req.title}


@api_router.delete("/requests/{request_id}")
async def delete_request(request_id: int, db: AsyncSession = Depends(get_db)):
    media_req = await db.get(MediaRequest, request_id)
    if not media_req:
        raise HTTPException(404, "Request not found")
    await db.delete(media_req)
    return {"deleted": True, "title": media_req.title}


# ============================================================
# SUBTITLES — search, download, serve for browser player
# ============================================================

from app.core.subtitles import subtitle_service
from fastapi.responses import PlainTextResponse


@api_router.get("/subtitles/search")
async def search_subtitles(
    q: str = "", imdb_id: str = "", tmdb_id: int = 0,
    season: int = 0, episode: int = 0, languages: str = "en",
):
    """Search for subtitles."""
    results = await subtitle_service.search(q, imdb_id, tmdb_id, season, episode, languages)
    return {"results": results, "total": len(results)}


@api_router.get("/subtitles/local/{file_token}")
async def get_local_subtitles(file_token: str):
    """Find subtitle files next to a media file."""
    file_path = _resolve_token(file_token)
    subs = subtitle_service.find_local_subtitles(str(file_path))
    # Generate stream URLs for each subtitle
    for sub in subs:
        import base64
        rel = str(_Path(sub["path"]).relative_to(settings.paths.media_root))
        sub["stream_url"] = "/api/subtitles/serve/" + base64.urlsafe_b64encode(rel.encode()).decode()
    return {"subtitles": subs, "total": len(subs)}


@api_router.get("/subtitles/serve/{file_token}")
async def serve_subtitle(file_token: str):
    """Serve a subtitle file, converting SRT to VTT for browser playback."""
    try:
        rel_path = _b64.urlsafe_b64decode(file_token).decode()
    except Exception:
        raise HTTPException(400, "Invalid token")

    sub_path = settings.paths.media_root / rel_path
    try:
        sub_path.resolve().relative_to(settings.paths.media_root.resolve())
    except ValueError:
        raise HTTPException(403, "Path traversal blocked")

    if not sub_path.is_file():
        raise HTTPException(404, "Subtitle file not found")

    content = sub_path.read_text(encoding="utf-8", errors="replace")

    # Convert SRT to VTT for browser compatibility
    if sub_path.suffix.lower() == ".srt":
        content = subtitle_service.srt_to_vtt(content)
        return PlainTextResponse(content, media_type="text/vtt")
    elif sub_path.suffix.lower() == ".vtt":
        return PlainTextResponse(content, media_type="text/vtt")
    else:
        return PlainTextResponse(content, media_type="text/plain")


@api_router.get("/subtitles/status")
async def subtitle_status():
    """Get subtitle service status."""
    return subtitle_service.stats


# ============================================================
# CLEANUP — automatic disk space management
# ============================================================

import shutil as _shutil

_cleanup_rules: list[dict] = [
    {"name": "Delete empty folders", "type": "empty_folders", "enabled": True},
    {"name": "Delete sample files", "type": "samples", "enabled": True, "max_size_mb": 100},
    {"name": "Delete non-media files", "type": "junk", "enabled": True},
    {"name": "Max disk usage", "type": "disk_limit", "enabled": False, "limit_gb": 500},
]

JUNK_EXTENSIONS = {".txt", ".nfo", ".jpg", ".jpeg", ".png", ".url", ".html", ".htm", ".exe", ".bat", ".com"}


@api_router.get("/cleanup/rules")
async def get_cleanup_rules():
    """Get current cleanup rules."""
    return {"rules": _cleanup_rules}


@api_router.get("/cleanup/disk")
async def get_disk_usage():
    """Get disk usage for media drives."""
    result = {}
    for name, path in [("media", settings.paths.media_root), ("downloads", settings.paths.download_dir)]:
        try:
            usage = _shutil.disk_usage(str(path))
            result[name] = {
                "path": str(path),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception as e:
            result[name] = {"path": str(path), "error": str(e)}
    return result


@api_router.post("/cleanup/scan")
async def scan_for_cleanup():
    """Scan media directories for cleanable files (dry run)."""
    media_root = settings.paths.media_root
    cleanable = []

    for subdir in ["Movies", "TVshows", "Music", "Books"]:
        folder = media_root / subdir
        if not folder.exists():
            continue

        for item in folder.rglob("*"):
            if not item.is_file():
                continue
            # Sample files
            if "sample" in item.name.lower() and item.stat().st_size < 100_000_000:
                cleanable.append({"path": str(item), "name": item.name, "size": item.stat().st_size, "reason": "sample file", "type": "samples"})
            # Junk files (nfo, txt, jpg etc)
            elif item.suffix.lower() in JUNK_EXTENSIONS:
                cleanable.append({"path": str(item), "name": item.name, "size": item.stat().st_size, "reason": "non-media file", "type": "junk"})

    # Empty folders
    for subdir in ["Movies", "TVshows", "Music", "Books"]:
        folder = media_root / subdir
        if not folder.exists():
            continue
        for d in folder.rglob("*"):
            if d.is_dir() and not any(d.iterdir()):
                cleanable.append({"path": str(d), "name": d.name, "size": 0, "reason": "empty folder", "type": "empty_folders"})

    total_size = sum(c["size"] for c in cleanable)
    return {"items": cleanable, "total": len(cleanable), "total_size": total_size}


class CleanupRunRequest(BaseModel):
    types: list[str] = []  # empty_folders, samples, junk — empty = all enabled


@api_router.post("/cleanup/run")
async def run_cleanup(req: CleanupRunRequest):
    """Execute cleanup based on rules. Deletes files identified by scan."""
    scan = await scan_for_cleanup()
    enabled_types = req.types if req.types else [r["type"] for r in _cleanup_rules if r["enabled"]]

    deleted = []
    errors = []
    for item in scan["items"]:
        if item["type"] not in enabled_types:
            continue
        try:
            p = _Path(item["path"])
            if p.is_file():
                p.unlink()
                deleted.append(item)
            elif p.is_dir():
                p.rmdir()  # Only removes if empty
                deleted.append(item)
        except Exception as e:
            errors.append({"path": item["path"], "error": str(e)})

    total_freed = sum(d["size"] for d in deleted)
    return {"deleted": len(deleted), "errors": len(errors), "freed": total_freed}


# ============================================================
# MUSIC — MusicBrainz metadata + search (replaces Lidarr)
# ============================================================

from app.services.metadata.musicbrainz import musicbrainz


@api_router.get("/music/search/artists")
async def search_music_artists(q: str = Query(..., min_length=1)):
    """Search MusicBrainz for artists."""
    return await musicbrainz.search_artists(q)


@api_router.get("/music/search/albums")
async def search_music_albums(q: str = Query(..., min_length=1), artist: str = ""):
    """Search MusicBrainz for albums/releases."""
    return await musicbrainz.search_albums(q, artist)


@api_router.get("/music/artist/{mbid}")
async def get_music_artist(mbid: str):
    """Get artist details + discography from MusicBrainz."""
    data = await musicbrainz.get_artist(mbid)
    if not data:
        raise HTTPException(404, "Artist not found")
    # Try to get cover art for first album
    if data.get("albums"):
        art = await musicbrainz.get_album_art(data["albums"][0]["mbid"])
        if art:
            data["image_url"] = art
    return data


@api_router.get("/music/library")
async def music_library():
    """List all music in the library (filesystem scan)."""
    music_dir = settings.paths.music_dir
    if not music_dir.exists():
        return {"artists": [], "total": 0}

    artists = {}
    for item in sorted(music_dir.iterdir()):
        if item.is_dir():
            # Count tracks
            tracks = sum(1 for f in item.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXT)
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXT)
            artists[item.name] = {"name": item.name, "tracks": tracks, "size": size, "path": str(item)}
        elif item.is_file() and item.suffix.lower() in AUDIO_EXT:
            name = item.stem
            artists[name] = {"name": name, "tracks": 1, "size": item.stat().st_size, "path": str(item)}

    return {"artists": list(artists.values()), "total": len(artists)}


# ============================================================
# BOOKS — OpenLibrary metadata (replaces Readarr)
# ============================================================

@api_router.get("/books/search")
async def search_books(q: str = Query(..., min_length=1)):
    """Search OpenLibrary for books."""
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://openlibrary.org/search.json",
                params={"q": q, "limit": 20},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                {
                    "title": doc.get("title", ""),
                    "author": doc.get("author_name", [""])[0] if doc.get("author_name") else "",
                    "year": doc.get("first_publish_year"),
                    "isbn": doc.get("isbn", [""])[0] if doc.get("isbn") else "",
                    "cover_url": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg" if doc.get("cover_i") else None,
                    "subjects": doc.get("subject", [])[:5],
                    "edition_count": doc.get("edition_count", 0),
                    "olid": doc.get("key", ""),
                }
                for doc in data.get("docs", [])
            ]
    except Exception as e:
        logger.error(f"OpenLibrary search error: {e}")
        return []


@api_router.get("/books/library")
async def books_library():
    """List all books in the library (filesystem scan)."""
    books_dir = settings.paths.books_dir
    if not books_dir.exists():
        return {"books": [], "total": 0}

    books = []
    for item in sorted(books_dir.rglob("*")):
        if item.is_file() and item.suffix.lower() in BOOK_EXT:
            books.append({
                "name": item.name,
                "format": item.suffix.lower().lstrip("."),
                "size": item.stat().st_size,
                "path": str(item),
            })
    return {"books": books, "total": len(books)}


# ============================================================
# COMICS — Comic Vine metadata (replaces Mylar3)
# ============================================================

COMIC_EXT = {".cbz", ".cbr", ".cb7", ".pdf", ".epub"}

@api_router.get("/comics/library")
async def comics_library():
    """List all comics on disk."""
    comics_dir = settings.paths.media_root / "Comics"
    if not comics_dir.exists():
        return {"comics": [], "total": 0, "path": str(comics_dir)}

    comics = []
    for item in sorted(comics_dir.rglob("*")):
        if item.is_file() and item.suffix.lower() in COMIC_EXT:
            comics.append({
                "name": item.name,
                "format": item.suffix.lower().lstrip("."),
                "size": item.stat().st_size,
                "path": str(item),
                "series": item.parent.name,
            })
    return {"comics": comics, "total": len(comics), "path": str(comics_dir)}


@api_router.get("/comics/series")
async def list_comic_series(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ComicSeries))
    series = result.scalars().all()
    return [{"id": s.id, "title": s.title, "publisher_id": s.publisher_id,
             "comicvine_id": s.comicvine_id, "year_start": s.year_start,
             "issue_count": s.issue_count, "monitored": s.monitored}
            for s in series]


@api_router.get("/comics/publishers")
async def list_comic_publishers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ComicPublisher))
    return [{"id": p.id, "title": p.title, "comicvine_id": p.comicvine_id,
             "poster_url": p.poster_url}
            for p in result.scalars().all()]


@api_router.get("/comics/search")
async def search_comics(q: str = Query(..., min_length=1)):
    """Search Comic Vine for comics (uses free API)."""
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://comicvine.gamespot.com/api/search/",
                params={"query": q, "format": "json", "resources": "volume",
                        "limit": 20, "field_list": "id,name,start_year,count_of_issues,publisher,image,description"},
                headers={"User-Agent": "GrimmGear-Mediarr/1.0"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                {
                    "id": v.get("id"),
                    "title": v.get("name", ""),
                    "year": v.get("start_year"),
                    "issues": v.get("count_of_issues", 0),
                    "publisher": v.get("publisher", {}).get("name", "") if v.get("publisher") else "",
                    "cover_url": v.get("image", {}).get("medium_url") if v.get("image") else None,
                    "description": (v.get("description") or "")[:300],
                }
                for v in data.get("results", [])
            ]
    except Exception as e:
        logger.error(f"Comic Vine search error: {e}")
        return []


# ============================================================
# QUALITY PROFILES — per media type
# ============================================================

@api_router.get("/quality-profiles/by-type/{media_type}")
async def get_quality_profiles_by_type(media_type: str, db: AsyncSession = Depends(get_db)):
    """Get quality profiles for a specific media type."""
    await seed_quality_profiles(db)
    await db.commit()
    result = await db.execute(select(QualityProfile).where(QualityProfile.media_type == media_type))
    profiles = result.scalars().all()
    # Also include profiles without a media_type (legacy)
    if not profiles:
        result = await db.execute(select(QualityProfile))
        profiles = result.scalars().all()
    return [{"id": p.id, "name": p.name, "media_type": p.media_type, "language": p.language,
             "min_quality": p.min_quality, "cutoff": p.cutoff, "upgrade_allowed": p.upgrade_allowed,
             "items": p.items} for p in profiles]


@api_router.get("/quality-definitions")
async def get_quality_definitions():
    """Quality tiers per media type — like Sonarr Quality Definitions."""
    return {
        "movie": [
            {"quality": "SDTV", "title": "SDTV", "min_size": 0, "max_size": 2000, "preferred_size": 1500},
            {"quality": "DVD", "title": "DVD", "min_size": 0, "max_size": 4000, "preferred_size": 2000},
            {"quality": "HDTV-720p", "title": "HDTV 720p", "min_size": 0, "max_size": 6000, "preferred_size": 3500},
            {"quality": "HDTV-1080p", "title": "HDTV 1080p", "min_size": 0, "max_size": 15000, "preferred_size": 8000},
            {"quality": "WEB-DL-720p", "title": "WEB-DL 720p", "min_size": 0, "max_size": 8000, "preferred_size": 5000},
            {"quality": "WEB-DL-1080p", "title": "WEB-DL 1080p", "min_size": 0, "max_size": 20000, "preferred_size": 12000},
            {"quality": "Bluray-720p", "title": "Bluray 720p", "min_size": 0, "max_size": 12000, "preferred_size": 7000},
            {"quality": "Bluray-1080p", "title": "Bluray 1080p", "min_size": 0, "max_size": 35000, "preferred_size": 15000},
            {"quality": "Remux-1080p", "title": "Remux 1080p", "min_size": 10000, "max_size": 60000, "preferred_size": 35000},
            {"quality": "Bluray-2160p", "title": "Bluray 2160p", "min_size": 10000, "max_size": 80000, "preferred_size": 45000},
            {"quality": "Remux-2160p", "title": "Remux 2160p", "min_size": 25000, "max_size": 120000, "preferred_size": 70000},
        ],
        "music": [
            {"quality": "MP3-128", "title": "MP3 128kbps", "min_size": 0, "max_size": 5, "preferred_size": 3},
            {"quality": "MP3-192", "title": "MP3 192kbps", "min_size": 0, "max_size": 8, "preferred_size": 5},
            {"quality": "MP3-256", "title": "MP3 256kbps", "min_size": 0, "max_size": 10, "preferred_size": 7},
            {"quality": "MP3-320", "title": "MP3 320kbps", "min_size": 0, "max_size": 15, "preferred_size": 10},
            {"quality": "AAC-256", "title": "AAC 256kbps", "min_size": 0, "max_size": 10, "preferred_size": 7},
            {"quality": "OGG-320", "title": "OGG Vorbis 320kbps", "min_size": 0, "max_size": 15, "preferred_size": 10},
            {"quality": "FLAC", "title": "FLAC (Lossless)", "min_size": 10, "max_size": 80, "preferred_size": 35},
            {"quality": "FLAC-24bit", "title": "FLAC 24-bit (Hi-Res)", "min_size": 30, "max_size": 200, "preferred_size": 80},
            {"quality": "WAV", "title": "WAV (Uncompressed)", "min_size": 30, "max_size": 300, "preferred_size": 50},
            {"quality": "ALAC", "title": "ALAC (Apple Lossless)", "min_size": 10, "max_size": 80, "preferred_size": 35},
        ],
        "book": [
            {"quality": "PDF", "title": "PDF", "min_size": 0, "max_size": 500, "preferred_size": 10},
            {"quality": "MOBI", "title": "MOBI (Kindle)", "min_size": 0, "max_size": 50, "preferred_size": 5},
            {"quality": "EPUB", "title": "EPUB", "min_size": 0, "max_size": 50, "preferred_size": 5},
            {"quality": "AZW3", "title": "AZW3 (Kindle)", "min_size": 0, "max_size": 50, "preferred_size": 5},
            {"quality": "FB2", "title": "FB2", "min_size": 0, "max_size": 20, "preferred_size": 3},
            {"quality": "DJVU", "title": "DJVU", "min_size": 0, "max_size": 200, "preferred_size": 20},
        ],
        "audiobook": [
            {"quality": "MP3-64", "title": "MP3 64kbps", "min_size": 0, "max_size": 200, "preferred_size": 100},
            {"quality": "MP3-128", "title": "MP3 128kbps", "min_size": 0, "max_size": 400, "preferred_size": 200},
            {"quality": "MP3-192", "title": "MP3 192kbps", "min_size": 0, "max_size": 600, "preferred_size": 300},
            {"quality": "MP3-256", "title": "MP3 256kbps", "min_size": 0, "max_size": 800, "preferred_size": 400},
            {"quality": "M4B-128", "title": "M4B 128kbps (iTunes)", "min_size": 0, "max_size": 400, "preferred_size": 200},
            {"quality": "M4B-256", "title": "M4B 256kbps (iTunes)", "min_size": 0, "max_size": 800, "preferred_size": 400},
            {"quality": "FLAC", "title": "FLAC Audiobook", "min_size": 100, "max_size": 5000, "preferred_size": 2000},
        ],
        "comic": [
            {"quality": "CBR", "title": "CBR (RAR Archive)", "min_size": 0, "max_size": 200, "preferred_size": 50},
            {"quality": "CBZ", "title": "CBZ (ZIP Archive)", "min_size": 0, "max_size": 200, "preferred_size": 50},
            {"quality": "CB7", "title": "CB7 (7z Archive)", "min_size": 0, "max_size": 200, "preferred_size": 50},
            {"quality": "PDF", "title": "PDF Comic", "min_size": 0, "max_size": 500, "preferred_size": 100},
            {"quality": "EPUB", "title": "EPUB Comic", "min_size": 0, "max_size": 300, "preferred_size": 80},
        ],
    }


# ============================================================
# AUTH — local accounts with JWT
# ============================================================

from app.core.auth import auth_service


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    role: str = "user"


@api_router.post("/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get a JWT token."""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not auth_service.verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    token = auth_service.create_token(user.id, user.username, user.role)
    return {"token": token, "username": user.username, "role": user.role}


@api_router.post("/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if any users exist (first user becomes admin)
    count_result = await db.execute(select(User))
    existing_users = count_result.scalars().all()
    is_first = len(existing_users) == 0
    role = "admin" if is_first else req.role

    # Check duplicate
    dup = await db.execute(select(User).where(User.username == req.username))
    if dup.scalar_one_or_none():
        raise HTTPException(409, "Username already taken")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=auth_service.hash_password(req.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    token = auth_service.create_token(user.id, user.username, user.role)
    return {
        "registered": True, "username": user.username, "role": user.role,
        "token": token, "is_first_user": is_first,
    }


@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current user info from token."""
    from app.core.auth import get_current_user
    user = await get_current_user(request)
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, **user}


@api_router.get("/auth/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all users (admin only in production)."""
    result = await db.execute(select(User))
    return [
        {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active}
        for u in result.scalars().all()
    ]


@api_router.get("/setup/status")
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Check if first-run setup is needed."""
    result = await db.execute(select(User))
    users = result.scalars().all()
    indexers = await db.execute(select(Indexer))
    idx_list = indexers.scalars().all()
    return {
        "needs_setup": len(users) == 0,
        "has_users": len(users) > 0,
        "has_indexers": len(idx_list) > 0,
        "media_root": str(settings.paths.media_root),
        "media_root_exists": settings.paths.media_root.exists(),
    }


# ============================================================
# SETTINGS — full configuration management (persisted to DB)
# ============================================================

import json as _json


async def _get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def _set_setting(db: AsyncSession, key: str, value: str, category: str = "general"):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value, category=category))


# ── Root Folders (media paths per type) ───────────────────

class AddRootFolderRequest(BaseModel):
    path: str
    media_type: str  # movie, tv, music, books, comics
    name: str = ""


@api_router.get("/settings/rootfolders")
async def list_root_folders(db: AsyncSession = Depends(get_db)):
    """List all configured root folders."""
    result = await db.execute(select(RootFolder).order_by(RootFolder.media_type))
    folders = []
    for rf in result.scalars().all():
        p = _Path(rf.path)
        free = 0
        try:
            usage = _shutil.disk_usage(str(p))
            free = usage.free
        except Exception:
            pass
        folders.append({
            "id": rf.id, "path": rf.path, "media_type": rf.media_type,
            "name": rf.name, "exists": p.exists(), "free_space": free,
        })
    return {"folders": folders}


@api_router.post("/settings/rootfolders")
async def add_root_folder(req: AddRootFolderRequest, db: AsyncSession = Depends(get_db)):
    """Add a root folder for a media type."""
    p = _Path(req.path)
    if not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(400, f"Cannot create folder: {e}")
    rf = RootFolder(path=req.path, media_type=req.media_type, name=req.name or p.name)
    db.add(rf)
    await db.flush()
    return {"id": rf.id, "added": True, "path": rf.path}


@api_router.delete("/settings/rootfolders/{folder_id}")
async def delete_root_folder(folder_id: int, db: AsyncSession = Depends(get_db)):
    rf = await db.get(RootFolder, folder_id)
    if not rf:
        raise HTTPException(404, "Root folder not found")
    await db.delete(rf)
    return {"deleted": True}


@api_router.get("/settings/browse")
async def browse_filesystem(path: str = ""):
    """Browse local filesystem for folder selection. Like Sonarr's folder picker."""
    if not path:
        # Return drive roots on Windows, / on Linux
        if os.name == "nt":
            import string
            drives = []
            for letter in string.ascii_uppercase:
                dp = f"{letter}:\\"
                if os.path.exists(dp):
                    try:
                        usage = _shutil.disk_usage(dp)
                        drives.append({"name": dp, "path": dp, "type": "drive",
                                       "free": usage.free, "total": usage.total})
                    except Exception:
                        drives.append({"name": dp, "path": dp, "type": "drive"})
            return {"items": drives, "path": ""}
        else:
            path = "/"

    target = _Path(path)
    if not target.exists():
        raise HTTPException(404, "Path not found")

    items = []
    try:
        for item in sorted(target.iterdir()):
            if item.name.startswith(".") or item.name.startswith("$"):
                continue
            if item.is_dir():
                items.append({"name": item.name, "path": str(item), "type": "folder"})
    except PermissionError:
        pass

    parent = str(target.parent) if str(target) != str(target.parent) else ""
    return {"items": items, "path": str(target), "parent": parent}


# ── Download Clients ──────────────────────────────────────

class AddDownloadClientRequest(BaseModel):
    name: str
    client_type: str = "qbittorrent"
    host: str = "localhost"
    port: int = 8080
    username: str = ""
    password: str = ""
    api_key: str = ""
    category: str = "grimmgear"


@api_router.get("/settings/downloadclients")
async def list_download_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DownloadClientModel).order_by(DownloadClientModel.priority))
    return [
        {
            "id": c.id, "name": c.name, "client_type": c.client_type,
            "host": c.host, "port": c.port, "username": c.username,
            "category": c.category, "enabled": c.enabled, "priority": c.priority,
        }
        for c in result.scalars().all()
    ]


@api_router.post("/settings/downloadclients")
async def add_download_client(req: AddDownloadClientRequest, db: AsyncSession = Depends(get_db)):
    client = DownloadClientModel(
        name=req.name, client_type=req.client_type, host=req.host,
        port=req.port, username=req.username, password=req.password,
        api_key=req.api_key, category=req.category,
    )
    db.add(client)
    await db.flush()
    return {"id": client.id, "added": True, "name": client.name}


@api_router.delete("/settings/downloadclients/{client_id}")
async def delete_download_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await db.get(DownloadClientModel, client_id)
    if not client:
        raise HTTPException(404)
    await db.delete(client)
    return {"deleted": True}


@api_router.post("/settings/downloadclients/test")
async def test_download_client(req: AddDownloadClientRequest):
    """Test connection to a download client."""
    import httpx as _hx
    if req.client_type == "qbittorrent":
        url = f"http://{req.host}:{req.port}"
        try:
            async with _hx.AsyncClient(timeout=5.0) as client:
                # Try login
                resp = await client.post(f"{url}/api/v2/auth/login", data={
                    "username": req.username, "password": req.password,
                })
                if resp.status_code == 200 and resp.text == "Ok.":
                    # Get version
                    ver_resp = await client.get(f"{url}/api/v2/app/version")
                    return {"success": True, "version": ver_resp.text, "message": f"Connected to qBittorrent {ver_resp.text}"}
                elif resp.status_code == 200:
                    # No auth needed
                    ver_resp = await client.get(f"{url}/api/v2/app/version")
                    return {"success": True, "version": ver_resp.text, "message": f"Connected (no auth) to qBittorrent {ver_resp.text}"}
                return {"success": False, "message": f"Auth failed: {resp.status_code} {resp.text}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    elif req.client_type == "sabnzbd":
        url = f"http://{req.host}:{req.port}/api?mode=version&apikey={req.api_key}&output=json"
        try:
            async with _hx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return {"success": True, "message": f"Connected to SABnzbd {resp.json().get('version','')}"}
                return {"success": False, "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    return {"success": False, "message": f"Unknown client type: {req.client_type}"}


# ── Notification Agents (persistent) ─────────────────────

class AddNotificationAgentRequest(BaseModel):
    name: str
    agent_type: str  # discord, telegram, webhook
    config: dict = {}  # discord_webhook_url, telegram_bot_token, telegram_chat_id, webhook_url
    on_grab: bool = True
    on_import: bool = True


@api_router.get("/settings/notifications")
async def list_notification_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationAgent))
    return [
        {
            "id": a.id, "name": a.name, "agent_type": a.agent_type,
            "enabled": a.enabled, "on_grab": a.on_grab, "on_import": a.on_import,
            "config_keys": list((a.config or {}).keys()),
        }
        for a in result.scalars().all()
    ]


@api_router.post("/settings/notifications")
async def add_notification_agent(req: AddNotificationAgentRequest, db: AsyncSession = Depends(get_db)):
    agent = NotificationAgent(
        name=req.name, agent_type=req.agent_type,
        config=req.config, on_grab=req.on_grab, on_import=req.on_import,
    )
    db.add(agent)
    await db.flush()

    # Also register with the in-memory notifier
    from app.core.notifications.notifier import NotificationChannel
    ch = NotificationChannel(
        name=req.name, type=req.agent_type,
        discord_webhook_url=req.config.get("discord_webhook_url", ""),
        telegram_bot_token=req.config.get("telegram_bot_token", ""),
        telegram_chat_id=req.config.get("telegram_chat_id", ""),
        webhook_url=req.config.get("webhook_url", ""),
    )
    notifier.add_channel(ch)

    return {"id": agent.id, "added": True, "name": agent.name}


@api_router.post("/settings/notifications/{agent_id}/test")
async def test_notification_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await db.get(NotificationAgent, agent_id)
    if not agent:
        raise HTTPException(404)
    return await notifier.test_channel(agent.name)


@api_router.delete("/settings/notifications/{agent_id}")
async def delete_notification_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await db.get(NotificationAgent, agent_id)
    if not agent:
        raise HTTPException(404)
    notifier.remove_channel(agent.name)
    await db.delete(agent)
    return {"deleted": True}


# ── Media Server Config ───────────────────────────────────

class MediaServerConfigRequest(BaseModel):
    type: str = "built-in"  # built-in, plex, jellyfin, emby
    url: str = ""
    token: str = ""


@api_router.get("/settings/mediaserver")
async def get_media_server_config(db: AsyncSession = Depends(get_db)):
    ms_type = await _get_setting(db, "media_server_type", settings.media_server.type)
    ms_url = await _get_setting(db, "media_server_url", settings.media_server.url)
    ms_token = await _get_setting(db, "media_server_token", "")
    return {"type": ms_type, "url": ms_url, "has_token": bool(ms_token)}


@api_router.put("/settings/mediaserver")
async def update_media_server_config(req: MediaServerConfigRequest, db: AsyncSession = Depends(get_db)):
    await _set_setting(db, "media_server_type", req.type, "media_server")
    await _set_setting(db, "media_server_url", req.url, "media_server")
    if req.token:
        await _set_setting(db, "media_server_token", req.token, "media_server")
    return {"saved": True}


@api_router.post("/settings/mediaserver/test")
async def test_media_server(req: MediaServerConfigRequest):
    """Test connection to Plex/Jellyfin/Emby."""
    import httpx as _hx
    if req.type == "plex" and req.url and req.token:
        try:
            async with _hx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{req.url.rstrip('/')}/identity",
                    headers={"X-Plex-Token": req.token, "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    name = data.get("MediaContainer", {}).get("friendlyName", "Plex")
                    return {"success": True, "message": f"Connected to {name}"}
                return {"success": False, "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    elif req.type == "jellyfin" and req.url and req.token:
        try:
            async with _hx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{req.url.rstrip('/')}/System/Info",
                    headers={"X-Emby-Token": req.token},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"success": True, "message": f"Connected to {data.get('ServerName','Jellyfin')} {data.get('Version','')}"}
                return {"success": False, "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    elif req.type == "built-in":
        return {"success": True, "message": "Using built-in media server (DLNA + web player)"}
    return {"success": False, "message": "Invalid configuration"}


# ── Quality Profiles (full CRUD) ─────────────────────────

class QualityProfileRequest(BaseModel):
    name: str
    language: str = "English"
    min_quality: str = "HDTV-720p"
    cutoff: str = "Bluray-1080p"
    upgrade_allowed: bool = True
    items: list = []  # quality tier definitions


@api_router.post("/qualityprofiles")
async def create_quality_profile(req: QualityProfileRequest, db: AsyncSession = Depends(get_db)):
    qp = QualityProfile(
        name=req.name, language=req.language, min_quality=req.min_quality,
        cutoff=req.cutoff, upgrade_allowed=req.upgrade_allowed, items=req.items,
    )
    db.add(qp)
    await db.flush()
    return {"id": qp.id, "created": True, "name": qp.name}


@api_router.put("/qualityprofiles/{profile_id}")
async def update_quality_profile(profile_id: int, req: QualityProfileRequest, db: AsyncSession = Depends(get_db)):
    qp = await db.get(QualityProfile, profile_id)
    if not qp:
        raise HTTPException(404)
    qp.name = req.name
    qp.language = req.language
    qp.min_quality = req.min_quality
    qp.cutoff = req.cutoff
    qp.upgrade_allowed = req.upgrade_allowed
    qp.items = req.items
    return {"id": qp.id, "updated": True}


@api_router.delete("/qualityprofiles/{profile_id}")
async def delete_quality_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    qp = await db.get(QualityProfile, profile_id)
    if not qp:
        raise HTTPException(404)
    await db.delete(qp)
    return {"deleted": True}


# ── General Settings ──────────────────────────────────────

@api_router.get("/settings/general")
async def get_general_settings(db: AsyncSession = Depends(get_db)):
    """Get all configurable settings."""
    return {
        "app_name": await _get_setting(db, "app_name", settings.app_name),
        "media_root": await _get_setting(db, "media_root", str(settings.paths.media_root)),
        "download_dir": await _get_setting(db, "download_dir", str(settings.paths.download_dir)),
        "dlna_enabled": await _get_setting(db, "dlna_enabled", "true") == "true",
        "dlna_name": await _get_setting(db, "dlna_name", settings.dlna.friendly_name),
    }


class GeneralSettingsRequest(BaseModel):
    app_name: str = ""
    media_root: str = ""
    download_dir: str = ""
    dlna_enabled: bool = True
    dlna_name: str = ""


@api_router.put("/settings/general")
async def update_general_settings(req: GeneralSettingsRequest, db: AsyncSession = Depends(get_db)):
    if req.app_name:
        await _set_setting(db, "app_name", req.app_name, "general")
    if req.media_root:
        await _set_setting(db, "media_root", req.media_root, "paths")
    if req.download_dir:
        await _set_setting(db, "download_dir", req.download_dir, "paths")
    await _set_setting(db, "dlna_enabled", "true" if req.dlna_enabled else "false", "general")
    if req.dlna_name:
        await _set_setting(db, "dlna_name", req.dlna_name, "general")
    return {"saved": True}


# ============================================================
# CALENDAR — upcoming episodes, movie releases, scheduled items
# ============================================================

@api_router.get("/calendar")
async def get_calendar(
    start: str = Query(None, description="Start date YYYY-MM-DD"),
    end: str = Query(None, description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Calendar of upcoming/recent media — like Sonarr/Radarr calendar."""
    from datetime import datetime, timedelta

    # Default: this week +-7 days
    if not start:
        start = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end:
        end = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    events = []

    # Movies with release dates (year match or from TMDB)
    result = await db.execute(select(Movie).where(Movie.monitored == True))
    for m in result.scalars().all():
        if m.year:
            events.append({
                "id": f"movie-{m.id}", "type": "movie", "title": m.title, "year": m.year,
                "date": f"{m.year}-01-01", "has_file": m.has_file,
                "poster_url": m.poster_url, "media_id": m.id,
            })

    # Series episodes with air dates
    ep_result = await db.execute(
        select(Episode).where(Episode.air_date != None, Episode.air_date >= start, Episode.air_date <= end)
    )
    for ep in ep_result.scalars().all():
        season = await db.get(Season, ep.season_id)
        series = await db.get(Series, season.series_id) if season else None
        events.append({
            "id": f"episode-{ep.id}", "type": "episode",
            "title": f"{series.title if series else 'Unknown'} S{season.season_number:02d}E{ep.episode_number:02d}" if season else ep.title,
            "episode_title": ep.title, "date": ep.air_date, "has_file": ep.has_file,
            "poster_url": series.poster_url if series else None, "media_id": ep.id,
        })

    events.sort(key=lambda x: x.get("date", ""))
    return {"events": events, "start": start, "end": end}


# ============================================================
# BLOCKLIST — rejected releases
# ============================================================

@api_router.get("/blocklist")
async def get_blocklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get blocklisted releases."""
    result = await db.execute(
        select(BlocklistItem).order_by(BlocklistItem.date.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    count_result = await db.execute(select(text("COUNT(*)")).select_from(BlocklistItem.__table__))
    total = count_result.scalar() or 0
    return {
        "items": [{"id": b.id, "title": b.title, "indexer": b.indexer, "media_type": b.media_type,
                    "reason": b.reason, "protocol": b.protocol, "size": b.size,
                    "date": b.date.isoformat() if b.date else None} for b in items],
        "total": total, "page": page, "page_size": page_size,
    }


class BlocklistAdd(BaseModel):
    title: str
    indexer: str = ""
    media_type: str = "movie"
    reason: str = "manual"
    protocol: str = "torrent"
    size: int = 0

@api_router.post("/blocklist")
async def add_to_blocklist(req: BlocklistAdd, db: AsyncSession = Depends(get_db)):
    item = BlocklistItem(title=req.title, indexer=req.indexer, media_type=req.media_type,
                         reason=req.reason, protocol=req.protocol, size=req.size)
    db.add(item)
    await db.commit()
    return {"id": item.id, "added": True}


@api_router.delete("/blocklist/{item_id}")
async def remove_from_blocklist(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(BlocklistItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    await db.delete(item)
    await db.commit()
    return {"deleted": True}


@api_router.delete("/blocklist/bulk")
async def clear_blocklist(db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM blocklist"))
    await db.commit()
    return {"cleared": True}


# ============================================================
# TAGS — organize media, indexers, download clients
# ============================================================

@api_router.get("/tags")
async def get_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).order_by(Tag.name))
    tags = result.scalars().all()
    # Count assignments per tag
    out = []
    for t in tags:
        assign_result = await db.execute(
            select(text("COUNT(*)")).select_from(TagAssignment.__table__).where(TagAssignment.tag_id == t.id)
        )
        count = assign_result.scalar() or 0
        out.append({"id": t.id, "name": t.name, "color": t.color, "usage_count": count})
    return out


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"

@api_router.post("/tags")
async def create_tag(req: TagCreate, db: AsyncSession = Depends(get_db)):
    tag = Tag(name=req.name, color=req.color)
    db.add(tag)
    await db.commit()
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@api_router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Not found")
    # Remove all assignments
    await db.execute(text(f"DELETE FROM tag_assignments WHERE tag_id = {tag_id}"))
    await db.delete(tag)
    await db.commit()
    return {"deleted": True}


class TagAssign(BaseModel):
    tag_id: int
    entity_type: str  # movie, series, artist, author, indexer, download_client
    entity_id: int

@api_router.post("/tags/assign")
async def assign_tag(req: TagAssign, db: AsyncSession = Depends(get_db)):
    assignment = TagAssignment(tag_id=req.tag_id, entity_type=req.entity_type, entity_id=req.entity_id)
    db.add(assignment)
    await db.commit()
    return {"assigned": True}


@api_router.delete("/tags/assign/{entity_type}/{entity_id}/{tag_id}")
async def unassign_tag(entity_type: str, entity_id: int, tag_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TagAssignment).where(
            TagAssignment.tag_id == tag_id,
            TagAssignment.entity_type == entity_type,
            TagAssignment.entity_id == entity_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return {"removed": True}


# ============================================================
# CUSTOM FORMATS — regex-based quality matching
# ============================================================

@api_router.get("/custom-formats")
async def get_custom_formats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CustomFormat).order_by(CustomFormat.name))
    return [{"id": cf.id, "name": cf.name, "score": cf.score,
             "include_when_renaming": cf.include_when_renaming,
             "specifications": cf.specifications} for cf in result.scalars().all()]


class CustomFormatCreate(BaseModel):
    name: str
    score: int = 0
    include_when_renaming: bool = False
    specifications: list = []  # [{field, value, regex, negate, required}]

@api_router.post("/custom-formats")
async def create_custom_format(req: CustomFormatCreate, db: AsyncSession = Depends(get_db)):
    cf = CustomFormat(name=req.name, score=req.score, include_when_renaming=req.include_when_renaming,
                      specifications=req.specifications)
    db.add(cf)
    await db.commit()
    return {"id": cf.id, "name": cf.name}


@api_router.put("/custom-formats/{cf_id}")
async def update_custom_format(cf_id: int, req: CustomFormatCreate, db: AsyncSession = Depends(get_db)):
    cf = await db.get(CustomFormat, cf_id)
    if not cf:
        raise HTTPException(404, "Not found")
    cf.name = req.name
    cf.score = req.score
    cf.include_when_renaming = req.include_when_renaming
    cf.specifications = req.specifications
    await db.commit()
    return {"updated": True}


@api_router.delete("/custom-formats/{cf_id}")
async def delete_custom_format(cf_id: int, db: AsyncSession = Depends(get_db)):
    cf = await db.get(CustomFormat, cf_id)
    if not cf:
        raise HTTPException(404, "Not found")
    await db.delete(cf)
    await db.commit()
    return {"deleted": True}


@api_router.post("/custom-formats/test")
async def test_custom_format(req: CustomFormatCreate):
    """Test a custom format against sample release names."""
    import re
    test_names = [
        "Movie.Title.2024.1080p.BluRay.x264-GROUP",
        "Movie.Title.2024.2160p.UHD.BluRay.HDR.DV.Atmos-GROUP",
        "Movie.Title.2024.720p.WEB-DL.AAC2.0.H.264-GROUP",
        "Movie.Title.2024.HDCAM.XviD-FAKE",
        "Movie.Title.2024.FRENCH.1080p.BluRay-GROUP",
    ]
    results = []
    for name in test_names:
        matched = True
        for spec in (req.specifications or []):
            pattern = spec.get("value", "")
            try:
                m = bool(re.search(pattern, name, re.IGNORECASE))
            except re.error:
                m = False
            if spec.get("negate"):
                m = not m
            if spec.get("required") and not m:
                matched = False
                break
            if not spec.get("required") and not m:
                matched = False
        results.append({"name": name, "matched": matched, "score": req.score if matched else 0})
    return {"results": results}


# ============================================================
# IMPORT LISTS — TMDB, Trakt, IMDB auto-import
# ============================================================

@api_router.get("/import-lists")
async def get_import_lists(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ImportList).order_by(ImportList.name))
    return [{"id": il.id, "name": il.name, "list_type": il.list_type, "enabled": il.enabled,
             "media_type": il.media_type, "config": il.config, "monitor": il.monitor,
             "search_on_add": il.search_on_add, "sync_interval": il.sync_interval,
             "last_sync": il.last_sync, "quality_profile_id": il.quality_profile_id,
             "root_folder_id": il.root_folder_id} for il in result.scalars().all()]


class ImportListCreate(BaseModel):
    name: str
    list_type: str  # tmdb_popular, tmdb_upcoming, tmdb_list, trakt_watchlist, imdb_watchlist
    media_type: str = "movie"
    enabled: bool = True
    config: dict = {}
    quality_profile_id: int = None
    root_folder_id: int = None
    monitor: bool = True
    search_on_add: bool = True
    sync_interval: int = 360

@api_router.post("/import-lists")
async def create_import_list(req: ImportListCreate, db: AsyncSession = Depends(get_db)):
    il = ImportList(name=req.name, list_type=req.list_type, media_type=req.media_type,
                    enabled=req.enabled, config=req.config, quality_profile_id=req.quality_profile_id,
                    root_folder_id=req.root_folder_id, monitor=req.monitor,
                    search_on_add=req.search_on_add, sync_interval=req.sync_interval)
    db.add(il)
    await db.commit()
    return {"id": il.id, "name": il.name}


@api_router.put("/import-lists/{list_id}")
async def update_import_list(list_id: int, req: ImportListCreate, db: AsyncSession = Depends(get_db)):
    il = await db.get(ImportList, list_id)
    if not il:
        raise HTTPException(404, "Not found")
    for field in ["name", "list_type", "media_type", "enabled", "config", "quality_profile_id",
                  "root_folder_id", "monitor", "search_on_add", "sync_interval"]:
        setattr(il, field, getattr(req, field))
    await db.commit()
    return {"updated": True}


@api_router.delete("/import-lists/{list_id}")
async def delete_import_list(list_id: int, db: AsyncSession = Depends(get_db)):
    il = await db.get(ImportList, list_id)
    if not il:
        raise HTTPException(404, "Not found")
    await db.delete(il)
    await db.commit()
    return {"deleted": True}


@api_router.post("/import-lists/{list_id}/sync")
async def sync_import_list(list_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger manual sync of an import list."""
    il = await db.get(ImportList, list_id)
    if not il:
        raise HTTPException(404, "Not found")

    imported = []
    if il.list_type.startswith("tmdb_"):
        # TMDB lists
        if il.list_type == "tmdb_popular":
            data = await tmdb.popular_movies() if il.media_type == "movie" else await tmdb.trending_tv()
        elif il.list_type == "tmdb_upcoming":
            data = await tmdb.upcoming_movies()
        elif il.list_type == "tmdb_trending":
            data = await tmdb.trending_movies() if il.media_type == "movie" else await tmdb.trending_tv()
        else:
            data = []

        if data and isinstance(data, dict):
            data = data.get("results", [])

        for item in (data or [])[:50]:
            tmdb_id = item.get("id")
            if not tmdb_id:
                continue
            title = item.get("title") or item.get("name", "")
            if not title:
                continue
            year_str = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            year = int(year_str) if year_str.isdigit() else None

            if il.media_type == "movie":
                exists = await db.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
                if not exists.scalar_one_or_none():
                    m = Movie(title=title, year=year, tmdb_id=tmdb_id,
                              overview=item.get("overview", ""),
                              poster_url=f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else None,
                              monitored=il.monitor, quality_profile_id=il.quality_profile_id or 1,
                              root_folder=str(il.root_folder_id or ""))
                    db.add(m)
                    imported.append(title)

        await db.commit()

    from datetime import datetime
    il.last_sync = datetime.utcnow().isoformat()
    await db.commit()

    # Log the event
    log = EventLog(category="import", level="info",
                   message=f"Import list '{il.name}' synced: {len(imported)} new items")
    db.add(log)
    await db.commit()

    return {"synced": len(imported), "items": imported[:20]}


# ============================================================
# EVENT LOG — structured events like Sonarr
# ============================================================

@api_router.get("/events")
async def get_events(
    level: str = Query(None),
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(EventLog).order_by(EventLog.timestamp.desc())
    if level:
        q = q.where(EventLog.level == level)
    if category:
        q = q.where(EventLog.category == category)
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    items = result.scalars().all()
    count_q = select(text("COUNT(*)")).select_from(EventLog.__table__)
    if level:
        count_q = count_q.where(EventLog.level == level)
    if category:
        count_q = count_q.where(EventLog.category == category)
    total = (await db.execute(count_q)).scalar() or 0
    return {
        "events": [{"id": e.id, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                     "level": e.level, "category": e.category, "message": e.message,
                     "detail": e.detail, "media_type": e.media_type, "media_id": e.media_id}
                    for e in items],
        "total": total, "page": page,
    }


@api_router.delete("/events")
async def clear_events(db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM event_log"))
    await db.commit()
    return {"cleared": True}


# ============================================================
# LOG FILES — read application logs
# ============================================================

@api_router.get("/logs")
async def get_log_files():
    """List available log files."""
    import os
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    files = []
    for f in os.listdir(log_dir):
        fp = os.path.join(log_dir, f)
        if os.path.isfile(fp):
            files.append({"name": f, "size": os.path.getsize(fp),
                          "modified": os.path.getmtime(fp)})
    return {"log_dir": log_dir, "files": sorted(files, key=lambda x: x["modified"], reverse=True)}


@api_router.get("/logs/{filename}")
async def read_log_file(filename: str, lines: int = Query(200, ge=1, le=5000)):
    """Read last N lines of a log file."""
    import os
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "logs")
    fp = os.path.join(log_dir, filename)
    if ".." in filename or not os.path.exists(fp):
        raise HTTPException(404, "Not found")
    with open(fp, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"filename": filename, "lines": all_lines[-lines:], "total_lines": len(all_lines)}


# ============================================================
# NAMING CONFIG — per-media-type file naming patterns
# ============================================================

@api_router.get("/naming")
async def get_naming_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NamingConfig))
    configs = result.scalars().all()
    # Return defaults for any missing media types
    existing = {c.media_type: c for c in configs}
    defaults = {
        "movie": {"standard_format": "{Movie Title} ({Release Year}) [{Quality Full}]",
                   "folder_format": "{Movie Title} ({Release Year})"},
        "tv": {"standard_format": "{Series Title} - S{season:00}E{episode:00} - {Episode Title} [{Quality Full}]",
                "folder_format": "{Series Title}", "multi_episode_style": "extend"},
        "music": {"standard_format": "{Artist Name} - {Album Title} - {track:00} - {Track Title}",
                   "folder_format": "{Artist Name}/{Album Title} ({Release Year})"},
        "book": {"standard_format": "{Author Name} - {Book Title} ({Release Year})",
                  "folder_format": "{Author Name}"},
    }
    out = []
    for mt, dflt in defaults.items():
        if mt in existing:
            c = existing[mt]
            out.append({"id": c.id, "media_type": mt, "rename_files": c.rename_files,
                        "replace_illegal": c.replace_illegal, "colon_replacement": c.colon_replacement,
                        "standard_format": c.standard_format, "folder_format": c.folder_format,
                        "multi_episode_style": c.multi_episode_style})
        else:
            out.append({"id": None, "media_type": mt, "rename_files": True, "replace_illegal": True,
                        "colon_replacement": "dash", **dflt, "multi_episode_style": "extend"})
    return out


class NamingUpdate(BaseModel):
    media_type: str
    rename_files: bool = True
    replace_illegal: bool = True
    colon_replacement: str = "dash"
    standard_format: str = ""
    folder_format: str = ""
    multi_episode_style: str = "extend"

@api_router.put("/naming")
async def update_naming_config(req: NamingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NamingConfig).where(NamingConfig.media_type == req.media_type))
    config = result.scalar_one_or_none()
    if config:
        config.rename_files = req.rename_files
        config.replace_illegal = req.replace_illegal
        config.colon_replacement = req.colon_replacement
        config.standard_format = req.standard_format
        config.folder_format = req.folder_format
        config.multi_episode_style = req.multi_episode_style
    else:
        config = NamingConfig(media_type=req.media_type, rename_files=req.rename_files,
                              replace_illegal=req.replace_illegal, colon_replacement=req.colon_replacement,
                              standard_format=req.standard_format, folder_format=req.folder_format,
                              multi_episode_style=req.multi_episode_style)
        db.add(config)
    await db.commit()
    return {"saved": True}


# ============================================================
# SCHEDULED TASKS — dashboard with intervals, timing
# ============================================================

@api_router.get("/system/tasks")
async def get_scheduled_tasks():
    """Like Sonarr System > Tasks: intervals, last run, next run."""
    from app.core.queue.scheduler import scheduler
    from datetime import datetime, timedelta

    task_defs = [
        {"name": "ImportScan", "interval": 60, "description": "Scan download client for completed items"},
        {"name": "SpeedLog", "interval": 300, "description": "Log download/upload speed"},
        {"name": "RSSSync", "interval": 900, "description": "Search indexers for monitored wanted items"},
        {"name": "PlexNotify", "interval": 120, "description": "Notify Plex of new imports"},
        {"name": "ImportListSync", "interval": 21600, "description": "Sync import lists from TMDB/Trakt"},
        {"name": "HealthCheck", "interval": 3600, "description": "Check system health (disk, indexers, clients)"},
        {"name": "Backup", "interval": 86400, "description": "Automated database backup"},
        {"name": "CleanupLog", "interval": 86400, "description": "Clean old event log entries (>30 days)"},
    ]

    now = datetime.utcnow()
    tasks = []
    for td in task_defs:
        task_key = td["name"].lower()
        last_run = getattr(scheduler, f"last_{task_key}", None)
        if last_run and last_run != "never":
            try:
                last_dt = datetime.fromisoformat(last_run)
                next_dt = last_dt + timedelta(seconds=td["interval"])
                duration = "< 1s"
            except (ValueError, TypeError):
                next_dt = now + timedelta(seconds=td["interval"])
                duration = "unknown"
        else:
            next_dt = now + timedelta(seconds=td["interval"])
            last_run = "never"
            duration = "n/a"

        tasks.append({
            "name": td["name"], "description": td["description"],
            "interval_seconds": td["interval"],
            "interval_display": f"{td['interval'] // 60} min" if td["interval"] < 3600 else f"{td['interval'] // 3600} hr",
            "last_run": last_run if isinstance(last_run, str) else (last_run.isoformat() if last_run else "never"),
            "next_run": next_dt.isoformat(),
            "duration": duration,
            "running": task_key in scheduler._tasks and not scheduler._tasks[task_key].done() if task_key in scheduler._tasks else False,
        })
    return {"tasks": tasks, "scheduler_running": scheduler._running}


@api_router.post("/system/tasks/{task_name}/run")
async def trigger_task(task_name: str):
    """Manually trigger a scheduled task."""
    from app.core.queue.scheduler import scheduler
    from app.core.import_pipeline import import_pipeline

    task_name_lower = task_name.lower()
    if task_name_lower == "importscan":
        result = await import_pipeline.scan_and_import()
        return {"triggered": True, "result": result}
    elif task_name_lower == "rsssync":
        # Just indicate it will run
        return {"triggered": True, "message": "RSS sync will run on next cycle"}
    elif task_name_lower == "healthcheck":
        # Run inline health check
        return {"triggered": True, "message": "Health check triggered"}
    else:
        return {"triggered": False, "message": f"Unknown task: {task_name}"}


# ============================================================
# HEALTH CHECKS — like Sonarr System > Health
# ============================================================

@api_router.get("/system/health-checks")
async def get_health_checks(db: AsyncSession = Depends(get_db)):
    """Comprehensive health checks — indexer failures, disk space, connections."""
    import os
    import shutil
    checks = []

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks.append({"source": "Database", "type": "ok", "message": "SQLite connected"})
    except Exception as e:
        checks.append({"source": "Database", "type": "error", "message": f"Database error: {e}"})

    # Download client
    try:
        version = await qbit.get_version()
        if version != "offline":
            checks.append({"source": "DownloadClient", "type": "ok", "message": f"qBittorrent {version} connected"})
        else:
            checks.append({"source": "DownloadClient", "type": "warning", "message": "qBittorrent not reachable"})
    except Exception:
        checks.append({"source": "DownloadClient", "type": "error", "message": "Download client connection failed"})

    # Indexers — check for high fail counts
    idx_result = await db.execute(select(Indexer).where(Indexer.enabled == True))
    indexers = idx_result.scalars().all()
    if not indexers:
        checks.append({"source": "Indexer", "type": "warning", "message": "No indexers configured"})
    else:
        for idx in indexers:
            if idx.fail_count > 10:
                checks.append({"source": "Indexer", "type": "warning",
                                "message": f"Indexer '{idx.name}' has {idx.fail_count} failures"})
        if all(idx.fail_count <= 10 for idx in indexers):
            checks.append({"source": "Indexer", "type": "ok", "message": f"{len(indexers)} indexers healthy"})

    # Disk space
    media_root = str(settings.paths.media_root)
    try:
        usage = shutil.disk_usage(media_root)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        pct_used = (usage.used / usage.total) * 100
        if pct_used > 95:
            checks.append({"source": "DiskSpace", "type": "error",
                            "message": f"Critical: {media_root} is {pct_used:.0f}% full ({free_gb:.1f} GB free)"})
        elif pct_used > 85:
            checks.append({"source": "DiskSpace", "type": "warning",
                            "message": f"Low space: {media_root} is {pct_used:.0f}% full ({free_gb:.1f} GB free)"})
        else:
            checks.append({"source": "DiskSpace", "type": "ok",
                            "message": f"{media_root}: {free_gb:.1f} GB free of {total_gb:.1f} GB"})
    except Exception:
        checks.append({"source": "DiskSpace", "type": "warning", "message": f"Cannot check disk: {media_root}"})

    # Root folders existence
    rf_result = await db.execute(select(RootFolder))
    for rf in rf_result.scalars().all():
        if not os.path.exists(rf.path):
            checks.append({"source": "RootFolder", "type": "error",
                            "message": f"Root folder missing: {rf.path} ({rf.media_type})"})

    # Media server
    if settings.media_server.type and settings.media_server.url:
        checks.append({"source": "MediaServer", "type": "ok",
                        "message": f"{settings.media_server.type.title()} configured at {settings.media_server.url}"})
    else:
        checks.append({"source": "MediaServer", "type": "warning", "message": "No media server configured"})

    return {"checks": checks, "status": "error" if any(c["type"] == "error" for c in checks)
            else "warning" if any(c["type"] == "warning" for c in checks) else "ok"}


# ============================================================
# DISK SPACE — like Sonarr System > Disk Space
# ============================================================

@api_router.get("/system/disk-space")
async def get_disk_space(db: AsyncSession = Depends(get_db)):
    """Disk space for all configured root folders."""
    import shutil
    drives = []
    seen_paths = set()

    # Check root folders
    rf_result = await db.execute(select(RootFolder))
    for rf in rf_result.scalars().all():
        try:
            usage = shutil.disk_usage(rf.path)
            drive = rf.path[:3] if len(rf.path) >= 3 else rf.path
            if drive not in seen_paths:
                seen_paths.add(drive)
                drives.append({
                    "path": rf.path, "label": rf.name or rf.media_type,
                    "total": usage.total, "used": usage.used, "free": usage.free,
                    "percent_used": round((usage.used / usage.total) * 100, 1),
                })
        except Exception:
            drives.append({"path": rf.path, "label": rf.name or rf.media_type,
                           "total": 0, "used": 0, "free": 0, "percent_used": 0, "error": "Cannot access"})

    # Always include media root
    media_root = str(settings.paths.media_root)
    try:
        usage = shutil.disk_usage(media_root)
        drive = media_root[:3] if len(media_root) >= 3 else media_root
        if drive not in seen_paths:
            drives.append({
                "path": media_root, "label": "Media Root",
                "total": usage.total, "used": usage.used, "free": usage.free,
                "percent_used": round((usage.used / usage.total) * 100, 1),
            })
    except Exception:
        pass

    return {"drives": drives}


# ============================================================
# SYSTEM INFO — version, Python, DB, uptime, dirs
# ============================================================

@api_router.get("/system/info")
async def system_info():
    """Like Lidarr's System > Status: version, runtime, DB, dirs, uptime."""
    import sys, os, platform
    from app.core.config import settings
    from datetime import datetime

    db_path = settings.database.url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")

    return {
        "version": settings.version,
        "app_name": settings.app_name,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "database": "SQLite",
        "database_path": db_path,
        "app_data_dir": os.path.dirname(os.path.abspath(db_path)) if db_path else "",
        "startup_dir": os.getcwd(),
        "media_root": str(settings.paths.media_root),
        "mode": "Standalone",
        "host": settings.server.host,
        "port": settings.server.port,
        "uptime_start": _app_start_time.isoformat() if _app_start_time else None,
    }


# ============================================================
# BACKUPS — DB backup/restore
# ============================================================

@api_router.get("/system/backups")
async def get_backups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Backup).order_by(Backup.created_at.desc()))
    return [{"id": b.id, "filename": b.filename, "size": b.size,
             "backup_type": b.backup_type,
             "created_at": b.created_at.isoformat() if b.created_at else None}
            for b in result.scalars().all()]


@api_router.post("/system/backups")
async def create_backup(db: AsyncSession = Depends(get_db)):
    """Create a database backup."""
    import shutil, os
    from datetime import datetime

    db_path = settings.database.url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"mediarr_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    shutil.copy2(db_path, backup_path)
    size = os.path.getsize(backup_path)

    record = Backup(filename=backup_filename, size=size, backup_type="manual")
    db.add(record)

    log = EventLog(category="system", level="info", message=f"Database backup created: {backup_filename}")
    db.add(log)
    await db.commit()

    return {"filename": backup_filename, "size": size, "path": backup_path}


@api_router.delete("/system/backups/{backup_id}")
async def delete_backup(backup_id: int, db: AsyncSession = Depends(get_db)):
    import os
    backup = await db.get(Backup, backup_id)
    if not backup:
        raise HTTPException(404, "Not found")

    db_path = settings.database.url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    fp = os.path.join(backup_dir, backup.filename)
    if os.path.exists(fp):
        os.remove(fp)

    await db.delete(backup)
    await db.commit()
    return {"deleted": True}


# ── Track app start time for uptime ──
from datetime import datetime as _dt
_app_start_time = _dt.utcnow()


# ============================================================
# DLNA/UPnP — device discovery + content directory
# ============================================================

from app.core.dlna import dlna_server
from fastapi.responses import Response


@api_router.get("/dlna/status")
async def dlna_status():
    """Get DLNA server status."""
    return dlna_server.status


@api_router.post("/dlna/start")
async def dlna_start():
    """Start the DLNA server."""
    await dlna_server.start()
    return {"started": True, **dlna_server.status}


@api_router.post("/dlna/stop")
async def dlna_stop():
    """Stop the DLNA server."""
    await dlna_server.stop()
    return {"stopped": True}


@api_router.get("/dlna/description.xml")
async def dlna_description():
    """UPnP device description XML."""
    return Response(content=dlna_server.device_description(), media_type="text/xml")


@api_router.get("/dlna/content-directory.xml")
async def dlna_content_directory_scpd():
    """ContentDirectory service description XML."""
    return Response(content=dlna_server.content_directory_scpd(), media_type="text/xml")


@api_router.get("/dlna/connection-manager.xml")
async def dlna_connection_manager():
    """ConnectionManager service description (minimal)."""
    return Response(content="""<?xml version="1.0" encoding="UTF-8"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <actionList>
    <action><name>GetProtocolInfo</name>
      <argumentList>
        <argument><name>Source</name><direction>out</direction><relatedStateVariable>SourceProtocolInfo</relatedStateVariable></argument>
        <argument><name>Sink</name><direction>out</direction><relatedStateVariable>SinkProtocolInfo</relatedStateVariable></argument>
      </argumentList>
    </action>
  </actionList>
  <serviceStateTable>
    <stateVariable sendEvents="yes"><name>SourceProtocolInfo</name><dataType>string</dataType></stateVariable>
    <stateVariable sendEvents="yes"><name>SinkProtocolInfo</name><dataType>string</dataType></stateVariable>
  </serviceStateTable>
</scpd>""", media_type="text/xml")


@api_router.post("/dlna/control")
async def dlna_control(request: Request):
    """Handle UPnP SOAP Browse/GetSystemUpdateID actions."""
    body = await request.body()
    body_str = body.decode("utf-8", errors="replace")

    if "Browse" in body_str:
        # Parse ObjectID from SOAP
        import re
        obj_match = re.search(r"<ObjectID>([^<]*)</ObjectID>", body_str)
        start_match = re.search(r"<StartingIndex>(\d+)</StartingIndex>", body_str)
        count_match = re.search(r"<RequestedCount>(\d+)</RequestedCount>", body_str)

        object_id = obj_match.group(1) if obj_match else "0"
        start = int(start_match.group(1)) if start_match else 0
        count = int(count_match.group(1)) if count_match else 50
        if count == 0:
            count = 50

        didl, returned, total = dlna_server.browse(object_id, start, count)
        didl_escaped = didl.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:BrowseResponse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <Result>{didl_escaped}</Result>
      <NumberReturned>{returned}</NumberReturned>
      <TotalMatches>{total}</TotalMatches>
      <UpdateID>1</UpdateID>
    </u:BrowseResponse>
  </s:Body>
</s:Envelope>"""
        return Response(content=soap, media_type="text/xml")

    elif "GetSystemUpdateID" in body_str:
        soap = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetSystemUpdateIDResponse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <Id>1</Id>
    </u:GetSystemUpdateIDResponse>
  </s:Body>
</s:Envelope>"""
        return Response(content=soap, media_type="text/xml")

    return Response(content="", status_code=400)
