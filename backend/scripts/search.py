import json
import requests
from backend.scripts.film import Film
from backend.scripts.urlgetter import URL
from bs4 import BeautifulSoup

def find_image_cover( images : list ):
    for img in images:
        if img["type"] == "cover":
            return img["filename"]

def search_by_title( name : str ) -> list:
    session = requests.Session()
    headers = {
        "referrer": URL + '/it/archive',
        "Content-Type":"application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "text/html, application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "mode":"cors"
    }
    r = session.get(URL + f'/it/archive?search={name}',headers=headers)
    if r.status_code != 200:
        return
    soup = BeautifulSoup(r.text,'html.parser')
    data = soup.find('div',id="app")
    json_data = json.loads(data['data-page'])
    films = json_data["props"]["titles"]
    films_found = []
    for f in films:
        film = Film(f["name"], find_image_cover(f["images"]), f["slug"], f["id"])
        films_found.append(film)
    
    return films_found

