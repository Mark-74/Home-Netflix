import sqlite3
from backend.scripts.film import Film, Stored

DB_PATH = 'database.db'

def get_conn():
    return sqlite3.connect(DB_PATH)

with get_conn() as conn:
    conn.execute("""
                CREATE TABLE IF NOT EXISTS films (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                path VARCHAR(255) NOT NULL,
                cover VARCHAR(255),
                status VARCHAR(255) NOT NULL
               );""")

def check_already_exists(id):
    query = "SELECT 1 FROM films WHERE id = ?"
    with get_conn() as conn:
        film = conn.execute(query, (id,)).fetchone()
    return film is not None

def add_film(film : Film):
    if check_already_exists(film.id):
        return "error"
    path = film.title + '.mp4'
    cover = film.title + '.webp'
    status = "downloading"
    query = "INSERT INTO FILMS (id, title, path,cover,status) VALUES (?, ?, ?, ?, ?)"
    with get_conn() as conn:
        conn.execute(query, (film.id, film.title, path, cover, status))
    print("ok")
    return "ok"
def get_status(id):
    query = "SELECT status FROM films WHERE id = ?"
    with get_conn() as conn:
        row = conn.execute(query, (id,)).fetchone()
    return row[0] if row else None

def update_status(id, status="completed"):
    query = "UPDATE films SET status = ? WHERE id = ?"
    with get_conn() as conn:
        conn.execute(query, (status, id))

def delete_film(id):
    query = "DELETE FROM films WHERE id = ?"
    with get_conn() as conn:
        conn.execute(query,(id,))

def list_films():
    query = "SELECT * FROM films"
    with get_conn() as conn:
        db_entries = conn.execute(query).fetchall()
    films = []
    for f in db_entries:
        films.append(Stored(f[0],f[1],f[2],f[3],f[4]))
    return films

def get_path(id : int):
    query = "SELECT path FROM films WHERE id = ?"
    with get_conn() as conn:
        path = conn.execute(query, (id,)).fetchone()
    return path[0]
    