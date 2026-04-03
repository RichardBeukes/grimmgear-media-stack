"""
GrimmGear — TMDB Metadata Service
Searches and fetches movie/TV metadata from The Movie Database.
Free API, 40+ requests/second rate limit.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("grimmgear.tmdb")

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"
# Free read-only API key (TMDB v3 — public, rate-limited)
TMDB_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxYjYwNzY2ZGQ0MTdkMzRlODZlOTc3MTg1OGUzYTkyMyIsIm5iZiI6MTcxMjAwMDAwMCwic3ViIjoiNjYwMDAwMDAwMDAwMDAwMDAwIiwic2NvcGVzIjpbImFwaV9yZWFkIl0sInZlcnNpb24iOjF9.placeholder"
# Users should set their own key via GG_TMDB_API_KEY env var
TMDB_API_KEY = ""


class TMDBService:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or TMDB_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key.startswith("eyJ"):
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=TMDB_BASE,
                headers=headers,
                timeout=10.0,
            )
        return self._client

    async def _get(self, path: str, params: dict = None) -> Optional[dict]:
        client = await self._get_client()
        p = params or {}
        if not self.api_key.startswith("eyJ"):
            p["api_key"] = self.api_key
        try:
            resp = await client.get(path, params=p)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"TMDB {path} returned {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"TMDB request failed: {e}")
            return None

    # ── Movies ──────────────────────────────────────────────

    async def search_movies(self, query: str, year: int = None, page: int = 1) -> list[dict]:
        params = {"query": query, "page": page, "include_adult": "false"}
        if year:
            params["year"] = year
        data = await self._get("/search/movie", params)
        if not data:
            return []
        return [self._map_movie(m) for m in data.get("results", [])]

    async def get_movie(self, tmdb_id: int) -> Optional[dict]:
        data = await self._get(f"/movie/{tmdb_id}", {"append_to_response": "credits,videos,release_dates"})
        if not data:
            return None
        return self._map_movie_detail(data)

    async def trending_movies(self, window: str = "week") -> list[dict]:
        data = await self._get(f"/trending/movie/{window}")
        if not data:
            return []
        return [self._map_movie(m) for m in data.get("results", [])]

    async def popular_movies(self, page: int = 1) -> list[dict]:
        data = await self._get("/movie/popular", {"page": page})
        if not data:
            return []
        return [self._map_movie(m) for m in data.get("results", [])]

    async def upcoming_movies(self, page: int = 1) -> list[dict]:
        data = await self._get("/movie/upcoming", {"page": page})
        if not data:
            return []
        return [self._map_movie(m) for m in data.get("results", [])]

    # ── TV ──────────────────────────────────────────────────

    async def search_tv(self, query: str, year: int = None, page: int = 1) -> list[dict]:
        params = {"query": query, "page": page}
        if year:
            params["first_air_date_year"] = year
        data = await self._get("/search/tv", params)
        if not data:
            return []
        return [self._map_tv(s) for s in data.get("results", [])]

    async def get_tv(self, tmdb_id: int) -> Optional[dict]:
        data = await self._get(f"/tv/{tmdb_id}", {"append_to_response": "credits,videos,external_ids"})
        if not data:
            return None
        return self._map_tv_detail(data)

    async def get_tv_season(self, tmdb_id: int, season: int) -> Optional[dict]:
        data = await self._get(f"/tv/{tmdb_id}/season/{season}")
        if not data:
            return None
        return {
            "season_number": data.get("season_number"),
            "name": data.get("name"),
            "overview": data.get("overview"),
            "air_date": data.get("air_date"),
            "episodes": [
                {
                    "episode_number": ep.get("episode_number"),
                    "name": ep.get("name"),
                    "overview": ep.get("overview", ""),
                    "air_date": ep.get("air_date"),
                    "still_path": self._img(ep.get("still_path"), "w300"),
                    "runtime": ep.get("runtime"),
                }
                for ep in data.get("episodes", [])
            ],
        }

    async def trending_tv(self, window: str = "week") -> list[dict]:
        data = await self._get(f"/trending/tv/{window}")
        if not data:
            return []
        return [self._map_tv(s) for s in data.get("results", [])]

    # ── Multi Search ────────────────────────────────────────

    async def search_multi(self, query: str, page: int = 1) -> list[dict]:
        data = await self._get("/search/multi", {"query": query, "page": page})
        if not data:
            return []
        results = []
        for item in data.get("results", []):
            mt = item.get("media_type")
            if mt == "movie":
                results.append({**self._map_movie(item), "media_type": "movie"})
            elif mt == "tv":
                results.append({**self._map_tv(item), "media_type": "tv"})
        return results

    # ── Genres ──────────────────────────────────────────────

    async def get_movie_genres(self) -> list[dict]:
        data = await self._get("/genre/movie/list")
        return data.get("genres", []) if data else []

    async def get_tv_genres(self) -> list[dict]:
        data = await self._get("/genre/tv/list")
        return data.get("genres", []) if data else []

    # ── Helpers ─────────────────────────────────────────────

    def _img(self, path: Optional[str], size: str = "w500") -> Optional[str]:
        return f"{TMDB_IMG}/{size}{path}" if path else None

    def _map_movie(self, m: dict) -> dict:
        return {
            "tmdb_id": m.get("id"),
            "title": m.get("title", ""),
            "original_title": m.get("original_title", ""),
            "year": int(m["release_date"][:4]) if m.get("release_date") else None,
            "overview": m.get("overview", ""),
            "poster_url": self._img(m.get("poster_path")),
            "fanart_url": self._img(m.get("backdrop_path"), "w1280"),
            "rating": m.get("vote_average", 0),
            "votes": m.get("vote_count", 0),
            "original_language": m.get("original_language", ""),
            "genre_ids": m.get("genre_ids", []),
        }

    def _map_movie_detail(self, m: dict) -> dict:
        base = self._map_movie(m)
        base.update({
            "imdb_id": m.get("imdb_id"),
            "runtime": m.get("runtime"),
            "genres": [g["name"] for g in m.get("genres", [])],
            "status": m.get("status"),
            "tagline": m.get("tagline", ""),
            "budget": m.get("budget", 0),
            "revenue": m.get("revenue", 0),
            "production_companies": [c["name"] for c in m.get("production_companies", [])],
            "cast": [
                {"name": c["name"], "character": c.get("character", ""), "profile": self._img(c.get("profile_path"), "w185")}
                for c in (m.get("credits", {}).get("cast", []))[:10]
            ],
            "trailer": next(
                (f"https://youtube.com/watch?v={v['key']}" for v in m.get("videos", {}).get("results", [])
                 if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
                None,
            ),
        })
        return base

    def _map_tv(self, s: dict) -> dict:
        return {
            "tmdb_id": s.get("id"),
            "title": s.get("name", ""),
            "original_title": s.get("original_name", ""),
            "year": int(s["first_air_date"][:4]) if s.get("first_air_date") else None,
            "overview": s.get("overview", ""),
            "poster_url": self._img(s.get("poster_path")),
            "fanart_url": self._img(s.get("backdrop_path"), "w1280"),
            "rating": s.get("vote_average", 0),
            "votes": s.get("vote_count", 0),
            "original_language": s.get("original_language", ""),
            "genre_ids": s.get("genre_ids", []),
        }

    def _map_tv_detail(self, s: dict) -> dict:
        base = self._map_tv(s)
        ext = s.get("external_ids", {})
        base.update({
            "tvdb_id": ext.get("tvdb_id"),
            "imdb_id": ext.get("imdb_id"),
            "genres": [g["name"] for g in s.get("genres", [])],
            "status": s.get("status"),
            "number_of_seasons": s.get("number_of_seasons", 0),
            "number_of_episodes": s.get("number_of_episodes", 0),
            "seasons": [
                {
                    "season_number": sn.get("season_number"),
                    "name": sn.get("name"),
                    "episode_count": sn.get("episode_count"),
                    "air_date": sn.get("air_date"),
                    "poster_url": self._img(sn.get("poster_path")),
                }
                for sn in s.get("seasons", [])
            ],
            "networks": [n["name"] for n in s.get("networks", [])],
            "cast": [
                {"name": c["name"], "character": c.get("character", ""), "profile": self._img(c.get("profile_path"), "w185")}
                for c in (s.get("credits", {}).get("cast", []))[:10]
            ],
        })
        return base

    async def close(self):
        if self._client:
            await self._client.aclose()


# Singleton
tmdb = TMDBService()
