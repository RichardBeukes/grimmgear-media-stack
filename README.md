# GrimmGear Media Stack

> One system. Every media type. Every feature. Toggle what you need.

GrimmGear replaces **30+ separate applications** with a single unified media automation platform.
Built-in streaming means you don't even need Plex.

## Quick Start

```bash
# Clone
git clone https://github.com/RichardBeukes/grimmgear-media-stack.git
cd grimmgear-media-stack

# Install backend
cd backend
pip install -r requirements.txt

# Run
python run.py
```

Open **http://localhost:7777** — GrimmGear is running.

## What It Replaces

Sonarr + Radarr + Lidarr + Readarr + Prowlarr + Bazarr + Tdarr + Seerr +
Tautulli + Kometa + Maintainerr + Recyclarr + Unpackerr + Notifiarr +
Cross-seed + qbit_manage + Autobrr + Mylar3 + Audiobookshelf + Kavita +
and more — **all in one**.

## Modules (Toggle On/Off)

| Module | Replaces | Default |
|--------|----------|---------|
| Movies | Radarr | ON |
| TV Shows | Sonarr | ON |
| Music | Lidarr + SoulSync | OFF |
| Books | Readarr + LazyLibrarian | OFF |
| Comics | Mylar3 + Kapowarr | OFF |
| Subtitles | Bazarr | OFF |
| Transcode | Tdarr | OFF |
| Requests | Seerr + Ombi | OFF |
| Indexers | Prowlarr | ON |
| Streaming | Plex/Jellyfin (built-in) | ON |

## Tech Stack

- **Backend:** Python 3.12+ / FastAPI
- **Frontend:** Svelte 5 / TypeScript (coming)
- **Database:** SQLite (single-user) or PostgreSQL (scale)
- **Streaming:** DLNA/UPnP + HLS web player + FFmpeg

## API Docs

Start the server and visit **http://localhost:7777/api/docs** for interactive Swagger documentation.

## Docker

```bash
cd docker
docker compose up -d
```

## Acknowledgements

Built on the shoulders of giants: Sonarr, Radarr, Lidarr, Readarr, Prowlarr,
Bazarr, Tdarr, Seerr, Tautulli, Kometa, Maintainerr, Audiobookshelf, Kavita,
SoulSync, Autobrr, MediaManager, and the entire *arr community.

## License

GPL v3

## Credits

- **Richard Beukes** — GrimmGear Systems
- Deep analysis powered by Claude Code (11 research agents, 9,343 C# files analyzed)
