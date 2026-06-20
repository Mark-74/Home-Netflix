import sys
from pathlib import Path
from backend.scripts.utlis import check_connection


ROOT = Path(__file__).resolve().parent.parent
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.scripts.search import search_by_title
from backend.scripts.download import download_film
from backend.db import list_films
import asyncio

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


# Cover images for downloaded films. Mounted before the "/" catch-all so it matches first.
app.mount("/covers", StaticFiles(directory=COVERS_DIR), name="covers")
app.mount("/movies", StaticFiles(directory=MOVIES_DIR), name="movies")
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")