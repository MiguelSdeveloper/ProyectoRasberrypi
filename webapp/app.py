"""
=====================================================================
 WEBAPP/APP.PY -- Panel de control Flask con grabación 24/7
=====================================================================
"""
import os
import sys
import time
import glob
import secrets
import threading
from functools import wraps

from flask import Flask, Response, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import database
import train_model
from recognition_engine import RecognitionEngine
from camera_worker import CameraWorker, no_signal_jpeg

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

event_log = []
MAX_EVENT_LOG = 40
event_log_lock = threading.Lock()


def log_event(message, level="info"):
    with event_log_lock:
        event_log.insert(0, {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
            "level": level,
        })
        del event_log[MAX_EVENT_LOG:]


def on_alert(message):
    log_event(f"⚠ ALERTA: {message}", "danger")


# 3 cámaras simultáneas, cada una intentando conectar por su cuenta.
# La que no esté físicamente disponible se queda reintentando en
# segundo plano y se muestra como "SIN SEÑAL" -- no rompe nada.
pi_worker = CameraWorker("pi", mode="recognition", engine=engine, backend="picamera2", on_alert=on_alert)
pi_worker.start()

usb_worker = CameraWorker("usb", mode="recognition", engine=engine, backend="usb", on_alert=on_alert)
usb_worker.start()

wifi_worker = None
if config.CAMERA_WIFI_ENABLED and config.CAMERA_WIFI_URL:
    wifi_worker = CameraWorker("wifi", mode="motion", backend="ip", url=config.CAMERA_WIFI_URL, on_alert=on_alert)
    wifi_worker.start()

NO_SIGNAL_JPEG = no_signal_jpeg(*config.CAMERA_RESOLUTION)

training_lock = threading.Lock()

registration_lock = threading.Lock()
registration_state = {
    "active": False, "person_id": None, "name": None,
    "role": None, "count": 0, "target": config.CAPTURE_SAMPLE_TARGET, "done": False,
}


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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.get_user(username)
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


@app.route("/users", methods=["GET", "POST"])
@login_required(role="admin")
def manage_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "viewer")
        if username and password:
            database.add_user(username, password, role)
            log_event(f"Usuario de panel creado: {username} ({role})", "success")
            flash(f"Usuario '{username}' creado.")
        else:
            flash("Usuario y contraseña son obligatorios.")
    return render_template("users.html", users=database.list_users())


@app.route("/users/delete/<username>", methods=["POST"])
@login_required(role="admin")
def delete_user_route(username):
    if username == session.get("user"):
        flash("No puedes eliminar tu propio usuario mientras tienes sesión iniciada.")
        return redirect(url_for("manage_users"))
    database.delete_user(username)
    log_event(f"Usuario de panel eliminado: {username}", "warning")
    flash(f"Usuario '{username}' eliminado.")
    return redirect(url_for("manage_users"))


@app.route("/people")
@login_required(role="admin")
def manage_people():
    return render_template("people.html", people=database.get_people())


@app.route("/people/delete/<int:person_id>", methods=["POST"])
@login_required(role="admin")
def delete_person_route(person_id):
    database.delete_person(person_id)
    for path in glob.glob(os.path.join(config.DATASET_DIR, f"user.{person_id}.*.jpg")):
        os.remove(path)
    log_event(f"Persona eliminada del reconocimiento: ID {person_id}", "warning")
    flash("Persona eliminada. Recuerda entrenar el modelo de nuevo.")
    return redirect(url_for("manage_people"))


@app.route("/dashboard")
@login_required()
def dashboard():
    recognition_events = database.get_recent_events(limit=15)
    combined = []
    with event_log_lock:
        for e in event_log:
            combined.append(dict(e))
    for e in recognition_events:
        estado = "en curso" if not e["end_time"] else f"hasta {e['end_time']}"
        nivel = "danger" if e["person_name"] in ("Desconocido", "Movimiento") else "success"
        combined.append({
            "time": e["start_time"],
            "message": f"Reconocido: {e['person_name']} ({e['person_role'] or '-'}) "
                       f"cámara={e['camera_source']} [{estado}]",
            "level": nivel,
        })
    combined.sort(key=lambda e: e["time"], reverse=True)

    return render_template(
        "dashboard.html",
        role=session.get("role"),
        events=combined[:20],
        model_ready=engine.ready,
        pi_connected=pi_worker.connected,
        usb_connected=usb_worker.connected,
        wifi_connected=(wifi_worker.connected if wifi_worker is not None else False),
    )


def gen_stream(worker):
    while True:
        jpeg = worker.get_display_jpeg() if worker is not None else None
        if jpeg is None:
            jpeg = NO_SIGNAL_JPEG
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(1.0)
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(1.0 / config.CAMERA_FRAMERATE)


@app.route("/video_feed")
@login_required()
def video_feed():
    return Response(gen_stream(pi_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_usb")
@login_required()
def video_feed_usb():
    return Response(gen_stream(usb_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_wifi")
@login_required()
def video_feed_wifi():
    return Response(gen_stream(wifi_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/register", methods=["GET", "POST"])
@login_required(role="admin")
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "Invitado")
        id_document = request.form.get("id_document", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        email = request.form.get("email", "").strip() or None
        notes = request.form.get("notes", "").strip() or None

        if not name:
            flash("El nombre es obligatorio.")
            return redirect(url_for("register"))

        person_id = database.next_person_id()
        database.add_person(person_id, name, role, id_document, phone, email, notes)

        with registration_lock:
            registration_state.update({
                "active": True, "person_id": person_id, "name": name,
                "role": role, "count": 0,
                "target": config.CAPTURE_SAMPLE_TARGET, "done": False,
            })
        return redirect(url_for("register_capture"))

    return render_template("register.html", sample_target=config.CAPTURE_SAMPLE_TARGET)


@app.route("/register/capture")
@login_required(role="admin")
def register_capture():
    return render_template("register_capture.html", name=registration_state.get("name"))


def gen_register_frames():
    import cv2
    os.makedirs(config.DATASET_DIR, exist_ok=True)

    while True:
        with registration_lock:
            if not registration_state["active"]:
                break
            person_id = registration_state["person_id"]
            count = registration_state["count"]
            target = registration_state["target"]

        frame = pi_worker.get_raw_frame()
        if frame is None:
            time.sleep(0.05)
            continue

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

                if count == 1:
                    os.makedirs(config.PREVIEW_DIR, exist_ok=True)
                    preview_path = os.path.join(config.PREVIEW_DIR, f"user.{person_id}.jpg")
                    cv2.imwrite(preview_path, frame[y:y + h, x:x + w])
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
        time.sleep(1.0 / config.CAMERA_FRAMERATE)


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
    got_lock = training_lock.acquire(blocking=False)
    if not got_lock:
        flash("Ya hay un entrenamiento en curso, espera a que termine.")
        return redirect(url_for("dashboard"))
    try:
        train_model.main()
        engine.reload()
        flash("Modelo entrenado y recargado correctamente.")
    finally:
        training_lock.release()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)