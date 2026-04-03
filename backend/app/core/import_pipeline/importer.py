"""
GrimmGear Mediarr — Import Pipeline
Detects completed downloads in qBittorrent, verifies the file,
renames it, moves it to the correct media folder, and updates the database.

This is the bridge between "downloaded" and "in your library."
"""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.download.qbit_client import qbit

logger = logging.getLogger("grimmgear.import")

# Category → media folder mapping
CATEGORY_FOLDERS = {
    "grimmgear-movies": "Movies",
    "grimmgear-tv": "TVshows",
    "grimmgear-music": "Music",
    "grimmgear-books": "Books",
    "grimmgear-comics": "Comics",
    # Also handle arr-style categories from existing setup
    "radarr": "Movies",
    "tv-sonarr": "TVshows",
    "lidarr": "Music",
    "readarr": "Books",
}

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".ts", ".m2ts", ".webm"}
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".wma", ".aac"}
BOOK_EXTENSIONS = {".epub", ".mobi", ".azw3", ".pdf", ".cbz", ".cbr"}


class ImportPipeline:
    """Scans qBittorrent for completed downloads and imports them."""

    def __init__(self):
        self._running = False
        self._import_count = 0
        self._reject_count = 0

    async def scan_and_import(self) -> dict:
        """Main scan loop — check qBit for completed torrents and import them."""
        if self._running:
            return {"status": "already running"}

        self._running = True
        imported = []
        rejected = []

        try:
            torrents = await qbit.get_torrents()
            completed = [
                t for t in torrents
                if t.get("progress", 0) >= 1.0
                and t.get("category", "") in CATEGORY_FOLDERS
                and t.get("state", "") in ("uploading", "stalledUP", "stoppedUP", "pausedUP", "forcedUP", "queuedUP")
            ]

            logger.info(f"Import scan: {len(completed)} completed torrents with GrimmGear categories")

            for torrent in completed:
                result = await self._import_torrent(torrent)
                if result["imported"]:
                    imported.append(result)
                    self._import_count += 1
                else:
                    rejected.append(result)
                    self._reject_count += 1

        except Exception as e:
            logger.error(f"Import scan failed: {e}")
        finally:
            self._running = False

        return {
            "scanned": len(completed) if 'completed' in dir() else 0,
            "imported": len(imported),
            "rejected": len(rejected),
            "details": {"imported": imported, "rejected": rejected},
            "totals": {"imported": self._import_count, "rejected": self._reject_count},
        }

    async def _import_torrent(self, torrent: dict) -> dict:
        """Import a single completed torrent."""
        name = torrent.get("name", "")
        category = torrent.get("category", "")
        content_path = torrent.get("content_path", "")
        save_path = torrent.get("save_path", "")
        hash_id = torrent.get("hash", "")

        # Determine target media folder
        subfolder = CATEGORY_FOLDERS.get(category, "")
        if not subfolder:
            return {"imported": False, "title": name, "reason": f"Unknown category: {category}"}

        target_root = settings.paths.media_root / subfolder

        # Find the actual media file(s)
        source_path = Path(content_path) if content_path else Path(save_path) / name

        if not source_path.exists():
            return {"imported": False, "title": name, "reason": f"Source path not found: {source_path}"}

        # Find media files
        media_files = self._find_media_files(source_path, category)

        if not media_files:
            return {"imported": False, "title": name, "reason": "No media files found in download"}

        results = []
        for src_file in media_files:
            # Parse title and build target path
            parsed = self._parse_filename(src_file.name, category)
            target_dir = target_root / parsed["folder_name"]
            target_file = target_dir / parsed["file_name"]

            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)

            # Copy or hardlink
            try:
                if self._same_drive(src_file, target_dir):
                    # Hardlink (instant, no extra disk space)
                    if not target_file.exists():
                        os.link(str(src_file), str(target_file))
                        logger.info(f"Hardlinked: {src_file.name} -> {target_file}")
                else:
                    # Copy (different drives)
                    if not target_file.exists():
                        shutil.copy2(str(src_file), str(target_file))
                        logger.info(f"Copied: {src_file.name} -> {target_file}")

                results.append({"file": src_file.name, "target": str(target_file), "success": True})
            except Exception as e:
                logger.error(f"Failed to import {src_file.name}: {e}")
                results.append({"file": src_file.name, "error": str(e), "success": False})

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "imported": success_count > 0,
            "title": name,
            "files": success_count,
            "target": str(target_root),
            "details": results,
        }

    def _find_media_files(self, path: Path, category: str) -> list[Path]:
        """Find all media files in a download path."""
        if category in ("grimmgear-movies", "radarr", "grimmgear-tv", "tv-sonarr"):
            extensions = VIDEO_EXTENSIONS
        elif category in ("grimmgear-music", "lidarr"):
            extensions = AUDIO_EXTENSIONS
        elif category in ("grimmgear-books", "readarr", "grimmgear-comics"):
            extensions = BOOK_EXTENSIONS
        else:
            extensions = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | BOOK_EXTENSIONS

        files = []
        if path.is_file():
            if path.suffix.lower() in extensions:
                files.append(path)
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file() and f.suffix.lower() in extensions and not f.name.startswith("."):
                    # Skip samples
                    if "sample" in f.name.lower() and f.stat().st_size < 100_000_000:
                        continue
                    files.append(f)

        # Sort by size descending (main file first)
        files.sort(key=lambda f: f.stat().st_size, reverse=True)
        return files

    def _parse_filename(self, filename: str, category: str) -> dict:
        """Parse a media filename into folder name and clean file name."""
        name = Path(filename).stem
        ext = Path(filename).suffix

        # Strip website prefixes (our rr-stack patch)
        name = re.sub(r'^(?:www\.)?[-a-z0-9]{1,256}\.(?:[a-z]{2,6})\s*[-–]\s*', '', name, flags=re.IGNORECASE)

        # Extract title and year for movies
        movie_match = re.match(r'^(.+?)[.\s_-]+(\d{4})', name)
        if movie_match and category in ("grimmgear-movies", "radarr"):
            title = movie_match.group(1).replace(".", " ").replace("_", " ").strip()
            year = movie_match.group(2)
            folder_name = f"{title} ({year})"
            return {"folder_name": folder_name, "file_name": filename}

        # For TV: extract show name
        tv_match = re.match(r'^(.+?)[.\s_-]+[Ss](\d+)[Ee](\d+)', name)
        if tv_match and category in ("grimmgear-tv", "tv-sonarr"):
            show = tv_match.group(1).replace(".", " ").replace("_", " ").strip()
            season = int(tv_match.group(2))
            folder_name = os.path.join(show, f"Season {season:02d}")
            return {"folder_name": folder_name, "file_name": filename}

        # Fallback: use filename as-is
        clean = name.replace(".", " ").replace("_", " ").strip()
        return {"folder_name": clean, "file_name": filename}

    def _same_drive(self, path1: Path, path2: Path) -> bool:
        """Check if two paths are on the same drive (for hardlink support)."""
        try:
            return os.path.splitdrive(str(path1))[0].upper() == os.path.splitdrive(str(path2))[0].upper()
        except Exception:
            return False

    @property
    def stats(self) -> dict:
        return {"imported": self._import_count, "rejected": self._reject_count, "running": self._running}


# Singleton
import_pipeline = ImportPipeline()
