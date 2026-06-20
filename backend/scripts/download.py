import asyncio
import yt_dlp
import requests
from playwright.async_api import async_playwright
from backend.scripts.film import Film
from backend.db import add_film, update_status, get_status, delete_film


URL = "https://streamingcommunityz.us"
COVER_URL = "https://cdn.streamingcommunityz.us/images/"
async def download_film(movie : Film):
    async with async_playwright() as p:
        download_url = None
        found = asyncio.Event()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        def handle_req(request):
            nonlocal download_url
            if "token" in request.url and "playlist/" in request.url and not "jwplayer" in request.url:
                download_url = request.url
                found.set()

        BLOCK_TYPES = {"image", "stylesheet", "font"}
        async def block_assets(route):
            if route.request.resource_type in BLOCK_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", block_assets)
        page.on("request", handle_req)
        await page.goto(URL + f'/it/watch/{movie.id}', timeout=20000)
        try:
            await asyncio.wait_for(found.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        await browser.close()
        if not download_url:
            print("It wasnt possible to find a download url")
            return

    if add_film(movie) == "error":
        if get_status(movie.id) == "completed":
            print("Already exists")
            return "already exists"
        print("re-downloading stuck entry")
    else:
        print("added")
        
    class SilentLogger:
        def debug(self, _msg): pass
        def info(self, _msg): pass
        def warning(self, _msg): pass
        def error(self, _msg): print(_msg)

    def custom_progress_hook(d): # Slopped to show progress
        if d['status'] == 'downloading':
            pct = d.get('_percent', 0)
            frag_index = d.get('fragment_index', 0)
            frag_count = d.get('fragment_count', 0)
            filled = int(40 * pct / 100)
            bar = '=' * filled + ('>' if filled < 40 else '=') + ' ' * max(0, 39 - filled)
            frag_str = f" ({frag_index}/{frag_count})" if frag_count else ""
            print(f"\rDownloading: [{bar}] {pct:5.1f}%{frag_str}  ", end='', flush=True)
        elif d['status'] == 'finished':
            print(flush=True)

    options = {
        'format': 'bestvideo+bestaudio/best',
        'logger': SilentLogger(),
        'outtmpl' : f'Movies/{movie.title}.mp4',
        'progress_hooks' : [custom_progress_hook],
        'concurrent_fragment_downloads': 16,
        'hls_prefer_native': True,
        'socket_timeout': 15,
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': False,
    }
    print("Downloading")

    def _blocking_download():
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([download_url])
        resp = requests.get(COVER_URL + movie.cover)
        if resp.status_code == 200:
            with open('Covers/' + movie.title + '.webp', 'wb') as f:
                f.write(resp.content)

    try:
        await asyncio.to_thread(_blocking_download)
    except Exception as e:
        print(f"Download failed: {e}")
        delete_film(movie.id)
        raise
    update_status(movie.id, "completed")

    