"""
GrimmGear Mediarr — DLNA/UPnP Media Server
SSDP discovery + UPnP Content Directory so smart TVs find your media.
No app install needed — TVs, consoles, and players auto-discover.
"""

import asyncio
import logging
import socket
import struct
import uuid
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from app.core.config import settings

logger = logging.getLogger("grimmgear.dlna")

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SERVER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "grimmgear-mediarr"))

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".webm", ".ts", ".m2ts"}
AUDIO_EXT = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac"}

MIME_MAP = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
    ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".ts": "video/mp2t", ".m2ts": "video/mp2t",
    ".mp3": "audio/mpeg", ".flac": "audio/flac", ".m4a": "audio/mp4",
    ".ogg": "audio/ogg", ".opus": "audio/opus", ".wav": "audio/wav", ".aac": "audio/aac",
}


def _get_local_ip() -> str:
    """Get the machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class DLNAServer:
    """Minimal DLNA/UPnP server for media discovery on LAN."""

    def __init__(self):
        self._running = False
        self._ssdp_task: Optional[asyncio.Task] = None
        self._local_ip = _get_local_ip()
        self._http_port = settings.server.port
        self._friendly_name = settings.dlna.friendly_name
        self._uuid = f"uuid:{SERVER_ID}"

    async def start(self):
        """Start SSDP listener for device discovery."""
        if self._running:
            return
        self._running = True
        self._local_ip = _get_local_ip()
        self._ssdp_task = asyncio.create_task(self._ssdp_loop())
        logger.info(f"DLNA server started: {self._friendly_name} at {self._local_ip}:{self._http_port}")

    async def stop(self):
        self._running = False
        if self._ssdp_task:
            self._ssdp_task.cancel()
            try:
                await self._ssdp_task
            except asyncio.CancelledError:
                pass
        logger.info("DLNA server stopped")

    async def _ssdp_loop(self):
        """Listen for SSDP M-SEARCH requests and respond."""
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(("", SSDP_PORT))
        except OSError as e:
            logger.warning(f"DLNA: Cannot bind SSDP port {SSDP_PORT}: {e}. Another service may be using it.")
            self._running = False
            return

        # Join multicast group
        mreq = struct.pack("4sL", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            logger.warning(f"DLNA: Cannot join multicast: {e}")

        sock.setblocking(False)
        logger.info(f"DLNA: SSDP listening on {SSDP_ADDR}:{SSDP_PORT}")

        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(sock, 4096)
                msg = data.decode("utf-8", errors="replace")
                if "M-SEARCH" in msg and ("ssdp:all" in msg or "MediaServer" in msg or "ContentDirectory" in msg):
                    response = self._build_ssdp_response()
                    await loop.sock_sendto(sock, response.encode(), addr)
                    logger.debug(f"DLNA: Responded to M-SEARCH from {addr}")
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

        sock.close()

    def _build_ssdp_response(self) -> str:
        location = f"http://{self._local_ip}:{self._http_port}/api/dlna/description.xml"
        return (
            "HTTP/1.1 200 OK\r\n"
            f"LOCATION: {location}\r\n"
            "CACHE-CONTROL: max-age=1800\r\n"
            f"SERVER: GrimmGear/1.0 UPnP/1.0 Mediarr/0.1\r\n"
            f"USN: {self._uuid}::urn:schemas-upnp-org:device:MediaServer:1\r\n"
            "ST: urn:schemas-upnp-org:device:MediaServer:1\r\n"
            "EXT:\r\n"
            "\r\n"
        )

    def device_description(self) -> str:
        """Generate UPnP device description XML."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
    <friendlyName>{escape(self._friendly_name)}</friendlyName>
    <manufacturer>GrimmGear Systems</manufacturer>
    <manufacturerURL>https://grimmgear.com</manufacturerURL>
    <modelName>GrimmGear Mediarr</modelName>
    <modelDescription>Unified Media Automation Server</modelDescription>
    <modelNumber>0.1.0</modelNumber>
    <UDN>{self._uuid}</UDN>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>
        <serviceId>urn:upnp-org:serviceId:ContentDirectory</serviceId>
        <SCPDURL>/api/dlna/content-directory.xml</SCPDURL>
        <controlURL>/api/dlna/control</controlURL>
        <eventSubURL>/api/dlna/event</eventSubURL>
      </service>
      <service>
        <serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>
        <serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>
        <SCPDURL>/api/dlna/connection-manager.xml</SCPDURL>
        <controlURL>/api/dlna/connection</controlURL>
        <eventSubURL>/api/dlna/connection-event</eventSubURL>
      </service>
    </serviceList>
  </device>
</root>"""

    def content_directory_scpd(self) -> str:
        """ContentDirectory service description."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <actionList>
    <action><name>Browse</name>
      <argumentList>
        <argument><name>ObjectID</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_ObjectID</relatedStateVariable></argument>
        <argument><name>BrowseFlag</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_BrowseFlag</relatedStateVariable></argument>
        <argument><name>Filter</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_Filter</relatedStateVariable></argument>
        <argument><name>StartingIndex</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_Index</relatedStateVariable></argument>
        <argument><name>RequestedCount</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable></argument>
        <argument><name>SortCriteria</name><direction>in</direction><relatedStateVariable>A_ARG_TYPE_SortCriteria</relatedStateVariable></argument>
        <argument><name>Result</name><direction>out</direction><relatedStateVariable>A_ARG_TYPE_Result</relatedStateVariable></argument>
        <argument><name>NumberReturned</name><direction>out</direction><relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable></argument>
        <argument><name>TotalMatches</name><direction>out</direction><relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable></argument>
        <argument><name>UpdateID</name><direction>out</direction><relatedStateVariable>SystemUpdateID</relatedStateVariable></argument>
      </argumentList>
    </action>
    <action><name>GetSystemUpdateID</name>
      <argumentList>
        <argument><name>Id</name><direction>out</direction><relatedStateVariable>SystemUpdateID</relatedStateVariable></argument>
      </argumentList>
    </action>
  </actionList>
  <serviceStateTable>
    <stateVariable sendEvents="yes"><name>SystemUpdateID</name><dataType>ui4</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_ObjectID</name><dataType>string</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_Result</name><dataType>string</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_BrowseFlag</name><dataType>string</dataType><allowedValueList><allowedValue>BrowseMetadata</allowedValue><allowedValue>BrowseDirectChildren</allowedValue></allowedValueList></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_Filter</name><dataType>string</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_SortCriteria</name><dataType>string</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_Index</name><dataType>ui4</dataType></stateVariable>
    <stateVariable sendEvents="no"><name>A_ARG_TYPE_Count</name><dataType>ui4</dataType></stateVariable>
  </serviceStateTable>
