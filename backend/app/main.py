"""
GrimmGear Media Stack — Main Application
One system. Every media type. Every feature. Toggle what you need.

Built on the shoulders of Sonarr, Radarr, Lidarr, Readarr, Prowlarr,
Bazarr, Tdarr, Seerr, Tautulli, Audiobookshelf, Kavita, SoulSync,
and the entire *arr community.

GrimmGear Systems — Richard Beukes
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import init_db, close_db
from app.modules.registry import registry
from app.api.routes import api_router

logger = logging.getLogger("grimmgear")


def register_modules():
    """Register all available modules with the registry."""
    from app.modules.registry import Module

    modules = [
        Module(
            name="movies",
            display_name="Movies",
            description="Movie automation with TMDB metadata, multi-version/edition support",
            enabled=settings.modules.movies,
        ),
        Module(
            name="tv",
            display_name="TV Shows",
            description="TV series automation with TVDB metadata, anime season packs, calendar",
            enabled=settings.modules.tv,
        ),
        Module(
            name="music",
            display_name="Music",
            description="Track-level music with 6 download sources, AcoustID, fake lossless detection",
            enabled=settings.modules.music,
        ),
        Module(
            name="books",
            display_name="Books",
            description="Ebooks + audiobooks + magazines with 5 metadata sources, OPDS, Calibre",
            enabled=settings.modules.books,
        ),
        Module(
            name="comics",
            display_name="Comics",
            description="Comic automation with Comic Vine metadata, story arc tracking",
            enabled=settings.modules.comics,
        ),
        Module(
            name="subtitles",
            display_name="Subtitles",
            description="Subtitle automation with 50+ providers, 184 languages",
            enabled=settings.modules.subtitles,
            dependencies=["movies", "tv"],
        ),
        Module(
            name="transcode",
            display_name="Transcode",
            description="Distributed transcoding/remuxing with FFmpeg, health checking",
            enabled=settings.modules.transcode,
        ),
        Module(
            name="requests",
            display_name="Requests",
            description="Discovery + request management with approval, voting, AI recommendations",
            enabled=settings.modules.requests,
        ),
        Module(
            name="indexers",
            display_name="Indexers",
            description="Built-in indexer management with CF bypass, IRC monitoring, rate limiting",
            enabled=settings.modules.indexers,
        ),
        Module(
            name="streaming",
            display_name="Streaming",
            description="Built-in DLNA/UPnP server, HLS web player, readers, cross-device sync",
            enabled=settings.modules.streaming,
        ),
    ]

    for mod in modules:
        registry.register(mod)

    enabled_names = [m.name for m in registry.get_enabled()]
    logger.info(f"Modules registered: {len(modules)} total, {len(enabled_names)} enabled: {enabled_names}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Database: {settings.database.url}")
    logger.info(f"Media root: {settings.paths.media_root}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Register and start modules
    register_modules()

    # Start enabled module lifecycle hooks
    for mod in registry.get_enabled():
        if mod.startup:
            await mod.startup()
            logger.info(f"Module started: {mod.name}")

    # Start DLNA server if streaming module is enabled
    streaming_mod = registry.get("streaming")
    if streaming_mod and streaming_mod.enabled and settings.dlna.enabled:
        logger.info(f"DLNA server: {settings.dlna.friendly_name} on port {settings.dlna.port}")

    logger.info(f"GrimmGear ready at http://{settings.server.host}:{settings.server.port}")

    yield

    # Shutdown
    logger.info("Shutting down GrimmGear...")
    for mod in registry.get_enabled():
        if mod.shutdown:
            await mod.shutdown()

    await close_db()
    logger.info("Goodbye.")


def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="One system. Every media type. Every feature. Toggle what you need.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router, prefix="/api")

    return app


# Create the app instance
app = create_app()
