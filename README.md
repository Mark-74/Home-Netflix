# Home-Netflix

A small self-hosted app that lets you search a streaming catalog, pull a film down to local disk, watch it from your own "shelf" once it's downloaded, and export finished files out to an external drive or folder. Runs as a single Docker container with a FastAPI backend and a plain HTML/JS frontend — no build step, no external database.

For an explanation of how it works internally (backend structure, download pipeline, domain rotation handling, filesystem browsing, etc.), see [INDEPTH.md](INDEPTH.md).

## Requirements

- Docker and Docker Compose
- A Telegram account (used only to read the current catalog domain — see below)

## Setup

1. Clone the repo and `cd` into it.
2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
3. Get a Telegram `api_id` and `api_hash` from https://my.telegram.org (API development tools) and put them in `.env`.
4. Generate a session string once, locally (not inside Docker, since it needs an interactive login):
   ```bash
   pip install telethon
   python -m backend.scripts.tg_session
   ```
   Enter your `api_id` and `api_hash` when prompted, then paste the printed `TG_SESSION` value into `.env`.
5. Set `TG_CHANNEL` in `.env` to the Telegram channel (e.g. `@somechannel`) that posts the current catalog domain.
6. Start the app:
   ```bash
   docker compose up --build
   ```
7. Open http://localhost:8000.

## Using the app

**Find a film** — the home page (`/`). Type a title and press Find. Results come from the live catalog; press "Download" on a result to start pulling it to disk in the background.

**My shelf** — `/offline.html`. Shows every film that's downloading or finished. In-progress downloads show a live progress bar. Click a finished film's cover to play it in the built-in video player.

**Export** — `/offline.html` → Export. Pick a finished film, then choose a destination folder using the built-in folder browser (limited to your home directory, `~/Videos`, and any mounted external drive), and press Export. This moves the file out of the app and removes it from the shelf.

If the app can't reach the internet, it automatically falls back to an offline-friendly landing page.

## Data and storage

- `Movies/` — downloaded video files
- `Covers/` — downloaded cover art
- `data/database.db` — SQLite database tracking each film's title, status, and download progress

These directories are mounted as Docker volumes, so downloads and the database persist across container restarts.

## Configuration reference

All configuration lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `TG_API_ID` | Telegram API ID from my.telegram.org |
| `TG_API_HASH` | Telegram API hash from my.telegram.org |
| `TG_SESSION` | Session string produced by `backend/scripts/tg_session.py` |
| `TG_CHANNEL` | Telegram channel that announces the current catalog domain |

`docker-compose.yml` also mounts `~/Videos` and `/media` into the container, so folders there are selectable as export destinations from inside Docker.

## Running without Docker

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

`ffmpeg` must be installed on the host (the Docker image installs it automatically; see `Dockerfile`).
