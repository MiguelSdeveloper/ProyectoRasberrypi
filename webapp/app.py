"""
=====================================================================
 WEBAPP/APP.PY -- Panel de control Flask con 2 cámaras
=====================================================================
- Credenciales del panel viven en la tabla "users" de la BD, no en
  este archivo.
- La primera vez que corre, se crea un admin con usuario/contraseña
  GENERADOS AL AZAR, impresos UNA VEZ en la terminal.
- El registro de personas se puede hacer desde la web en /register.
"""
import os
import sys
import time
import secrets
import threading
from functools import wraps

import cv2
from flask import Flask, Response, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import database
import train_model
from camera import CameraStream
from recognition_engine import RecognitionEngine
from recorder import PersonRecorder

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
database.init_db()


def bootstrap_admin():
    if database.count_users() > 0:
        return
    username = os.environ.get("ADMIN_USERNAME") or f"admin_{secrets.token_hex(2)}"
    password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
    database.add_user(username, password, role="admin")
    print("=" * 60)
    print(" USUARIO ADMIN CREADO (primera vez que corre el sistema)")
    print(f"   Usuario:    {username}")
    print(f"   Contraseña: {password}")
    print(" Guárdalo ahora -- no se vuelve a mostrar en ningún lado.")
    print("=" * 60)


bootstrap_admin()

engine = RecognitionEngine()

_pi_camera = None
_pi_recorder = PersonRecorder(camera_source="pi")
_pi_lock = threading.Lock()

_wifi_camera = None
_wifi_recorder = PersonRecorder(camera_source="wifi")
_wifi_lock = threading.Lock()

login_log = []
MAX_LOGIN_LOG = 30

registration_lock = threading.Lock()
registration_state = {
    "active": False, "person_id": None, "name": None,
    "role": None, "count": 0, "target": 40, "done": False,
}


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


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = database.get_user(username)
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


@app.route("/users", methods=["GET", "POST"])
@login_required(role="admin")
def manage_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "viewer")
        if username and password:
            database.add_user(username, password, role)
            log_login_event(f"Usuario de panel creado: {username} ({role})", "success")
            flash(f"Usuario '{username}' creado.")
        else:
            flash("Usuario y contraseña son obligatorios.")
    return render_template("users.html", users=database.list_users())


@app.route("/dashboard")
@login_required()
def dashboard():
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


def gen_frames_for(camera, recorder):
    while True:
        frame = camera.read_frame()
        frame, results = engine.process_frame(frame)
        recorder.update(frame, results)

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


@app.route("/register", methods=["GET", "POST"])
@login_required(role="admin")
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "Invitado")
        if not name:
            flash("El nombre es obligatorio.")
            return redirect(url_for("register"))

        person_id = database.next_person_id()
        database.add_person(person_id, name, role)

        with registration_lock:
            registration_state.update({
                "active": True, "person_id": person_id, "name": name,
                "role": role, "count": 0, "target": 40, "done": False,
            })
        return redirect(url_for("register_capture"))

    return render_template("register.html")


@app.route("/register/capture")
@login_required(role="admin")
def register_capture():
    return render_template("register_capture.html", name=registration_state.get("name"))


def gen_register_frames():
    cam = get_pi_camera()
    os.makedirs(config.DATASET_DIR, exist_ok=True)

    while True:
        with registration_lock:
            if not registration_state["active"]:
                break
            person_id = registration_state["person_id"]
            count = registration_state["count"]
            target = registration_state["target"]

        frame = cam.read_frame()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = engine.detector.detectMultiScale(
            gray,
            scaleFactor=config.FACE_DETECTION_SCALE_FACTOR,
            minNeighbors=config.FACE_DETECTION_MIN_NEIGHBORS,
            minSize=config.FACE_DETECTION_MIN_SIZE,
        )
        for (x, y, w, h) in faces:
            if count < target:
                count += 1
                face_img = gray[y:y + h, x:x + w]
                filename = os.path.join(config.DATASET_DIR, f"user.{person_id}.{count}.jpg")
                cv2.imwrite(filename, face_img)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

        with registration_lock:
            registration_state["count"] = count
            if count >= target:
                registration_state["active"] = False
                registration_state["done"] = True

        cv2.putText(frame, f"Muestras: {count}/{target}", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")


@app.route("/register_feed")
@login_required(role="admin")
def register_feed():
    return Response(gen_register_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/register/status")
@login_required(role="admin")
def register_status():
    with registration_lock:
        return {
            "count": registration_state["count"],
            "target": registration_state["target"],
            "done": registration_state["done"],
        }


@app.route("/train", methods=["POST"])
@login_required(role="admin")
def train():
    train_model.main()
    engine.reload()
    flash("Modelo entrenado y recargado correctamente.")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
