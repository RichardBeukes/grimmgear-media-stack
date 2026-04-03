"""
GrimmGear — qBittorrent Client
Single download client interface. One connection, all media types share it.
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("grimmgear.qbit")


class QBitClient:
    """Manages all communication with qBittorrent WebUI API."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False

    @property
    def base_url(self) -> str:
        return settings.download.qbit_url.rstrip("/")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
            self._authenticated = False
        if not self._authenticated:
            await self._login()
        return self._client

    async def _login(self):
        try:
            resp = await self._client.post("/api/v2/auth/login", data={
                "username": settings.download.qbit_username,
                "password": settings.download.qbit_password,
            })
            if resp.status_code == 200 and resp.text == "Ok.":
                self._authenticated = True
                logger.info("qBittorrent authenticated")
            else:
                logger.error(f"qBittorrent auth failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"qBittorrent connection failed: {e}")

    async def is_connected(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/api/v2/app/version")
            return resp.status_code == 200
        except Exception:
            return False

    async def get_version(self) -> str:
        try:
            client = await self._get_client()
            resp = await client.get("/api/v2/app/version")
            return resp.text if resp.status_code == 200 else "unknown"
        except Exception:
            return "offline"

    async def add_torrent(self, url: str, category: str = "", save_path: str = "") -> bool:
        """Add a torrent by magnet link or .torrent URL."""
        client = await self._get_client()
        data = {"urls": url}
        if category:
            data["category"] = category
        if save_path:
            data["savepath"] = save_path
        try:
            resp = await client.post("/api/v2/torrents/add", data=data)
            success = resp.status_code == 200 and resp.text == "Ok."
            if success:
                logger.info(f"Torrent added: {url[:80]}... category={category}")
            else:
                logger.warning(f"Torrent add failed: {resp.status_code} {resp.text}")
            return success
        except Exception as e:
            logger.error(f"Failed to add torrent: {e}")
            return False

    async def get_torrents(self, category: str = "", filter_status: str = "") -> list[dict]:
        """Get all torrents, optionally filtered by category or status."""
        client = await self._get_client()
        params = {}
        if category:
            params["category"] = category
        if filter_status:
            params["filter"] = filter_status
        try:
            resp = await client.get("/api/v2/torrents/info", params=params)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    async def get_transfer_info(self) -> dict:
        """Get global download/upload speed."""
        client = await self._get_client()
        try:
            resp = await client.get("/api/v2/transfer/info")
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}

    async def delete_torrent(self, hash: str, delete_files: bool = False) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post("/api/v2/torrents/delete", data={
                "hashes": hash,
                "deleteFiles": str(delete_files).lower(),
            })
            return resp.status_code == 200
        except Exception:
            return False

    async def pause_torrent(self, hash: str) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post("/api/v2/torrents/pause", data={"hashes": hash})
            return resp.status_code == 200
        except Exception:
            return False

    async def resume_torrent(self, hash: str) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post("/api/v2/torrents/resume", data={"hashes": hash})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()


# Singleton — one client for the whole system
qbit = QBitClient()
