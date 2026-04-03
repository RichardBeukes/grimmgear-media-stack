"""
GrimmGear Media Stack — Configuration
TOML-based settings with Pydantic validation.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    url: str = Field(default="sqlite:///./grimmgear.db", description="Database URL (sqlite or postgresql)")
    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="GG_DB_")


class ServerSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 7777
    workers: int = 1
    debug: bool = False
    base_url: str = ""
    secret_key: str = "change-me-in-production"

    model_config = SettingsConfigDict(env_prefix="GG_SERVER_")


class PathSettings(BaseSettings):
    media_root: Path = Field(default=Path("D:/Media"), description="Root folder for all media")
    download_dir: Path = Field(default=Path("D:/Downloads"), description="Download client save path")

    model_config = SettingsConfigDict(env_prefix="GG_PATH_")

    @property
    def movies_dir(self) -> Path:
        return self.media_root / "Movies"

    @property
    def tv_dir(self) -> Path:
        return self.media_root / "TVshows"

    @property
    def music_dir(self) -> Path:
        return self.media_root / "Music"

    @property
    def books_dir(self) -> Path:
        return self.media_root / "Books"

    @property
    def comics_dir(self) -> Path:
        return self.media_root / "Comics"


class ModuleSettings(BaseSettings):
    """Toggle modules on/off. All installed, enable what you need."""
    movies: bool = True
    tv: bool = True
    music: bool = False
    books: bool = False
    comics: bool = False
    subtitles: bool = False
    transcode: bool = False
    requests: bool = False
    indexers: bool = True
    streaming: bool = True

    model_config = SettingsConfigDict(env_prefix="GG_MODULE_")


class DownloadClientSettings(BaseSettings):
    qbit_url: str = "http://localhost:8081"
    qbit_username: str = ""
    qbit_password: str = ""
    usenet_url: str = ""
    usenet_api_key: str = ""
    slskd_url: str = "http://localhost:5030"
    slskd_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="GG_DL_")


class IndexerProxySettings(BaseSettings):
    """Auto-discover indexers from Prowlarr or Jackett."""
    prowlarr_url: str = "http://localhost:9696"
    prowlarr_api_key: str = ""
    jackett_url: str = "http://localhost:9117"
    jackett_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="GG_IDX_")


class MediaServerSettings(BaseSettings):
    """Optional external media server. If streaming module is ON, this is optional."""
    type: str = "built-in"  # built-in, plex, jellyfin, emby
    url: str = ""
    token: str = ""

    model_config = SettingsConfigDict(env_prefix="GG_MEDIA_SERVER_")


class DLNASettings(BaseSettings):
    enabled: bool = True
    friendly_name: str = "GrimmGear Media"
    port: int = 8200

    model_config = SettingsConfigDict(env_prefix="GG_DLNA_")


class AuthSettings(BaseSettings):
    type: str = "local"  # local, oidc
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    model_config = SettingsConfigDict(env_prefix="GG_AUTH_")


class Settings(BaseSettings):
    """Root settings — aggregates all config sections."""
    app_name: str = "GrimmGear Mediarr"
    version: str = "0.1.0"

    server: ServerSettings = ServerSettings()
    database: DatabaseSettings = DatabaseSettings()
    paths: PathSettings = PathSettings()
    modules: ModuleSettings = ModuleSettings()
    download: DownloadClientSettings = DownloadClientSettings()
    indexer_proxy: IndexerProxySettings = IndexerProxySettings()
    media_server: MediaServerSettings = MediaServerSettings()
    dlna: DLNASettings = DLNASettings()
    auth: AuthSettings = AuthSettings()

    model_config = SettingsConfigDict(
        env_prefix="GG_",
        toml_file="grimmgear.toml",
    )


# Singleton
settings = Settings()
