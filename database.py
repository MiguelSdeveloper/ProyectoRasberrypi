"""
=====================================================================
 DATABASE.PY -- Toda la comunicación con la base de datos SQLite
=====================================================================
CONCEPTO CLAVE para explicarle a tus compañeros:

SQLite no es un programa aparte que tengas que instalar ni un
servidor que corra en segundo plano (a diferencia de MySQL o
PostgreSQL). Es solo UN ARCHIVO en el disco (data/facesec.db) que
Python sabe leer/escribir de forma estructurada, como si fuera un
Excel con "reglas". Por eso es ideal para un proyecto como este:
cero configuración, cero instalación extra.

Tenemos 2 TABLAS (como 2 hojas de un Excel):

  people
  ------
  id   | name         | role
  1    | Miguel       | Admin
  2    | Compañero A  | Estudiante

  recognition_events
  -------------------
  id | person_id | person_name | camera_source | start_time | end_time | video_path
  1  | 1         | Miguel      | pi            | 14:03:01   | 14:03:22 | data/recordings/...

Cada función de este archivo hace UNA sola cosa (abrir conexión,
guardar una persona, registrar un evento, etc.) -- eso se llama
"separación de responsabilidades" y hace el código más fácil de leer
y de arreglar cuando algo falla.
"""
import sqlite3
import time

import config


def get_connection():
    """
    Abre una conexión a la base de datos. 'row_factory = sqlite3.Row'
    hace que podamos leer los resultados como diccionarios
    (fila["name"]) en vez de solo por posición (fila[1]), que es
    mucho más legible.
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Crea las tablas SI NO EXISTEN todavía. Es seguro llamar esta
    función cada vez que arranca el programa: si las tablas ya
    existen, "CREATE TABLE IF NOT EXISTS" no hace nada.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id   INTEGER PRIMARY KEY,   -- mismo ID que usa el modelo LBPH
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Invitado'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recognition_events (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id      INTEGER,
            person_name    TEXT NOT NULL,
            person_role    TEXT,
            camera_source  TEXT NOT NULL,   -- "pi" o "wifi"
            start_time     TEXT NOT NULL,
            end_time       TEXT,
            video_path     TEXT
        )
    """)
    conn.commit()
    conn.close()


# --------------------- Tabla "people" ---------------------

def add_person(person_id, name, role):
    """
    Inserta o actualiza una persona. 'INSERT OR REPLACE' significa:
    si ya existe un registro con ese id, lo sobreescribe; si no
    existe, lo crea. Así puedes re-registrar a alguien con nombre o
    rol corregido sin duplicar filas.
    """
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO people (id, name, role) VALUES (?, ?, ?)",
        (person_id, name, role),
    )
    conn.commit()
    conn.close()


def get_people():
    """
    Devuelve TODAS las personas registradas como un diccionario:
    { 1: {"name": "Miguel", "role": "Admin"}, 2: {...}, ... }
    Esto es lo que usa recognition_engine.py para traducir el
    "ID numérico" que predice el modelo LBPH a un nombre y rol reales.
    """
    conn = get_connection()
    rows = conn.execute("SELECT * FROM people").fetchall()
    conn.close()
    return {row["id"]: {"name": row["name"], "role": row["role"]} for row in rows}


def next_person_id():
    """
    Calcula el próximo ID disponible (el máximo existente + 1).
    Si no hay nadie registrado todavía, empieza en 1.
    """
    conn = get_connection()
    row = conn.execute("SELECT MAX(id) AS max_id FROM people").fetchone()
    conn.close()
    return (row["max_id"] or 0) + 1


# --------------------- Tabla "recognition_events" ---------------------

def log_recognition_start(person_id, person_name, person_role, camera_source):
    """
    Se llama en el INSTANTE en que empezamos a grabar a alguien.
    Crea una fila nueva con start_time = ahora, y end_time vacío
    todavía (se completa después con log_recognition_end).
    Devuelve el 'id' de esa fila para poder completarla después.
    """
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO recognition_events
           (person_id, person_name, person_role, camera_source, start_time)
           VALUES (?, ?, ?, ?, ?)""",
        (person_id, person_name, person_role, camera_source,
         time.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    event_id = cur.lastrowid   # el id autogenerado de la fila que acabamos de crear
    conn.close()
    return event_id


def log_recognition_end(event_id, video_path):
    """
    Se llama cuando la persona DEJA de verse en cámara: completa la
    fila que abrimos en log_recognition_start con la hora de fin y
    la ruta del video guardado.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE recognition_events SET end_time = ?, video_path = ? WHERE id = ?",
        (time.strftime("%Y-%m-%d %H:%M:%S"), video_path, event_id),
    )
    conn.commit()
    conn.close()


def get_recent_events(limit=20):
    """
    Trae los últimos N eventos, del más nuevo al más viejo
    (ORDER BY id DESC), para mostrarlos en el panel web.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recognition_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
