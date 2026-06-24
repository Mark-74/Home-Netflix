import sys
from pathlib import Path
from backend.scripts.utlis import check_connection


ROOT = Path(__file__).resolve().parent.parent
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.scripts.search import search_by_title
from backend.scripts.download import download_film
from backend.db import list_films, delete_film, get_path
import asyncio
import shutil

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = ROOT / "frontend"
ONLINE_FRONTEND = FRONTEND_DIR / "index.html"
OFFLINE_FRONTEND = FRONTEND_DIR / "offline.html"
COVERS_DIR = ROOT / "Covers"
MOVIES_DIR = ROOT / "Movies"
# StaticFiles refuses to mount a missing directory — ensure they exist.
COVERS_DIR.mkdir(exist_ok=True)
MOVIES_DIR.mkdir(exist_ok=True)


class FilmIn(BaseModel):
    title: str
    cover: str | None = None
    slug: str | None = None
    id: int


@app.get("/")
def home():
    return FileResponse(ONLINE_FRONTEND if check_connection() else OFFLINE_FRONTEND)


@app.post("/api/search")
def search(title: str):
    if not title:
        raise HTTPException(status_code=400, detail="Title required")
    films = search_by_title(title)
    return films


@app.post("/api/download")
async def download(film: FilmIn, background_tasks : BackgroundTasks):
    background_tasks.add_task(download_film,film) # download_film only reads .id and .title
    return {"status": "ok"}

@app.get('/api/films')
def get_film():
    return list_films()

def _within(child: Path, parent: Path) -> bool:
    """True if child is parent itself or sits underneath it."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _drive_mounts(home: Path) -> list[Path]:
    """Resolved roots of mounted hard drives / removable media (Linux)."""
    user = home.name
    candidates = [Path("/media") / user, Path(f"/run/media/{user}"), Path("/media"), Path("/mnt")]
    mounts: list[Path] = []
    seen: set[Path] = set()
    for root in candidates:
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir(), key=lambda e: e.name.lower())
        except PermissionError:
            continue
        for mount in entries:
            if not mount.is_dir() or mount.name.startswith('.'):
                continue
            r = mount.resolve()
            if r in seen:
                continue
            seen.add(r)
            mounts.append(r)
    return mounts


@app.get('/api/browse')
def browse(path: str | None = None):
    # Browsing is locked to: home (launchpad only), the Videos folder, and any
    # mounted external drive. Everything else is off-limits.
    home = Path.home().resolve()
    videos = (home / "Videos")
    drives = _drive_mounts(home)
    allowed_roots = list(drives)
    if videos.is_dir():
        allowed_roots.append(videos.resolve())

    base = (Path(path).expanduser() if path else home).resolve()
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")

    is_home = base == home
    if not (is_home or any(_within(base, r) for r in allowed_roots)):
        raise HTTPException(status_code=403, detail="That folder is off-limits")

    try:
        names = sorted(
            (e.name for e in base.iterdir() if e.is_dir() and not e.name.startswith('.')),
            key=str.lower,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied for that folder")

    # Only show sub-folders the user is actually allowed to enter. At home this
    # leaves just Videos; drives are reached via the shortcuts below.
    dirs = [n for n in names if any(_within((base / n).resolve(), r) for r in allowed_roots)]

    # No climbing above a root (home or a drive/Videos top): hide the parent there.
    is_root = is_home or any(base == r for r in allowed_roots)
    parent = None if is_root else str(base.parent)

    shortcuts = [{"name": "Home", "path": str(home)}]
    if videos.is_dir():
        shortcuts.append({"name": "Videos", "path": str(videos.resolve())})
    for d in drives:
        shortcuts.append({"name": d.name, "path": str(d)})

    return {
        "path": str(base),
        "parent": parent,
        "dirs": dirs,
        "shortcuts": shortcuts,
        # Paths the UI may sit at or climb to (used to gate breadcrumb clicks).
        "roots": [str(home)] + [str(r) for r in allowed_roots],
    }

@app.post('/api/export')
def export(id, new_path : str):
    path = get_path(id)
    if path == None:
        raise HTTPException(status_code=400, detail="No film was found with that id")
    src = MOVIES_DIR / Path(path)
    dest = Path(new_path)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="The source isn't a file or doesn't exist")
    if not dest.is_dir():
        raise HTTPException(status_code=400, detail="The destination has to be an existing directory")
    dest = dest / src.name
    if dest.exists():
        raise HTTPException(status_code=409, detail="A file by that name already exists in the destination")
    shutil.move(str(src),str(dest))
    delete_film(id)
    return {"status":"ok"}

app.mount("/covers", StaticFiles(directory=COVERS_DIR), name="covers")
app.mount("/movies", StaticFiles(directory=MOVIES_DIR), name="movies")
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")