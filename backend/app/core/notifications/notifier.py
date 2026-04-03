"""
GrimmGear Mediarr — Notification Service
Discord, Telegram, and generic webhook notifications for media events.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("grimmgear.notify")


@dataclass
class NotificationChannel:
    name: str
    type: str  # discord, telegram, webhook
    enabled: bool = True
    # Discord
    discord_webhook_url: str = ""
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Generic webhook
    webhook_url: str = ""
    webhook_method: str = "POST"


class Notifier:
    """Sends notifications to configured channels."""

    def __init__(self):
        self._channels: list[NotificationChannel] = []
        self._history: list[dict] = []

    def add_channel(self, channel: NotificationChannel):
        self._channels.append(channel)

    def remove_channel(self, name: str) -> bool:
        for ch in self._channels:
            if ch.name == name:
                self._channels.remove(ch)
                return True
        return False

    def get_channels(self) -> list[dict]:
        return [
            {"name": c.name, "type": c.type, "enabled": c.enabled}
            for c in self._channels
        ]

    async def notify(self, event: str, title: str, message: str, **kwargs):
        """Send notification to all enabled channels."""
        for ch in self._channels:
            if not ch.enabled:
                continue
            try:
                if ch.type == "discord":
                    await self._send_discord(ch, event, title, message, **kwargs)
                elif ch.type == "telegram":
                    await self._send_telegram(ch, event, title, message, **kwargs)
                elif ch.type == "webhook":
                    await self._send_webhook(ch, event, title, message, **kwargs)
            except Exception as e:
                logger.error(f"Notification failed ({ch.name}): {e}")

        self._history.append({"event": event, "title": title, "message": message})
        if len(self._history) > 100:
            self._history = self._history[-100:]

    async def _send_discord(self, ch: NotificationChannel, event: str, title: str, message: str, **kwargs):
        """Send Discord webhook embed."""
        color_map = {
            "download.complete": 0x27C24C,  # green
            "import.complete": 0x35C5F4,    # cyan
            "request.new": 0xFFC230,         # yellow
            "request.approved": 0x27C24C,    # green
            "request.denied": 0xF05050,      # red
            "transcode.complete": 0x5D9CEC,  # blue
        }
        embed = {
            "title": title,
            "description": message,
            "color": color_map.get(event, 0x5D9CEC),
            "footer": {"text": "GrimmGear Mediarr"},
        }
        if kwargs.get("poster_url"):
            embed["thumbnail"] = {"url": kwargs["poster_url"]}

        payload = {"embeds": [embed]}
        if kwargs.get("username"):
            payload["username"] = kwargs["username"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(ch.discord_webhook_url, json=payload)
            if resp.status_code not in (200, 204):
                logger.warning(f"Discord webhook returned {resp.status_code}")

    async def _send_telegram(self, ch: NotificationChannel, event: str, title: str, message: str, **kwargs):
        """Send Telegram bot message."""
        emoji_map = {
            "download.complete": "\U0001F4E5",
            "import.complete": "\U00002705",
            "request.new": "\U0001F4DD",
            "request.approved": "\U0001F44D",
            "request.denied": "\U0000274C",
            "transcode.complete": "\U0001F3AC",
        }
        emoji = emoji_map.get(event, "\U0001F4E2")
        text = f"{emoji} *{title}*\n{message}"

        url = f"https://api.telegram.org/bot{ch.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": ch.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Telegram returned {resp.status_code}")

    async def _send_webhook(self, ch: NotificationChannel, event: str, title: str, message: str, **kwargs):
        """Send generic webhook."""
        payload = {
            "event": event,
            "title": title,
            "message": message,
            "source": "grimmgear-mediarr",
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            if ch.webhook_method.upper() == "GET":
                await client.get(ch.webhook_url, params=payload)
            else:
                await client.post(ch.webhook_url, json=payload)

    async def test_channel(self, name: str) -> dict:
        """Test a notification channel."""
        ch = next((c for c in self._channels if c.name == name), None)
        if not ch:
            return {"success": False, "error": "Channel not found"}
        try:
            await self.notify(
                "test",
                "GrimmGear Mediarr Test",
                "If you see this, notifications are working!",
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @property
    def history(self) -> list[dict]:
        return list(reversed(self._history[-20:]))


# Singleton
notifier = Notifier()
