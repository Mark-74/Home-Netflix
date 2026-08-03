# In-depth: how Home-Netflix works

This document explains the internals — how requests flow, why certain design choices were made, and where to look when something breaks. For setup and everyday use, see [README.md](README.md).

## Project layout

```
backend/
  main.py            FastAPI app: routes, static file mounts, filesystem browsing
  db.py              SQLite access layer (schema, CRUD for the films table)
  scripts/
    film.py           Film / Stored data classes
    search.py         Queries the catalog site and parses results
    download.py       Playwright + yt-dlp download pipeline
    urlgetter.py      Resolves the catalog's current (rotating) domain via Telegram
    utlis.py          Connectivity check used to pick online/offline frontend
    tg_session.py     One-time CLI to generate a Telethon session string
frontend/
  index.html          Search page ("Find a film")
  offline.html         Shelf page: downloaded/downloading films, video player
  export.html          Export page: pick a film + destination, move it out
  app.css              Shared styling for all three pages
Movies/, Covers/, data/  Runtime storage (video files, cover art, SQLite DB)
```

There is no frontend build step. The three HTML pages are served directly as static files, each with its own inline `<script>` block, and talk to the backend purely over `fetch()`.

## The domain rotation problem

The catalog this app scrapes (StreamingCommunity) rotates its public domain frequently to dodge blocking. There's no fixed API endpoint to hit. Instead, a public Telegram channel posts the current domain whenever it changes.

`backend/scripts/urlgetter.py` handles this:

- `get_new_url()` uses Telethon (a Telegram client library) to scan the most recent messages in the configured channel (`TG_CHANNEL`) for a URL matching the pattern `streamingcommunity*.<tld>`, newest message first.
- Because this needs an authenticated Telegram session, and creating one requires an interactive phone-number login, `tg_session.py` is a separate one-time script you run locally to produce a reusable `TG_SESSION` string. That string, plus `TG_API_ID`/`TG_API_HASH`, go into `.env` so the container can authenticate non-interactively.
- The Telethon client is async, but this module needs to expose a synchronous `URL` constant at import time. `_run_in_thread()` works around the "event loop already running" problem (Telethon's asyncio loop vs. uvicorn's) by spinning up a dedicated thread with its own fresh event loop for the one-off fetch.
- `URL` and `COVER_URL` are resolved exactly once, at first import, and reused by every other module (`search.py`, `download.py`, the `/api/config` route). If the domain rotates while the process is running, calling `refresh()` re-fetches and updates both in place — but nothing currently calls `refresh()` automatically; a container restart is the practical way to pick up a new domain today.
- If the Telegram env vars are missing or the fetch fails for any reason, `get_new_url()` swallows the error, logs it, and falls back to `DEFAULT_URL` (empty string), rather than crashing the app at import time.

The frontend never hardcodes the catalog domain. It calls `/api/config` on load to get `url` and `cover_base`, and builds cover image URLs from that.

## Search

`POST /api/search?title=...` → `backend/scripts/search.py::search_by_title()`.

The catalog's archive page embeds its search results as a JSON blob inside a `data-page` attribute on a `<div id="app">` (a common pattern for server-rendered Inertia.js-style apps). The scraper:

1. Requests `{URL}/it/archive?search={title}` with headers that mimic a real browser (referrer, `X-Requested-With`, `Sec-Fetch-*`) so the request isn't rejected as non-browser traffic.
2. Parses the HTML with BeautifulSoup, finds `#app`, and `json.loads()`s its `data-page` attribute.
3. Walks `props.titles`, and for each entry builds a `Film` (title, cover filename, slug, id), picking the cover image whose `type` is `"cover"` out of each title's `images` array.

No browser automation is needed for search — it's a plain HTTP request, since the search results are present in the initial HTML response.

## Download pipeline

`POST /api/download` takes a `FilmIn` body and immediately returns `{"status": "ok"}`, handing the actual work to a FastAPI `BackgroundTasks` task running `download_film()`. This keeps the request non-blocking; progress is polled separately via `/api/films`.

`backend/scripts/download.py::download_film()` does two very different things in sequence:

**1. Finding the real video URL (Playwright).** The catalog site doesn't expose a direct, stable download link — the actual HLS playlist URL is only visible in network traffic once the player loads. So a headless Chromium instance (Playwright) visits the watch page (`{URL}/it/watch/{id}`), with images/stylesheets/fonts blocked for speed, and a request listener watches for any request whose URL contains `token` and `playlist/` (excluding jwplayer's own internal requests). The first match found within a 10-second window is taken as the download URL; the browser is closed immediately after, whether or not anything was found.

**2. Downloading the file (yt-dlp).** Once a playlist URL is known, the film row is inserted into the DB (status `downloading`, progress `0`) via `add_film()`. If the id already exists and its status is `completed`, the function returns early — a rerun on an already-downloaded film is a no-op rather than a fresh save. yt-dlp then downloads the HLS stream directly to `Movies/{title}.mp4`, using native HLS with 16 concurrent fragment downloads. A custom progress hook computes a percentage from whichever fields yt-dlp provides for the current stream (native `_percent`, byte counts, or fragment index/count as a last resort) and writes it to the DB only when the whole-percent value changes, to avoid a DB write per fragment. Progress is capped at 99% during download and explicitly set to 100 + status `completed` only after `ydl.download()` returns successfully. The cover image is fetched synchronously in the same worker thread, right before the yt-dlp call.

