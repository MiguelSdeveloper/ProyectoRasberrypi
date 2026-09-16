"""
FaceSec Web — panel de control con autenticación, transmisión en vivo
con reconocimiento facial, y bitácora de eventos de acceso.

Uso:
    python webapp/app.py
Luego abre: http://<ip-de-tu-pi>:8080
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
from camera import CameraStream
from recognition_engine import RecognitionEngine

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# Usuarios de ejemplo. Cambia las contraseñas antes de usar esto en serio.
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

engine = RecognitionEngine()
camera = None
camera_lock = threading.Lock()

access_log = []
MAX_LOG = 50


def get_camera():
    global camera
    with camera_lock:
        if camera is None:
            camera = CameraStream().start()
    return camera


def log_event(message, level="info"):
    access_log.insert(0, {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "level": level,
    })
    del access_log[MAX_LOG:]


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


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            session["role"] = user["role"]
            log_event(f"Inicio de sesión: {username} ({user['role']})", "success")
            return redirect(url_for("dashboard"))
        log_event(f"Intento de acceso fallido: usuario '{username}'", "warning")
        flash("Credenciales incorrectas")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_event(f"Cierre de sesión: {session['user']}", "info")
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required()
def dashboard():
    return render_template(
        "dashboard.html",
        role=session.get("role"),
        events=access_log[:15],
        model_ready=engine.ready,
    )


def gen_frames():
    cam = get_camera()
    while True:
        frame = cam.read_frame()
        frame, _ = engine.process_frame(frame)
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")


@app.route("/video_feed")
@login_required()
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/events")
@login_required()
def api_events():
    return {"events": access_log[:15]}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
