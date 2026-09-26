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

Tenemos 3 TABLAS (como 3 hojas de un Excel):

  people
  ------
  id | name | role | id_document | phone | email | notes | age |
  workplace | position | institution | program

  recognition_events
  -------------------
  id | person_id | person_name | person_role | camera_source |
  start_time | end_time | video_path

  users
  -----
  username | password_hash | role | created_at

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

    'busy_timeout' es importante aquí: como Flask + cada CameraWorker
    (uno por cámara) escriben a la BD desde hilos distintos, SQLite
    puede rechazar una escritura con "database is locked" si dos
    llegan al mismo tiempo. Con busy_timeout, en vez de fallar de
    inmediato, espera hasta 3 segundos a que la otra termine.
    """
    conn = sqlite3.connect(config.DB_PATH, timeout=3.0)
    conn.execute("PRAGMA busy_timeout = 3000")
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
            camera_source  TEXT NOT NULL,   -- "pi", "usb" o "wifi"
            start_time     TEXT NOT NULL,
            end_time       TEXT,
            video_path     TEXT
        )
    """)
    # Usuarios que pueden ENTRAR AL PANEL WEB (login). Distinto de
    # "people", que son las personas que la CÁMARA reconoce.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username       TEXT PRIMARY KEY,
            password_hash  TEXT NOT NULL,
            role           TEXT NOT NULL DEFAULT 'viewer',  -- "admin" o "viewer"
            created_at     TEXT
        )
    """)
    _ensure_people_columns(conn)
    conn.commit()
    conn.close()


def _ensure_people_columns(conn):
    """
    MIGRACIÓN: agrega columnas nuevas a una tabla "people" que ya
    existía de una versión anterior (SQLite no tiene "ADD COLUMN IF
    NOT EXISTS", así que revisamos manualmente qué columnas faltan
    con PRAGMA table_info y las agregamos una por una).
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(people)").fetchall()}
    nuevas_columnas = {
        "id_document": "TEXT",  # cédula / identificación
        "phone": "TEXT",
        "email": "TEXT",
        "notes": "TEXT",
        "age": "INTEGER",
        "workplace": "TEXT",    # rol=Empleado
        "position": "TEXT",     # puesto/cargo, rol=Empleado
        "institution": "TEXT",  # rol=Estudiante
        "program": "TEXT",      # carrera, rol=Estudiante
    }
    for columna, tipo in nuevas_columnas.items():
        if columna not in existing:
            conn.execute(f"ALTER TABLE people ADD COLUMN {columna} {tipo}")


# --------------------- Tabla "people" ---------------------

def add_person(person_id, name, role, id_document=None, phone=None, email=None, notes=None,
                age=None, workplace=None, position=None, institution=None, program=None):
    """
    Inserta o actualiza una persona, incluyendo datos personales
    opcionales (cédula, teléfono, correo, notas, edad, y campos
    dependientes del rol: trabajo/puesto para Empleado, institución/
    carrera para Estudiante).
    """
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO people
           (id, name, role, id_document, phone, email, notes,
            age, workplace, position, institution, program)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (person_id, name, role, id_document, phone, email, notes,
         age, workplace, position, institution, program),
    )
    conn.commit()
    conn.close()


def get_person(person_id):
    """Trae UNA persona completa por ID (para el panel 'persona detectada')."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_people():
    """
    Devuelve TODAS las personas registradas como un diccionario:
    { 1: {"name": "Miguel", "role": "Admin", ...}, 2: {...}, ... }
    Esto es lo que usa recognition_engine.py para traducir el
    "ID numérico" que predice el modelo LBPH a un nombre y rol reales.
    """
    conn = get_connection()
    rows = conn.execute("SELECT * FROM people").fetchall()
    conn.close()
    return {
        row["id"]: {
            "name": row["name"], "role": row["role"],
            "id_document": row["id_document"], "phone": row["phone"],
            "email": row["email"], "notes": row["notes"],
            "age": row["age"], "workplace": row["workplace"],
            "position": row["position"], "institution": row["institution"],
            "program": row["program"],
        }
        for row in rows
    }


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


# --------------------- Tabla "users" (login del panel web) ---------------------

def add_user(username, password, role="viewer"):
    """
    Crea o actualiza un usuario del PANEL WEB. La contraseña se
    guarda SIEMPRE como hash (nunca en texto plano) usando el mismo
    algoritmo que ya usa Flask/Werkzeug.
    """
    from werkzeug.security import generate_password_hash
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, time.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_users():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    conn.close()
    return row["c"]


def list_users():
    conn = get_connection()
    rows = conn.execute("SELECT username, role, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_user(username):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def delete_person(person_id):
    conn = get_connection()
    conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()


# --------------------- Utilidades de administración ---------------------

def get_all_people():
    """Como get_people() pero como LISTA (más fácil de imprimir en tabla)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM people ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT username, role, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_events(limit=100):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recognition_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]