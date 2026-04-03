"""
GrimmGear Mediarr — MusicBrainz Metadata Service
Artist and album metadata from MusicBrainz. Free, no API key needed.
Rate limit: 1 request/second (respect it!).
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger("grimmgear.musicbrainz")

MB_BASE = "https://musicbrainz.org/ws/2"
COVER_BASE = "https://coverartarchive.org"
USER_AGENT = "GrimmGear-Mediarr/0.1.0 (https://github.com/RichardBeukes/grimmgear-media-stack)"


class MusicBrainzService:
    """Search and fetch artist/album metadata from MusicBrainz."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=MB_BASE,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=10.0,
            )
        return self._client

    async def _get(self, path: str, params: dict = None) -> Optional[dict]:
        # Rate limit: 1 req/sec
        import time
        now = time.time()
        wait = max(0, 1.0 - (now - self._last_request))
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request = time.time()

        client = await self._get_client()
        p = params or {}
        p["fmt"] = "json"
        try:
            resp = await client.get(path, params=p)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"MusicBrainz {path} returned {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"MusicBrainz request failed: {e}")
            return None

    async def search_artists(self, query: str, limit: int = 10) -> list[dict]:
        data = await self._get("/artist/", {"query": query, "limit": limit})
        if not data:
            return []
        return [
            {
                "mbid": a.get("id"),
                "name": a.get("name", ""),
                "sort_name": a.get("sort-name", ""),
                "country": a.get("country", ""),
                "type": a.get("type", ""),
                "score": a.get("score", 0),
                "disambiguation": a.get("disambiguation", ""),
            }
            for a in data.get("artists", [])
        ]

    async def search_albums(self, query: str, artist: str = "", limit: int = 10) -> list[dict]:
        q = query
        if artist:
            q += f' AND artist:"{artist}"'
        data = await self._get("/release-group/", {"query": q, "limit": limit})
        if not data:
            return []
        return [
            {
                "mbid": rg.get("id"),
                "title": rg.get("title", ""),
                "type": rg.get("primary-type", "Album"),
                "artist": rg.get("artist-credit", [{}])[0].get("name", "") if rg.get("artist-credit") else "",
                "year": rg.get("first-release-date", "")[:4] if rg.get("first-release-date") else "",
                "score": rg.get("score", 0),
            }
            for rg in data.get("release-groups", [])
        ]

    async def get_artist(self, mbid: str) -> Optional[dict]:
        data = await self._get(f"/artist/{mbid}", {"inc": "release-groups"})
        if not data:
            return None
        albums = [
            {
                "mbid": rg.get("id"),
                "title": rg.get("title", ""),
                "type": rg.get("primary-type", ""),
                "year": rg.get("first-release-date", "")[:4] if rg.get("first-release-date") else "",
            }
            for rg in data.get("release-groups", [])
        ]
        return {
            "mbid": data.get("id"),
            "name": data.get("name", ""),
            "country": data.get("country", ""),
            "type": data.get("type", ""),
            "life_span": data.get("life-span", {}),
            "albums": albums,
        }

    async def get_album_art(self, release_group_mbid: str) -> Optional[str]:
        """Get cover art URL from Cover Art Archive."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{COVER_BASE}/release-group/{release_group_mbid}")
                if resp.status_code == 200:
                    data = resp.json()
                    images = data.get("images", [])
                    if images:
                        return images[0].get("thumbnails", {}).get("500", images[0].get("image"))
        except Exception:
            pass
        return None

    async def close(self):
        if self._client:
            await self._client.aclose()


# Singleton
musicbrainz = MusicBrainzService()
