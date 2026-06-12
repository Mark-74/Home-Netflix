import requests
from film import Film
URL = "https://streamingcommunityz.eu"

def download_film(movie : Film):
    r = requests.get(URL + f'/it/watch/{movie.id}')
    with open('resp.txt','w') as f:
        f.write(r.text)


