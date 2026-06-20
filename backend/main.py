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
        return {"status": "error"}
    films = search_by_title(title)
    return films


@app.post("/api/download")
async def download(film: FilmIn, background_tasks : BackgroundTasks):
    background_tasks.add_task(download_film,film) # download_film only reads .id and .title
    return {"status": "ok"}

@app.get('/api/films')
def get_film():
    return list_films()

@app.get('/api/browse')
def browse(path: str | None = None):
    base = Path(path).expanduser() if path else Path.home()
    base = base.resolve()
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Not a directory")
    try:
        dirs = sorted(
            (e.name for e in base.iterdir() if e.is_dir() and not e.name.startswith('.')),
            key=str.lower,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied for that folder")
    home = Path.home()
    shortcuts = [{"name": "Home", "path": str(home)}]
    for name in ("Desktop", "Downloads", "Movies", "Videos", "Documents"):
        cand = home / name
        if cand.is_dir():
            shortcuts.append({"name": name, "path": str(cand)})
    return {
        "path": str(base),
        "parent": str(base.parent) if base.parent != base else None,
        "dirs": dirs,
        "shortcuts": shortcuts,
    }

@app.post('/api/export')
def export(id, new_path : str):
    path = get_path(id)
    if path == None:
        raise HTTPException(status=400, detail="No film was found with that id")
    src = 'Movies' / Path(path)
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

# Cover images for downloaded films. Mounted before the "/" catch-all so it matches first.
app.mount("/covers", StaticFiles(directory=COVERS_DIR), name="covers")
app.mount("/movies", StaticFiles(directory=MOVIES_DIR), name="movies")
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")