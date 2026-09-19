"""
=====================================================================
 WEBAPP/APP.PY -- Panel de control Flask con 2 cámaras
=====================================================================
Flask es un "microframework" web: básicamente traduce URLs (como
"/dashboard" o "/video_feed") a funciones de Python que corren
cuando alguien visita esa URL desde el navegador. Cada función así
se llama una "ruta" (route).

ARQUITECTURA de este archivo:
  - 1 CameraStream + 1 RecognitionEngine + 1 PersonRecorder para la
    cámara de la Pi ("pi")
  - Si config.CAMERA_WIFI_ENABLED = True, otro juego idéntico de los
    3 para la cámara WiFi ("wifi")
  - Cada cámara tiene su propia ruta de streaming de video
    (/video_feed y /video_feed_wifi)
  - El log de eventos combina: inicios/cierres de sesión (en memoria,
    se pierden al reiniciar) + reconocimientos guardados en la base
    de datos (persisten para siempre)
"""
import os
import sys
import time
import threading
from functools import wraps

import cv2
from flask import Flask, Response, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import database
from camera import CameraStream
from recognition_engine import RecognitionEngine
from recorder import PersonRecorder

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
database.init_db()

# Usuarios del PANEL WEB (login para ver el sistema). Esto es distinto
# de las "personas" que el sistema reconoce por cámara -- una cosa es
# quién puede ENTRAR AL PANEL, otra es a quién la cámara reconoce.
USERS = {
    config.ADMIN_USERNAME: {
        "password_hash": config.ADMIN_PASSWORD_HASH or generate_password_hash("admin"),
        "role": "admin",
    },
    "viewer": {
        "password_hash": generate_password_hash("viewer"),
        "role": "viewer",
    },
}

# ---------------------------------------------------------------
# Un solo "engine" de reconocimiento se puede reusar en ambas
# cámaras (no depende de la cámara, solo procesa imágenes).
# ---------------------------------------------------------------
engine = RecognitionEngine()

# Cada cámara es "perezosa": no se enciende hasta que alguien pide
# /video_feed por primera vez (para no gastar batería/CPU si nadie
# está viendo el panel).
_pi_camera = None
_pi_recorder = PersonRecorder(camera_source="pi")
_pi_lock = threading.Lock()

_wifi_camera = None
_wifi_recorder = PersonRecorder(camera_source="wifi")
_wifi_lock = threading.Lock()

# Log de eventos de LOGIN (en memoria -- se reinicia con el programa).
# Los eventos de RECONOCIMIENTO viven en la base de datos, no aquí.
login_log = []
MAX_LOGIN_LOG = 30


def get_pi_camera():
    global _pi_camera
    with _pi_lock:
        if _pi_camera is None:
            _pi_camera = CameraStream().start()
    return _pi_camera


def get_wifi_camera():
    global _wifi_camera
    with _wifi_lock:
        if _wifi_camera is None:
            _wifi_camera = CameraStream(backend="ip", url=config.CAMERA_WIFI_URL).start()
    return _wifi_camera


def log_login_event(message, level="info"):
    login_log.insert(0, {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "level": level,
    })
    del login_log[MAX_LOGIN_LOG:]


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return "Acceso denegado", 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------
# RUTAS DE AUTENTICACIÓN
# ---------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            session["role"] = user["role"]
            log_login_event(f"Inicio de sesión: {username} ({user['role']})", "success")
            return redirect(url_for("dashboard"))
        log_login_event(f"Intento de acceso fallido: usuario '{username}'", "warning")
        flash("Credenciales incorrectas")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_login_event(f"Cierre de sesión: {session['user']}", "info")
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# PANEL PRINCIPAL
# ---------------------------------------------------------------

@app.route("/dashboard")
@login_required()
def dashboard():
    # Combinamos: eventos de login (en memoria) + eventos de
    # reconocimiento (de la base de datos), y los mezclamos
    # ordenados por hora, más reciente primero.
    recognition_events = database.get_recent_events(limit=15)
    combined = []
    for e in login_log:
        combined.append({"time": e["time"], "message": e["message"], "level": e["level"]})
    for e in recognition_events:
        estado = "en curso" if not e["end_time"] else f"hasta {e['end_time']}"
        combined.append({
            "time": e["start_time"],
            "message": f"Reconocido: {e['person_name']} ({e['person_role']}) "
                       f"cámara={e['camera_source']} [{estado}]",
            "level": "success",
        })
    combined.sort(key=lambda e: e["time"], reverse=True)

    return render_template(
        "dashboard.html",
        role=session.get("role"),
        events=combined[:15],
        model_ready=engine.ready,
        wifi_enabled=config.CAMERA_WIFI_ENABLED,
    )


# ---------------------------------------------------------------
# STREAMING DE VIDEO
# ---------------------------------------------------------------
# gen_frames_for() es una "función generadora" (usa 'yield' en vez de
# 'return'): en vez de devolver UN resultado y terminar, va
# entregando frames UNO POR UNO, indefinidamente, mientras el
# navegador siga conectado. Esto es lo que permite un video "en vivo"
# sobre HTTP normal (se llama streaming MJPEG).

def gen_frames_for(camera, recorder):
    while True:
        frame = camera.read_frame()
        frame, results = engine.process_frame(frame)
        recorder.update(frame, results)  # graba (o no) según lo que se ve

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")


@app.route("/video_feed")
@login_required()
def video_feed():
    cam = get_pi_camera()
    return Response(gen_frames_for(cam, _pi_recorder),
                     mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_wifi")
@login_required()
def video_feed_wifi():
    if not config.CAMERA_WIFI_ENABLED:
        return "Cámara WiFi deshabilitada en config.py", 404
    cam = get_wifi_camera()
    return Response(gen_frames_for(cam, _wifi_recorder),
                     mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