</scpd>"""

    def browse(self, object_id: str = "0", start: int = 0, count: int = 50) -> tuple[str, int, int]:
        """Browse the content directory. Returns (DIDL-Lite XML, returned, total)."""
        media_root = settings.paths.media_root
        base_url = f"http://{self._local_ip}:{self._http_port}"

        items = []

        if object_id == "0":
            # Root: show media type folders
            for idx, (name, folder) in enumerate([
                ("Movies", "Movies"), ("TV Shows", "TVshows"),
                ("Music", "Music"), ("Books", "Books"),
            ], start=1):
                path = media_root / folder
                if path.exists():
                    child_count = sum(1 for _ in path.iterdir() if not _.name.startswith("."))
                    items.append(f'<container id="{idx}" parentID="0" restricted="true" childCount="{child_count}">'
                                 f'<dc:title>{escape(name)}</dc:title>'
                                 f'<upnp:class>object.container.storageFolder</upnp:class></container>')
        else:
            # Browse a specific folder
            folder_map = {"1": "Movies", "2": "TVshows", "3": "Music", "4": "Books"}
            if object_id in folder_map:
                folder = media_root / folder_map[object_id]
                if folder.exists():
                    for item in sorted(folder.iterdir()):
                        if item.name.startswith("."):
                            continue
                        item_id = f"{object_id}_{item.name}"
                        if item.is_dir():
                            child_count = sum(1 for f in item.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXT | AUDIO_EXT)
                            items.append(f'<container id="{escape(item_id)}" parentID="{object_id}" restricted="true" childCount="{child_count}">'
                                         f'<dc:title>{escape(item.name)}</dc:title>'
                                         f'<upnp:class>object.container.storageFolder</upnp:class></container>')
                        elif item.is_file() and item.suffix.lower() in VIDEO_EXT | AUDIO_EXT:
                            mime = MIME_MAP.get(item.suffix.lower(), "video/mp4")
                            import base64
                            rel = str(item.relative_to(media_root))
                            token = base64.urlsafe_b64encode(rel.encode()).decode()
                            stream_url = f"{base_url}/api/stream/{token}"
                            size = item.stat().st_size
                            upnp_class = "object.item.videoItem" if item.suffix.lower() in VIDEO_EXT else "object.item.audioItem.musicTrack"
                            items.append(
                                f'<item id="{escape(item_id)}" parentID="{object_id}" restricted="true">'
                                f'<dc:title>{escape(item.name)}</dc:title>'
                                f'<upnp:class>{upnp_class}</upnp:class>'
                                f'<res protocolInfo="http-get:*:{mime}:*" size="{size}">{escape(stream_url)}</res>'
                                f'</item>'
                            )
            else:
                # Sub-folder browse (object_id = "1_FolderName")
                parts = object_id.split("_", 1)
                if len(parts) == 2 and parts[0] in folder_map:
                    parent_folder = media_root / folder_map[parts[0]] / parts[1]
                    if parent_folder.is_dir():
                        for item in sorted(parent_folder.iterdir()):
                            if item.name.startswith("."):
                                continue
                            item_id = f"{object_id}_{item.name}"
                            if item.is_dir():
                                items.append(f'<container id="{escape(item_id)}" parentID="{escape(object_id)}" restricted="true">'
                                             f'<dc:title>{escape(item.name)}</dc:title>'
                                             f'<upnp:class>object.container.storageFolder</upnp:class></container>')
                            elif item.is_file() and item.suffix.lower() in VIDEO_EXT | AUDIO_EXT:
                                mime = MIME_MAP.get(item.suffix.lower(), "video/mp4")
                                import base64
                                rel = str(item.relative_to(media_root))
                                token = base64.urlsafe_b64encode(rel.encode()).decode()
                                stream_url = f"{base_url}/api/stream/{token}"
                                size = item.stat().st_size
                                upnp_class = "object.item.videoItem" if item.suffix.lower() in VIDEO_EXT else "object.item.audioItem.musicTrack"
                                items.append(
                                    f'<item id="{escape(item_id)}" parentID="{escape(object_id)}" restricted="true">'
                                    f'<dc:title>{escape(item.name)}</dc:title>'
                                    f'<upnp:class>{upnp_class}</upnp:class>'
                                    f'<res protocolInfo="http-get:*:{mime}:*" size="{size}">{escape(stream_url)}</res>'
                                    f'</item>'
                                )

        total = len(items)
        page = items[start:start + count]
        didl = (
            '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            + "".join(page)
            + '</DIDL-Lite>'
        )
        return didl, len(page), total

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "friendly_name": self._friendly_name,
            "local_ip": self._local_ip,
            "uuid": self._uuid,
            "ssdp_port": SSDP_PORT,
        }


# Singleton
dlna_server = DLNAServer()
