"""
GrimmGear — Unified API Routes
ONE port. ONE interface. Everything lives here.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decision.engine import decision_engine
from app.core.download.qbit_client import qbit
from app.core.search.indexer_search import indexer_engine
from app.db.models import (
    Movie, Series, Season, Episode, Artist, Album, Track,
    Author, Book, QualityProfile, Indexer, DownloadQueueItem, User,
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
        QualityProfile(name="Any", language="English", min_quality="SDTV", cutoff="Bluray-1080p", upgrade_allowed=True),
        QualityProfile(name="HD-1080p", language="English", min_quality="HDTV-720p", cutoff="Bluray-1080p", upgrade_allowed=True),
        QualityProfile(name="Ultra-HD", language="English", min_quality="HDTV-1080p", cutoff="Remux-2160p", upgrade_allowed=True),
        QualityProfile(name="SD", language="English", min_quality="SDTV", cutoff="DVD", upgrade_allowed=False),
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
        }
        for i in result.scalars().all()
    ]


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
