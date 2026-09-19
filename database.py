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

  people                  -> personas que la CÁMARA reconoce
  recognition_events       -> historial de cada vez que se reconoció a alguien
  users                     -> quién puede ENTRAR AL PANEL WEB (login)
"""
import sqlite3
import time

import config


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id   INTEGER PRIMARY KEY,
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
            camera_source  TEXT NOT NULL,
            start_time     TEXT NOT NULL,
            end_time       TEXT,
            video_path     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username       TEXT PRIMARY KEY,
            password_hash  TEXT NOT NULL,
            role           TEXT NOT NULL DEFAULT 'viewer',
            created_at     TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_person(person_id, name, role):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO people (id, name, role) VALUES (?, ?, ?)",
        (person_id, name, role),
    )
    conn.commit()
    conn.close()


def get_people():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM people").fetchall()
    conn.close()
    return {row["id"]: {"name": row["name"], "role": row["role"]} for row in rows}


def next_person_id():
    conn = get_connection()
    row = conn.execute("SELECT MAX(id) AS max_id FROM people").fetchone()
    conn.close()
    return (row["max_id"] or 0) + 1


def log_recognition_start(person_id, person_name, person_role, camera_source):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO recognition_events
           (person_id, person_name, person_role, camera_source, start_time)
           VALUES (?, ?, ?, ?, ?)""",
        (person_id, person_name, person_role, camera_source,
         time.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def log_recognition_end(event_id, video_path):
    conn = get_connection()
    conn.execute(
        "UPDATE recognition_events SET end_time = ?, video_path = ? WHERE id = ?",
        (time.strftime("%Y-%m-%d %H:%M:%S"), video_path, event_id),
    )
    conn.commit()
    conn.close()


def get_recent_events(limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recognition_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_user(username, password, role="viewer"):
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
