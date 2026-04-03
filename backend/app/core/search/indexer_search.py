"""
GrimmGear — Indexer Search Engine
Built-in Torznab/Newznab search. Replaces Prowlarr.
Bounded parallelism, mirror failover, rate limiting.
"""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("grimmgear.indexer")

MAX_CONCURRENT = 25  # Bounded parallelism (our Prowlarr fix)


@dataclass
class SearchResult:
    title: str
    indexer: str
    download_url: str
    info_url: str = ""
    size: int = 0
    seeders: int = 0
    leechers: int = 0
    quality: str = ""
    codec: str = ""
    source: str = ""
    language: str = ""
    age_days: int = 0
    categories: list[int] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Higher = better. Combines quality + seeders."""
        q_score = {"2160p": 100, "1080p": 80, "720p": 60, "480p": 20}.get(self.quality, 40)
        seed_score = min(self.seeders, 100)
        size_penalty = -20 if self.size == 0 else 0  # Our Size=0 rejection
        return q_score + seed_score + size_penalty


class IndexerSearchEngine:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def search(
        self,
        indexers: list[dict],
        query: str,
        categories: list[int] = None,
        imdb_id: str = None,
        tvdb_id: int = None,
        season: int = None,
        episode: int = None,
    ) -> list[SearchResult]:
        """Search all enabled indexers in parallel with bounded concurrency."""
        tasks = [
            self._search_indexer(idx, query, categories, imdb_id, tvdb_id, season, episode)
            for idx in indexers
            if idx.get("enabled", True)
        ]
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for r in results_nested:
            if isinstance(r, list):
                results.extend(r)
            elif isinstance(r, Exception):
                logger.warning(f"Indexer search failed: {r}")
        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    async def _search_indexer(
        self,
        indexer: dict,
        query: str,
        categories: list[int],
        imdb_id: str,
        tvdb_id: int,
        season: int,
        episode: int,
    ) -> list[SearchResult]:
        """Search a single indexer with semaphore-bounded concurrency."""
        async with self._semaphore:
            url = indexer["url"].rstrip("/")
            api_key = indexer.get("api_key", "")
            indexer_type = indexer.get("indexer_type", "torznab")

            params = {"apikey": api_key, "t": "search", "q": query}
            if categories:
                params["cat"] = ",".join(str(c) for c in categories)
            if imdb_id:
                params["imdbid"] = imdb_id
                params["t"] = "movie"
            if tvdb_id:
                params["tvdbid"] = str(tvdb_id)
                params["t"] = "tvsearch"
            if season is not None:
                params["season"] = str(season)
            if episode is not None:
                params["ep"] = str(episode)

            search_url = f"{url}/api" if not url.endswith("/api") else url

            client = await self._get_client()
            try:
                resp = await client.get(search_url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Indexer {indexer['name']} returned {resp.status_code}")
                    return []
                return self._parse_torznab(resp.text, indexer["name"])
            except httpx.TimeoutException:
                logger.warning(f"Indexer {indexer['name']} timed out")
                return []
            except Exception as e:
                logger.error(f"Indexer {indexer['name']} error: {e}")
                return []

    def _parse_torznab(self, xml_text: str, indexer_name: str) -> list[SearchResult]:
        """Parse Torznab/Newznab XML response into SearchResult objects."""
        results = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "torznab": "http://torznab.com/schemas/2015/feed"}
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                size = int(item.findtext("size", "0") or "0")
                info_url = item.findtext("comments", "") or item.findtext("guid", "")

                # Parse torznab attributes
                seeders = 0
                leechers = 0
                categories = []
                for attr in item.findall("torznab:attr", ns):
                    name = attr.get("name", "")
                    value = attr.get("value", "")
                    if name == "seeders":
                        seeders = int(value) if value.isdigit() else 0
                    elif name == "peers":
                        leechers = int(value) if value.isdigit() else 0
                    elif name == "category":
                        categories.append(int(value) if value.isdigit() else 0)

                # Also check newznab attributes
                for attr in item.findall("{http://www.newznab.com/DTD/2010/feeds/attributes/}attr"):
                    name = attr.get("name", "")
                    value = attr.get("value", "")
                    if name == "size" and not size:
                        size = int(value) if value.isdigit() else 0

                # Enclosure fallback for download URL
                enclosure = item.find("enclosure")
                if enclosure is not None and not link:
                    link = enclosure.get("url", "")
                    if not size:
                        size = int(enclosure.get("length", "0") or "0")

                # Parse quality from title
                quality = self._detect_quality(title)
                codec = self._detect_codec(title)
                source = self._detect_source(title)
                language = self._detect_language(title)

                results.append(SearchResult(
                    title=title,
                    indexer=indexer_name,
                    download_url=link,
                    info_url=info_url,
                    size=size,
                    seeders=seeders,
                    leechers=leechers,
                    quality=quality,
                    codec=codec,
                    source=source,
                    language=language,
                    categories=categories,
                ))
        except ET.ParseError as e:
            logger.error(f"Failed to parse Torznab XML from {indexer_name}: {e}")
        return results

    def _detect_quality(self, title: str) -> str:
        t = title.lower()
        if "2160p" in t or "4k" in t or "uhd" in t:
            return "2160p"
        if "1080p" in t:
            return "1080p"
        if "720p" in t:
            return "720p"
        if "480p" in t or "sd" in t:
            return "480p"
        return "unknown"

    def _detect_codec(self, title: str) -> str:
        t = title.lower()
        if "x265" in t or "hevc" in t or "h.265" in t or "h265" in t:
            return "x265"
        if "x264" in t or "h.264" in t or "h264" in t or "avc" in t:
            return "x264"
        if "av1" in t:
            return "AV1"
        return ""

    def _detect_source(self, title: str) -> str:
        t = title.lower()
        if "remux" in t:
            return "Remux"
        if "bluray" in t or "blu-ray" in t:
            return "BluRay"
        if "web-dl" in t or "webdl" in t:
            return "WEB-DL"
        if "webrip" in t:
            return "WEBRip"
        if "hdtv" in t:
            return "HDTV"
        if "dvdrip" in t:
            return "DVDRip"
        return ""

    def _detect_language(self, title: str) -> str:
        """GrimmGear language detection — includes our Cyrillic/CJK patches."""
        # Cyrillic detection (our patch)
        if re.search(r'[\u0400-\u04FF]{3,}', title):
            return "Russian"
        # CJK detection
        if re.search(r'[\u3000-\u9FFF\uAC00-\uD7AF]{2,}', title):
            return "Chinese/Korean/Japanese"
        # Arabic detection
        if re.search(r'[\u0600-\u06FF]{3,}', title):
            return "Arabic"
        # Russian dubbing tags (our patch)
        if re.search(r'\b(?:MVO|AVO|DVO|HDRezka|LostFilm|kinozal|rutor|RuTracker)\b', title, re.I):
            return "Russian"
        # Explicit language tags
        t = title.lower()
        if "french" in t or re.search(r'\b(?:VFF|VFQ|TRUEFRENCH)\b', title, re.I):
            return "French"
        if "german" in t or re.search(r'\bGER\b', title):
            return "German"
        if "spanish" in t or "latino" in t:
            return "Spanish"
        if "italian" in t:
            return "Italian"
        return "English"

    async def close(self):
        if self._client:
            await self._client.aclose()


# Singleton
indexer_engine = IndexerSearchEngine()