If the download throws at any point, the film's DB row is deleted (`delete_film`) and the exception is re-raised into the background task (where FastAPI logs it, but there's no user-facing error surface for a failed background download today — the film simply disappears from the shelf).

The blocking parts (`requests.get` for the cover, `yt_dlp.YoutubeDL(...).download(...)`) run inside `asyncio.to_thread()` so they don't block the event loop that's also serving other requests (like the polling `/api/films` calls from the shelf page).

## Data model and storage

`backend/db.py` is a thin wrapper around a single SQLite table:

```sql
CREATE TABLE films (
  id INTEGER PRIMARY KEY,       -- catalog's own film id, reused as our primary key
  title VARCHAR(255) NOT NULL,
  path VARCHAR(255) NOT NULL,   -- filename under Movies/
  cover VARCHAR(255),           -- filename under Covers/
  status VARCHAR(255) NOT NULL, -- "downloading" | "completed"
  progress INTEGER NOT NULL DEFAULT 0
)
```

Each function (`add_film`, `update_status`, `update_progress`, `delete_film`, `list_films`, `get_path`) opens its own short-lived `sqlite3.connect()` — there's no connection pool or ORM. `films.py` defines two small data classes: `Film` (search result, before it's ever downloaded) and `Stored` (a DB row, after `add_film`).

On startup, `db.py` also runs a lightweight migration: if an existing `database.db` predates the `progress` column, it's added via `ALTER TABLE`. This is intentionally the only migration strategy — there's no versioned migration framework, since the schema is small and changes infrequently.

`DB_PATH` defaults to `data/database.db` but can be overridden with the `DB_PATH` env var. The parent directory is always created up front — this matters specifically under Docker, where a bind mount of a not-yet-existing file can otherwise turn into a directory mount and break things silently.

## Filesystem browsing and export

`GET /api/browse` powers the folder picker on the export page. It's deliberately sandboxed: a caller can only browse the user's home directory (top level only — to reach shortcuts), `~/Videos`, or any directory mounted under `/media/<user>`, `/run/media/<user>`, `/media`, or `/mnt` (covers common Linux external-drive mount points). `_within()` checks a candidate path is the allowed root or nested under it; `_drive_mounts()` enumerates what's actually mounted right now, so newly plugged-in drives show up without a restart. The response includes the current directory's subfolders, a parent link (omitted at a root, to block climbing above it), a shortcuts list, and the full set of allowed roots so the frontend can grey out unreachable breadcrumb segments.

`POST /api/export` takes a film `id` and a `new_path` destination directory. It looks up the film's stored path, validates the source file exists and the destination is an existing directory, guards against overwriting a same-named file already there, then does a plain `shutil.move()` followed by `delete_film(id)` — export is a one-way move, not a copy, and it always removes the film from the shelf/DB regardless of whether the destination is on the same filesystem (Python's `shutil.move` copies + deletes automatically when moving across filesystems, e.g. a container volume mount to `/media/...`).

## Frontend

Three independent static pages, no framework, no bundler:

- **index.html** — search box, results grid, calls `/api/search` and `/api/download`.
- **offline.html** — the shelf. Polls `/api/films` once, then re-polls every second only while at least one film has status `downloading`. To avoid flicker, it distinguishes between "the set of films or their statuses changed" (full re-render, via a signature string of `id:status` pairs) and "only progress changed" (in-place progress bar update via `patchProgress()`, no DOM rebuild). Clicking a completed film's cover opens a modal `<video>` player pointed at `/movies/{path}`.
- **export.html** — lists completed films for selection, and a folder browser modal that walks `/api/browse` interactively, rendering clickable breadcrumbs and a shortcuts bar. The last-used destination is remembered in `localStorage`.

`backend/main.py` decides which landing page to serve at `/` based on `utlis.check_connection()` — a 3-second timeout request to `https://www.google.com`. If it fails, `offline.html`'s sibling `offline.html`-labeled fallback (actually served from the same file structure) is returned instead of the search page, since search requires reaching the catalog site.

## Docker

The image is `python:3.11-slim` plus `ffmpeg` (required by yt-dlp for muxing/remuxing) and Debian's `chromium` package, which Playwright is pointed at via the `CHROMIUM_PATH` env var.

Playwright's own bundled Chromium is deliberately **not** used. It ships without proprietary codecs on arm64 (it has them on x86_64), and jwplayer decides which playback provider to use by asking the browser what it can decode. With no H.264/AAC it concludes nothing can play the item, aborts setup with error 102630, and never issues the playlist request the download pipeline is listening for — so downloads failed on a Raspberry Pi while working on an x86 machine. Debian's package is built with those codecs and, conveniently, tracks the same Chromium major version Playwright expects. `CHROMIUM_PATH` is unset outside Docker, in which case Playwright falls back to its own build.

`docker-compose.yml` bind-mounts `Movies/`, `Covers/`, `data/`, and both `backend/` and `frontend/` from the host (so code edits are picked up by uvicorn's `--reload` without rebuilding the image), plus `~/Videos` and `/media` (with `rshared` propagation, so drives mounted on the host after the container starts are still visible inside it) to support the export destination browser.

## Known rough edges

- A failed download deletes the DB row but leaves no user-visible error — the film just vanishes from the shelf. There's no retry or failure status.
- `urlgetter.refresh()` exists but nothing calls it; picking up a rotated domain currently requires a container restart.
- Every DB call opens a fresh SQLite connection rather than sharing one — fine at this scale (single user, low concurrency), but worth knowing if this ever needs to handle concurrent downloads at higher volume.
