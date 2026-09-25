"""
=====================================================================
 WEBAPP/APP.PY -- Panel de control Flask con grabación 24/7
=====================================================================
Resumen de esta versión (auditoría completa):

  - CÁMARA USB = principal para reconocimiento Y para registrar
    personas. CÁMARA PI = secundaria (por defecto solo detecta
    movimiento, configurable a reconocimiento en config.py). WIFI =
    desactivada (CAMERA_WIFI_ENABLED = False).

  - Registro de personas: el ID se RESERVA al empezar, pero la
    persona NO se guarda en la base de datos hasta que la captura
    TERMINA con éxito -- evita "personas fantasma" sin fotos.

  - Logs separados: los ADMIN ven todo (login, usuarios, entrenamiento,
    eliminaciones); los VIEWER solo ven eventos de vigilancia
    (reconocimientos, alertas) -- nunca acciones administrativas.
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

if config.FLASK_SECRET_KEY == "cambia-esta-clave-en-produccion":
    print("=" * 60)
    print(" AVISO DE SEGURIDAD: estás usando la clave secreta de Flask")
    print(" por defecto. Define la variable de entorno APP_SECRET_KEY")
    print(" antes de exponer este sistema fuera de tu red local.")
    print("=" * 60)

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

# ---------------------------------------------------------------
# 2 logs SEPARADOS por diseño (no solo por CSS/HTML):
#   internal_log      -> SOLO admin (login, usuarios, entrenamiento...)
#   surveillance_log   -> admin Y viewer (alertas de cámara)
# El dashboard decide cuál(es) mostrar según session['role'].
# ---------------------------------------------------------------
internal_log = []
surveillance_log = []
MAX_LOG = 40
log_lock = threading.Lock()


def log_internal(message, level="info"):
    with log_lock:
        internal_log.insert(0, {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message, "level": level,
        })
        del internal_log[MAX_LOG:]


def log_surveillance(message, level="info"):
    with log_lock:
        surveillance_log.insert(0, {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message, "level": level,
        })
        del surveillance_log[MAX_LOG:]


def on_alert(message):
    log_surveillance(f"⚠ {message}", "danger")


# ---------------------------------------------------------------
# 3 cámaras: USB (principal, reconocimiento), Pi (secundaria, modo
# configurable), WiFi (desactivada salvo que la actives en config.py).
# Cada una con SU orientación propia -- nunca una regla global.
# ---------------------------------------------------------------
usb_worker = CameraWorker(
    "usb", mode="recognition", engine=engine, backend="usb",
    rotate_180=config.CAMERA_USB_ROTATE_180, mirror=config.CAMERA_USB_MIRROR,
    on_alert=on_alert,
)
usb_worker.start()

pi_worker = CameraWorker(
    "pi", mode=config.CAMERA_PI_MODE, engine=engine, backend="picamera2",
    rotate_180=config.CAMERA_PI_ROTATE_180, mirror=config.CAMERA_PI_MIRROR,
    on_alert=on_alert,
)
pi_worker.start()

wifi_worker = None
if config.CAMERA_WIFI_ENABLED and config.CAMERA_WIFI_URL:
    wifi_worker = CameraWorker(
        "wifi", mode="motion", backend="ip", url=config.CAMERA_WIFI_URL,
        rotate_180=config.CAMERA_WIFI_ROTATE_180, mirror=config.CAMERA_WIFI_MIRROR,
        on_alert=on_alert,
    )
    wifi_worker.start()

NO_SIGNAL_JPEG = no_signal_jpeg(*config.CAMERA_RESOLUTION)

training_lock = threading.Lock()

registration_lock = threading.Lock()
registration_state = {
    "active": False, "person_id": None, "name": None, "role": None,
    "id_document": None, "phone": None, "email": None, "notes": None,
    "count": 0, "target": config.CAPTURE_SAMPLE_TARGET, "done": False,
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


# ---------------------------------------------------------------
# AUTENTICACIÓN
# ---------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.get_user(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            session["role"] = user["role"]
            log_internal(f"Inicio de sesión: {username} ({user['role']})", "success")
            return redirect(url_for("dashboard"))
        log_internal(f"Intento de acceso fallido: usuario '{username}'", "warning")
        flash("Credenciales incorrectas")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_internal(f"Cierre de sesión: {session['user']}", "info")
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# GESTIÓN DE USUARIOS DEL PANEL (solo admin)
# ---------------------------------------------------------------

@app.route("/users", methods=["GET", "POST"])
@login_required(role="admin")
def manage_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "viewer")
        if username and password:
            database.add_user(username, password, role)
            log_internal(f"Usuario de panel creado: {username} ({role})", "success")
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
    log_internal(f"Usuario de panel eliminado: {username}", "warning")
    flash(f"Usuario '{username}' eliminado.")
    return redirect(url_for("manage_users"))


# ---------------------------------------------------------------
# GESTIÓN DE PERSONAS RECONOCIDAS (solo admin)
# ---------------------------------------------------------------

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
    # Refresca el motor YA (sin esto, LBPH seguiría reconociendo el ID
    # numérico viejo hasta el próximo reinicio o reentrenamiento).
    engine.reload()
    log_internal(f"Persona eliminada del reconocimiento: ID {person_id}", "warning")
    flash("Persona eliminada. El modelo se recargó -- ya no la reconocerá. "
          "Entrena de nuevo cuando puedas para limpiar sus datos del archivo del modelo.")
    return redirect(url_for("manage_people"))


# ---------------------------------------------------------------
# PANEL PRINCIPAL -- el contenido del log depende del ROL
# ---------------------------------------------------------------

@app.route("/dashboard")
@login_required()
def dashboard():
    role = session.get("role")
    recognition_events = database.get_recent_events(limit=15)

    combined = []
    with log_lock:
        combined.extend(dict(e) for e in surveillance_log)
        if role == "admin":
            combined.extend(dict(e) for e in internal_log)

    for e in recognition_events:
        estado = "en curso" if not e["end_time"] else f"hasta {e['end_time']}"
        nivel = "danger" if e["person_name"] in ("Desconocido", "Movimiento") else "success"
        combined.append({
            "time": e["start_time"],
            "message": f"{e['person_name']}" + (f" ({e['person_role']})" if e['person_role'] else "")
                       + f" -- cámara {e['camera_source']} [{estado}]",
            "level": nivel,
        })
    combined.sort(key=lambda e: e["time"], reverse=True)

    return render_template(
        "dashboard.html",
    )


# ---------------------------------------------------------------
# STREAMING DE VIDEO
# ---------------------------------------------------------------

def gen_stream(worker):
    while True:
        jpeg = worker.get_display_jpeg() if worker is not None else None
        if jpeg is None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + NO_SIGNAL_JPEG + b"\r\n")
            time.sleep(1.0)
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(1.0 / config.CAMERA_FRAMERATE)


@app.route("/video_feed_usb")
@login_required()
def video_feed_usb():
    return Response(gen_stream(usb_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed")
@login_required()
def video_feed():
    return Response(gen_stream(pi_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_wifi")
@login_required()
def video_feed_wifi():
    return Response(gen_stream(wifi_worker), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------
# REGISTRO DE PERSONAS -- EXCLUSIVAMENTE por la cámara USB
# ---------------------------------------------------------------

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

        with registration_lock:
            # Si había una captura anterior sin terminar, limpia sus
            # fotos sueltas antes de empezar una nueva (no se quedaron
            # en la base de datos porque nunca llegamos a confirmarla).
            if registration_state["active"] and not registration_state["done"]:
                old_id = registration_state["person_id"]
                for path in glob.glob(os.path.join(config.DATASET_DIR, f"user.{old_id}.*.jpg")):
                    os.remove(path)

            # El ID se RESERVA, pero la persona NO se guarda en la BD
            # todavía -- eso pasa solo si la captura termina con éxito
            # (ver gen_register_frames). Así no quedan "personas
            # fantasma" sin fotos si alguien cancela a medio camino.
            person_id = database.next_person_id()
            registration_state.update({
                "active": True, "person_id": person_id, "name": name, "role": role,
                "id_document": id_document, "phone": phone, "email": email, "notes": notes,
                "count": 0, "target": config.CAPTURE_SAMPLE_TARGET, "done": False,
            })
        return redirect(url_for("register_capture"))

    return render_template("register.html", sample_target=config.CAPTURE_SAMPLE_TARGET)


@app.route("/register/capture")
@login_required(role="admin")
def register_capture():
    return render_template("register_capture.html", name=registration_state.get("name"))


def gen_register_frames():
    """
    Usa EXCLUSIVAMENTE usb_worker -- nunca abre una segunda conexión
    a la cámara (usb_worker ya la tiene abierta). Si la USB no está
    disponible, muestra "SIN SEÑAL" y NO incrementa el contador de
    muestras (para no confundir "avanzando" con "cámara caída").
    """
    import cv2

    os.makedirs(config.DATASET_DIR, exist_ok=True)
    last_capture = 0.0

    while True:
        with registration_lock:
            if not registration_state["active"]:
                break
            person_id = registration_state["person_id"]
            count = registration_state["count"]
            target = registration_state["target"]

        frame = usb_worker.get_raw_frame()
        if frame is None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + NO_SIGNAL_JPEG + b"\r\n")
            time.sleep(0.5)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = engine.detector.detectMultiScale(
            gray,
            scaleFactor=config.FACE_DETECTION_SCALE_FACTOR,
            minNeighbors=config.FACE_DETECTION_MIN_NEIGHBORS,
            minSize=config.FACE_DETECTION_MIN_SIZE,
        )

        now = time.time()
        can_capture = (now - last_capture) >= config.CAPTURE_MIN_INTERVAL

        for (x, y, w, h) in faces:
            if count < target and can_capture:
                count += 1
                last_capture = now
                face_img = gray[y:y + h, x:x + w]
                filename = os.path.join(config.DATASET_DIR, f"user.{person_id}.{count}.jpg")
                cv2.imwrite(filename, face_img)

                if count == 1:
                    os.makedirs(config.PREVIEW_DIR, exist_ok=True)
                    preview_path = os.path.join(config.PREVIEW_DIR, f"user.{person_id}.jpg")
                    cv2.imwrite(preview_path, frame[y:y + h, x:x + w])
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

        finished_now = False
        with registration_lock:
            registration_state["count"] = count
            if count >= target and not registration_state["done"]:
                registration_state["active"] = False
                registration_state["done"] = True
                finished_now = True
                data = dict(registration_state)

        if finished_now:
            # SOLO AHORA, con la captura ya completa, se guarda la
            # persona en la base de datos -- si nunca se llega aquí,
            # nunca queda un registro huérfano en SQLite.
            database.add_person(
                data["person_id"], data["name"], data["role"],
                data["id_document"], data["phone"], data["email"], data["notes"],
            )
            log_internal(f"Persona registrada: {data['name']} ({data['role']}, ID {data['person_id']})", "success")

        cv2.putText(frame, f"CAMARA USB - CAPTURA DE REGISTRO  Muestras: {count}/{target}",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
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
            "usb_connected": usb_worker.connected,
        }


@app.route("/train", methods=["POST"])
@login_required(role="admin")
def train():
    got_lock = training_lock.acquire(blocking=False)
    if not got_lock:
        flash("Ya hay un entrenamiento en curso, espera a que termine.")
        return redirect(url_for("dashboard"))
    try:
        success = train_model.main()
        if success:
            engine.reload()
            log_internal("Modelo entrenado y recargado correctamente.", "success")
            flash("Modelo entrenado y recargado correctamente.")
        else:
            log_internal("Entrenamiento falló -- se conservó el modelo anterior.", "warning")
            flash("El entrenamiento no se pudo completar (revisa la terminal). El modelo anterior sigue activo.")
    finally:
        training_lock.release()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

