"""
GrimmGear — Media Models
Movies, Series, Episodes, Artists, Albums, Tracks, Authors, Books, Comics.
"""

from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MediaItemMixin


# ============================================================
# Movies Module
# ============================================================

class Movie(Base, MediaItemMixin):
    __tablename__ = "movies"

    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    original_language: Mapped[str] = mapped_column(String(10), default="en")
    runtime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genres: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    quality_profile_id: Mapped[int] = mapped_column(Integer, default=1)
    root_folder: Mapped[str] = mapped_column(String(500), default="")
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    edition: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Multi-version support
    versions: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)


# ============================================================
# TV Module
# ============================================================

class Series(Base, MediaItemMixin):
    __tablename__ = "series"

    tvdb_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    original_language: Mapped[str] = mapped_column(String(10), default="en")
    series_type: Mapped[str] = mapped_column(String(20), default="standard")  # standard, daily, anime
    quality_profile_id: Mapped[int] = mapped_column(Integer, default=1)
    root_folder: Mapped[str] = mapped_column(String(500), default="")
    season_folder: Mapped[bool] = mapped_column(Boolean, default=True)
    genres: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)

    seasons: Mapped[list["Season"]] = relationship(back_populates="series", cascade="all, delete-orphan")


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"))
    season_number: Mapped[int] = mapped_column(Integer)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)

    series: Mapped["Series"] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(back_populates="season", cascade="all, delete-orphan")


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    episode_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), default="")
    air_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_filler: Mapped[bool] = mapped_column(Boolean, default=False)

    season: Mapped["Season"] = relationship(back_populates="episodes")


# ============================================================
# Music Module
# ============================================================

class Artist(Base, MediaItemMixin):
    __tablename__ = "artists"

    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    spotify_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quality_profile_id: Mapped[int] = mapped_column(Integer, default=1)
    root_folder: Mapped[str] = mapped_column(String(500), default="")

    albums: Mapped[list["Album"]] = relationship(back_populates="artist", cascade="all, delete-orphan")


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    album_type: Mapped[str] = mapped_column(String(50), default="album")  # album, ep, single, compilation
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)

    artist: Mapped["Artist"] = relationship(back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship(back_populates="album", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    track_number: Mapped[int] = mapped_column(Integer, default=1)
    disc_number: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    acoustid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    isrc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    album: Mapped["Album"] = relationship(back_populates="tracks")


# ============================================================
# Books Module
# ============================================================

class Author(Base, MediaItemMixin):
    __tablename__ = "authors"

    goodreads_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    openlibrary_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quality_profile_id: Mapped[int] = mapped_column(Integer, default=1)
    root_folder: Mapped[str] = mapped_column(String(500), default="")

    books: Mapped[list["Book"]] = relationship(back_populates="author", cascade="all, delete-orphan")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    isbn13: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    asin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    book_type: Mapped[str] = mapped_column(String(20), default="ebook")  # ebook, audiobook, magazine
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)

    author: Mapped["Author"] = relationship(back_populates="books")


# ============================================================
# Shared: Quality Profiles, Indexers, Download Queue
# ============================================================

class QualityProfile(Base):
    __tablename__ = "quality_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(20), default="English")
    min_quality: Mapped[str] = mapped_column(String(50), default="HDTV-720p")
    cutoff: Mapped[str] = mapped_column(String(50), default="Bluray-1080p")
    upgrade_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    items: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)


class Indexer(Base):
    __tablename__ = "indexers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    indexer_type: Mapped[str] = mapped_column(String(50), default="torznab")  # torznab, newznab, rss
    categories: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    use_flaresolverr: Mapped[bool] = mapped_column(Boolean, default=False)
    mirror_urls: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)


class DownloadQueueItem(Base):
    __tablename__ = "download_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(20))  # movie, episode, track, book
    media_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, downloading, completed, importing, failed
    download_client: Mapped[str] = mapped_column(String(50), default="qbittorrent")
    download_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # admin, user, viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    streaming_services: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    quota_movies: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    quota_tv: Mapped[int] = mapped_column(Integer, default=0)


class MediaRequest(Base):
    __tablename__ = "media_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(20))  # movie, tv
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, denied, available
    requester: Mapped[str] = mapped_column(String(100), default="anonymous")
    votes: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class SystemSetting(Base):
    """Persistent key-value settings store. Survives restarts."""
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(String(5000), default="")
    category: Mapped[str] = mapped_column(String(50), default="general")  # paths, download, media_server, notifications, general


class RootFolder(Base):
    """Configurable media root folders per content type."""
    __tablename__ = "root_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(1000))
    media_type: Mapped[str] = mapped_column(String(20))  # movie, tv, music, books, comics
    name: Mapped[str] = mapped_column(String(200), default="")
    free_space: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class DownloadClient(Base):
    """Configured download clients (qBit, SABnzbd, etc)."""
    __tablename__ = "download_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    client_type: Mapped[str] = mapped_column(String(50))  # qbittorrent, sabnzbd, transmission, deluge, nzbget
    host: Mapped[str] = mapped_column(String(500))
    port: Mapped[int] = mapped_column(Integer, default=8080)
    username: Mapped[str] = mapped_column(String(200), default="")
    password: Mapped[str] = mapped_column(String(200), default="")
    api_key: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(100), default="grimmgear")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # lower = preferred


class NotificationAgent(Base):
    """Configured notification channels."""
    __tablename__ = "notification_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    agent_type: Mapped[str] = mapped_column(String(50))  # discord, telegram, webhook, email
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # type-specific config
    on_grab: Mapped[bool] = mapped_column(Boolean, default=True)
    on_import: Mapped[bool] = mapped_column(Boolean, default=True)
    on_upgrade: Mapped[bool] = mapped_column(Boolean, default=False)
    on_health: Mapped[bool] = mapped_column(Boolean, default=False)
