"""
GrimmGear Mediarr — Transcode Service
On-the-fly MKV to MP4 streaming + batch queue for permanent conversions.
Uses FFmpeg. Replaces Tdarr.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

logger = logging.getLogger("grimmgear.transcode")

# Find FFmpeg
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"


@dataclass
class TranscodeJob:
    id: int
    source: str
    target: str
    status: str = "queued"  # queued, running, done, failed
    progress: float = 0.0
    started: float = 0.0
    finished: float = 0.0
    error: str = ""
    duration: float = 0.0
    speed: str = ""


class Transcoder:
    """Manages FFmpeg transcoding: on-the-fly streaming and batch queue."""

    def __init__(self):
        self._queue: list[TranscodeJob] = []
        self._next_id = 1
        self._running = False
        self._current: Optional[TranscodeJob] = None
        self._stats = {"completed": 0, "failed": 0, "bytes_saved": 0}

    def probe(self, file_path: str) -> dict:
        """Get media file info via FFprobe."""
        try:
            result = subprocess.run(
                [FFPROBE_PATH, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", file_path],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt = data.get("format", {})
                streams = data.get("streams", [])
                video = next((s for s in streams if s.get("codec_type") == "video"), {})
                audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
                subs = [s for s in streams if s.get("codec_type") == "subtitle"]
                return {
                    "ok": True,
                    "duration": float(fmt.get("duration", 0)),
                    "size": int(fmt.get("size", 0)),
                    "bitrate": int(fmt.get("bit_rate", 0)),
                    "format": fmt.get("format_name", ""),
                    "video_codec": video.get("codec_name", ""),
                    "video_width": int(video.get("width", 0)),
                    "video_height": int(video.get("height", 0)),
                    "audio_codec": audio.get("codec_name", ""),
                    "audio_channels": int(audio.get("channels", 0)),
                    "subtitles": len(subs),
                    "subtitle_langs": [s.get("tags", {}).get("language", "und") for s in subs],
                    "needs_transcode": not self._browser_compatible(video.get("codec_name", ""), audio.get("codec_name", "")),
                }
            return {"ok": False, "error": "FFprobe failed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _browser_compatible(self, video_codec: str, audio_codec: str) -> bool:
        """Check if codecs are natively playable in browsers."""
        browser_video = {"h264", "vp8", "vp9", "av1"}
        browser_audio = {"aac", "mp3", "opus", "vorbis", "flac"}
        return video_codec.lower() in browser_video and audio_codec.lower() in browser_audio

    def _build_stream_args(self, file_path: str) -> list[str]:
        """Build FFmpeg args for on-the-fly streaming."""
        args = [
            FFMPEG_PATH, "-i", file_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "frag_keyframe+empty_moov+faststart",
            "-f", "mp4",
            "-y", "pipe:1",
        ]

        probe = self.probe(file_path)
        vc = probe.get("video_codec", "") if probe.get("ok") else ""

        # If video codec is not browser-compatible, transcode to h264
        if vc and vc not in ("h264",):
            idx = args.index("copy")
            args[idx] = "libx264"
            # Insert preset and crf after the codec
            insert_pos = idx + 1
            for kv in ["-preset", "ultrafast", "-crf", "23"]:
                args.insert(insert_pos, kv)
                insert_pos += 1

        return args

    async def stream_transcode(self, file_path: str) -> AsyncIterator[bytes]:
        """On-the-fly transcode and stream as fragmented MP4."""
        args = self._build_stream_args(file_path)
        logger.info(f"Stream transcode: {Path(file_path).name}")

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        try:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    def add_to_queue(self, source: str, target: str = "") -> TranscodeJob:
        """Add a file to the batch transcode queue."""
        if not target:
            p = Path(source)
            target = str(p.with_suffix(".mp4"))

        job = TranscodeJob(id=self._next_id, source=source, target=target)
        probe = self.probe(source)
        if probe.get("ok"):
            job.duration = probe.get("duration", 0)

        self._next_id += 1
        self._queue.append(job)
        logger.info(f"Queued transcode: {Path(source).name}")
        return job

    async def process_queue(self):
        """Process the batch transcode queue."""
        if self._running:
            return
        self._running = True

        try:
            while self._queue:
                job = next((j for j in self._queue if j.status == "queued"), None)
                if not job:
                    break

                self._current = job
                job.status = "running"
                job.started = time.time()

                try:
                    await self._transcode_file(job)
                    job.status = "done"
                    job.progress = 1.0
                    job.finished = time.time()
                    self._stats["completed"] += 1

                    src_size = Path(job.source).stat().st_size if Path(job.source).exists() else 0
                    tgt_size = Path(job.target).stat().st_size if Path(job.target).exists() else 0
                    if src_size > tgt_size > 0:
                        self._stats["bytes_saved"] += (src_size - tgt_size)

                    logger.info(f"Transcode complete: {Path(job.source).name}")
                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                    job.finished = time.time()
                    self._stats["failed"] += 1
                    logger.error(f"Transcode failed: {Path(job.source).name}: {e}")

                self._current = None
        finally:
            self._running = False

    async def _transcode_file(self, job: TranscodeJob):
        """Run FFmpeg to transcode a single file."""
        args = [
            FFMPEG_PATH, "-i", job.source,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-c:s", "mov_text",
            "-movflags", "+faststart",
            "-y", job.target,
            "-progress", "pipe:1",
        ]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded.startswith("out_time_ms="):
                try:
                    us = int(decoded.split("=")[1])
                    if job.duration > 0:
                        job.progress = min((us / 1_000_000) / job.duration, 1.0)
                except ValueError:
                    pass
            elif decoded.startswith("speed="):
                job.speed = decoded.split("=")[1].strip()

        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg exited with code {proc.returncode}")

    def cancel_job(self, job_id: int) -> bool:
        """Cancel a queued job."""
        for job in self._queue:
            if job.id == job_id and job.status == "queued":
                self._queue.remove(job)
                return True
        return False

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "queue_length": len([j for j in self._queue if j.status == "queued"]),
            "current": {
                "id": self._current.id,
                "source": Path(self._current.source).name,
                "progress": self._current.progress,
                "speed": self._current.speed,
            } if self._current else None,
            "stats": self._stats,
            "ffmpeg": FFMPEG_PATH,
        }

    @property
    def queue(self) -> list[dict]:
        return [
            {
                "id": j.id, "source": Path(j.source).name,
                "target": Path(j.target).name, "status": j.status,
                "progress": j.progress, "speed": j.speed, "error": j.error,
            }
            for j in self._queue
        ]


# Singleton
transcoder = Transcoder()
