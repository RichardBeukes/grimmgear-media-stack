"""
GrimmGear Mediarr — Subtitle Service
Search and download subtitles from OpenSubtitles and other providers.
Replaces Bazarr.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("grimmgear.subtitles")

OPENSUBTITLES_API = "https://api.opensubtitles.com/api/v1"
# Free tier: 5 downloads/day, 20 searches/day
# User agent required
USER_AGENT = "GrimmGear Mediarr v0.1.0"


class SubtitleService:
    """Search and download subtitles from multiple providers."""

    def __init__(self):
        self._api_key = os.environ.get("GG_OPENSUB_API_KEY", "")
        self._token = ""  # OpenSubtitles JWT
        self._download_count = 0

    async def search(self, query: str = "", imdb_id: str = "", tmdb_id: int = 0,
                     season: int = 0, episode: int = 0,
                     languages: str = "en", page: int = 1) -> list[dict]:
        """Search OpenSubtitles for subtitles."""
        if not self._api_key:
            return await self._search_fallback(query, languages)

        params = {"languages": languages, "page": str(page)}
        if imdb_id:
            params["imdb_id"] = imdb_id
        elif tmdb_id:
            params["tmdb_id"] = str(tmdb_id)
        elif query:
            params["query"] = query

        if season:
            params["season_number"] = str(season)
        if episode:
            params["episode_number"] = str(episode)

        headers = {
            "Api-Key": self._api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{OPENSUBTITLES_API}/subtitles", params=params, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"OpenSubtitles search returned {resp.status_code}")
                    return await self._search_fallback(query, languages)

                data = resp.json()
                results = []
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    files = attrs.get("files", [{}])
                    results.append({
                        "id": item.get("id"),
                        "title": attrs.get("release", ""),
                        "language": attrs.get("language", ""),
                        "download_count": attrs.get("download_count", 0),
                        "hearing_impaired": attrs.get("hearing_impaired", False),
                        "fps": attrs.get("fps", 0),
                        "format": "srt",
                        "file_id": files[0].get("file_id") if files else None,
                        "provider": "opensubtitles",
                    })
                return results
        except Exception as e:
            logger.error(f"OpenSubtitles search error: {e}")
            return await self._search_fallback(query, languages)

    async def _search_fallback(self, query: str, languages: str) -> list[dict]:
        """Fallback: search for existing SRT files in the same folder as the media."""
        return [{"id": 0, "title": "No OpenSubtitles API key configured", "language": "",
                 "provider": "none", "note": "Set GG_OPENSUB_API_KEY env var for subtitle search"}]

    async def download(self, file_id: int, target_path: str) -> dict:
        """Download a subtitle file from OpenSubtitles."""
        if not self._api_key:
            return {"ok": False, "error": "No API key configured"}

        headers = {
            "Api-Key": self._api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{OPENSUBTITLES_API}/download",
                    json={"file_id": file_id},
                    headers=headers,
                )
                if resp.status_code != 200:
                    return {"ok": False, "error": f"Download failed: {resp.status_code}"}

                data = resp.json()
                download_link = data.get("link", "")
                if not download_link:
                    return {"ok": False, "error": "No download link in response"}

                # Download the actual file
                sub_resp = await client.get(download_link)
                if sub_resp.status_code == 200:
                    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(target_path, "wb") as f:
                        f.write(sub_resp.content)
                    self._download_count += 1
                    logger.info(f"Subtitle downloaded: {target_path}")
                    return {"ok": True, "path": target_path, "size": len(sub_resp.content)}
                return {"ok": False, "error": f"File download failed: {sub_resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def find_local_subtitles(self, media_path: str) -> list[dict]:
        """Find existing subtitle files next to a media file."""
        p = Path(media_path)
        folder = p.parent
        stem = p.stem
        subs = []
        for ext in (".srt", ".vtt", ".ass", ".ssa", ".sub"):
            for sub_file in folder.glob(f"*{ext}"):
                # Match by same stem or partial match
                if sub_file.stem.startswith(stem) or stem in sub_file.stem:
                    lang = "en"
                    # Try to extract language code from filename
                    lang_match = re.search(r'\.([a-z]{2,3})$', sub_file.stem, re.IGNORECASE)
                    if lang_match:
                        lang = lang_match.group(1)
                    subs.append({
                        "name": sub_file.name,
                        "path": str(sub_file),
                        "language": lang,
                        "format": ext.lstrip("."),
                        "size": sub_file.stat().st_size,
                    })
        return subs

    def srt_to_vtt(self, srt_content: str) -> str:
        """Convert SRT subtitle format to WebVTT for browser playback."""
        vtt = "WEBVTT\n\n"
        # Replace SRT timestamps (comma) with VTT (period)
        content = srt_content.replace(",", ".")
        # Remove BOM
        content = content.lstrip("\ufeff")
        # Remove sequence numbers (lines that are just digits)
        lines = content.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.isdigit():
                continue
            result.append(line)
        vtt += "\n".join(result)
        return vtt

    @property
    def stats(self) -> dict:
        return {
            "api_key_set": bool(self._api_key),
            "downloads_this_session": self._download_count,
        }


# Singleton
subtitle_service = SubtitleService()
