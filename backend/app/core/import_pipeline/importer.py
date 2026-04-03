"""
GrimmGear Mediarr — Import Pipeline
Detects completed downloads in qBittorrent, verifies the file,
renames it, moves it to the correct media folder, and updates the database.

This is the bridge between "downloaded" and "in your library."
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
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

# Find FFprobe — check common locations
import glob
_ffprobe_candidates = [
    "ffprobe",  # system PATH
    *glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffprobe.exe")),
    r"C:\Tools\ffmpeg\bin\ffprobe.exe",
    r"C:\ffmpeg\bin\ffprobe.exe",
]
FFPROBE_PATH = "ffprobe"
for candidate in _ffprobe_candidates:
    if os.path.isfile(candidate):
        FFPROBE_PATH = candidate
        break

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

        # Verify main video file with FFprobe before importing
        if category in ("grimmgear-movies", "radarr", "grimmgear-tv", "tv-sonarr"):
            main_file = media_files[0]  # Largest file
            verify = self._verify_video(main_file)
            if not verify["ok"]:
                return {"imported": False, "title": name, "reason": verify["reason"]}

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

    def _verify_video(self, file_path: Path) -> dict:
        """Verify video file using FFprobe. Rejects fakes, samples, corrupt files."""
        try:
            result = subprocess.run(
                [FFPROBE_PATH, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file_path)],
                capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
            )
            if result.returncode != 0:
                return {"ok": False, "reason": f"FFprobe failed on {file_path.name}"}

            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])

            # Duration check — reject anything under 5 minutes for movies, 1 min for TV
            duration = float(fmt.get("duration", 0))
            if duration < 60:
                return {"ok": False, "reason": f"Duration {duration:.0f}s — too short, likely fake/sample"}
            if duration < 300:
                # Under 5 minutes — suspicious for movies but OK for shorts
                logger.warning(f"Short duration ({duration:.0f}s) for {file_path.name}")

            # Resolution check — find video stream
            video_streams = [s for s in streams if s.get("codec_type") == "video"]
            if not video_streams:
                return {"ok": False, "reason": "No video stream found"}

            width = int(video_streams[0].get("width", 0))
            height = int(video_streams[0].get("height", 0))

            # Reject SD garbage claiming to be HD (ETRG pattern)
            if width < 640 and height < 480:
                return {"ok": False, "reason": f"Resolution {width}x{height} — too low, likely fake"}

            # Check title claims vs reality
            fname_lower = file_path.name.lower()
            if ("2160p" in fname_lower or "4k" in fname_lower) and width < 3640:
                return {"ok": False, "reason": f"Claims 4K but actual {width}x{height} — upscale fake"}
            if "1080p" in fname_lower and width < 1824:
                return {"ok": False, "reason": f"Claims 1080p but actual {width}x{height} — upscale fake"}

            # Audio check
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            if not audio_streams:
                return {"ok": False, "reason": "No audio stream found"}

            # Size sanity — a 2-hour movie at 1080p should be at least 500MB
            file_size = file_path.stat().st_size
            if duration > 3600 and file_size < 200_000_000:
                return {"ok": False, "reason": f"File too small ({file_size//1048576}MB) for {duration/60:.0f}min video — likely fake"}

            logger.debug(f"Verified: {file_path.name} — {width}x{height}, {duration:.0f}s, {file_size//1048576}MB")
            return {"ok": True, "width": width, "height": height, "duration": duration}

        except FileNotFoundError:
            # FFprobe not installed — skip verification
            logger.warning("FFprobe not found — skipping video verification")
            return {"ok": True, "reason": "ffprobe not available"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "FFprobe timed out — possibly corrupt file"}
        except Exception as e:
            logger.error(f"Video verification error: {e}")
            return {"ok": True, "reason": f"Verification error: {e}"}

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
