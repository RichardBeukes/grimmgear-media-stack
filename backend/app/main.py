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

from fastapi import FastAPI, HTTPException
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

    # Start background scheduler (import scans, RSS sync)
    from app.core.queue import scheduler
    await scheduler.start()
    logger.info("Background scheduler started")

    # Start DLNA server if streaming module is enabled
    streaming_mod = registry.get("streaming")
    if streaming_mod and streaming_mod.enabled and settings.dlna.enabled:
        from app.core.dlna import dlna_server
        await dlna_server.start()
        logger.info(f"DLNA server: {settings.dlna.friendly_name} — SSDP active on {dlna_server._local_ip}")

    logger.info(f"GrimmGear Mediarr ready at http://{settings.server.host}:{settings.server.port}")

    yield

    # Shutdown
    logger.info("Shutting down GrimmGear Mediarr...")
    from app.core.queue import scheduler
    await scheduler.stop()
    try:
        from app.core.dlna import dlna_server
        await dlna_server.stop()
    except Exception:
        pass

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

    # Security headers middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response as StarletteResponse

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            response: StarletteResponse = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # API routes
    app.include_router(api_router, prefix="/api")

    # Serve static files (CSS, JS)
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve the SPA frontend
    from fastapi.responses import HTMLResponse, FileResponse

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    # SPA catch-all — any non-API, non-static path serves index.html
    # This fixes 404 on page refresh for /movies, /settings, /downloads etc.
    @app.get("/{path:path}")
    async def spa_catchall(path: str):
        # Don't catch API or static routes
        if path.startswith("api/") or path.startswith("static/"):
            raise HTTPException(404)
        return FileResponse(os.path.join(static_dir, "index.html"))

    # Keep the old landing page at /about for reference
    @app.get("/about", response_class=HTMLResponse)
    async def about():
        modules = registry.status()
        enabled = [f'<span style="color:#27c24c">{v["display_name"]}</span>' for k, v in modules.items() if v["enabled"]]
        disabled = [f'<span style="color:#666">{v["display_name"]}</span>' for k, v in modules.items() if not v["enabled"]]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GrimmGear Media Stack</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#202020;color:#ccc;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.container{{max-width:640px;padding:40px}}
h1{{font-size:28px;font-weight:300;color:#e1e2e3;margin-bottom:8px}}
h1 b{{font-weight:700;background:linear-gradient(135deg,#35c5f4,#ffc230);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.version{{color:#666;font-size:13px;margin-bottom:32px}}
.section{{margin-bottom:24px}}
.section-title{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#666;margin-bottom:8px}}
.modules{{display:flex;flex-wrap:wrap;gap:8px}}
.modules span{{font-size:13px;padding:4px 12px;background:#333;border-radius:4px}}
.links{{margin-top:32px;display:flex;gap:16px}}
.links a{{color:#5d9cec;text-decoration:none;font-size:14px}}
.links a:hover{{text-decoration:underline}}
.tagline{{color:#555;font-size:13px;margin-top:24px;font-style:italic}}
</style>
</head>
<body>
<div class="container">
<h1><b>GrimmGear</b> Media Stack</h1>
<div class="version">v{settings.version} — One system. Every media type. Toggle what you need.</div>

<div class="section">
<div class="section-title">Enabled Modules</div>
<div class="modules">{" ".join(enabled)}</div>
</div>

<div class="section">
<div class="section-title">Available Modules</div>
<div class="modules">{" ".join(disabled)}</div>
</div>

<div class="links">
<a href="/api/docs">API Docs</a>
<a href="/api/system/status">System Status</a>
<a href="/api/modules">Module Registry</a>
<a href="/api/system/health">Health Check</a>
</div>

<div class="tagline">Replaces 30+ self-hosted media tools. Built on the *arr community's shoulders.</div>
</div>
</body>
</html>"""

    return app


# Create the app instance
app = create_app()
