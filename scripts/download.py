import requests, re, yt_dlp
from playwright.sync_api import sync_playwright
from film import Film


URL = "https://streamingcommunityz.eu"

def download_film(movie : Film):
    with sync_playwright() as p:
        download_url = None
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def handle_req(request):
            nonlocal download_url
            if "token" in request.url and "playlist/" in request.url and not "jwplayer" in request.url:
                download_url = request.url
                

        page.on("request",handle_req)
        r = page.goto(URL + f'/it/watch/{movie.id}')
        page.wait_for_timeout(1000)
        browser.close()
        if not download_url:
            print("It wasnt possible to find a download url")
            return
        
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
        'outtmpl' : f'../Movies/{movie.title}.mp4',
        'progress_hooks' : [custom_progress_hook],
        'hls_prefer_native': True,
    }
    print("Downloading")
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([download_url])

    