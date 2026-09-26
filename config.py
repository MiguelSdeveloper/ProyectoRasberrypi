"""
=====================================================================
 CONFIG.PY -- Configuración central de FaceSec
=====================================================================
"""
import os
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")
PREVIEW_DIR = os.path.join(BASE_DIR, "data", "previews")
MODEL_PATH = os.path.join(BASE_DIR, "data", "trainer.yml")
DB_PATH = os.path.join(BASE_DIR, "data", "facesec.db")

RECORDINGS_PEOPLE_DIR = os.path.join(BASE_DIR, "data", "recordings", "people")
RECORDINGS_GENERAL_DIR = os.path.join(BASE_DIR, "data", "recordings", "general")
GENERAL_SEGMENT_SECONDS = 600
RECORDINGS_ALERTS_DIR = os.path.join(BASE_DIR, "data", "recordings", "alerts")


def _find_cascade_path():
    local_path = os.path.join(BASE_DIR, "data", "haarcascade_frontalface_default.xml")
    if os.path.exists(local_path):
        return local_path
    try:
        import cv2
        candidate = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if os.path.exists(candidate):
            return candidate
    except AttributeError:
        pass
    for path in [
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
    ]:
        if os.path.exists(path):
            return path
    matches = glob.glob("/usr/**/haarcascade_frontalface_default.xml", recursive=True)
    if matches:
        return matches[0]
    raise FileNotFoundError(
        "No se encontró haarcascade_frontalface_default.xml.\n"
        "Descárgalo con:\n"
        "  wget -O data/haarcascade_frontalface_default.xml "
        "https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml"
    )


def _find_eye_cascade_path():
    try:
        import cv2
        candidate = os.path.join(os.path.dirname(CASCADE_PATH), "haarcascade_eye.xml")
        if os.path.exists(candidate):
            return candidate
        candidate = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    matches = glob.glob("/usr/**/haarcascade_eye.xml", recursive=True)
    return matches[0] if matches else None


CASCADE_PATH = _find_cascade_path()
EYE_CASCADE_PATH = _find_eye_cascade_path()

# ---------------------------------------------------------------
# CÁMARAS -- cada una con SU PROPIA orientación (esto es clave: antes
# había una sola variable global CAMERA_ROTATE_180 que afectaba a
# todas las cámaras por igual; ahora cada cámara tiene la suya).
# ---------------------------------------------------------------
CAMERA_RESOLUTION = (320, 240)
CAMERA_FRAMERATE = 15

# --- Cámara USB (PRINCIPAL: reconocimiento facial + registro) ---
CAMERA_USB_INDEX = 0
CAMERA_USB_ROTATE_180 = False
CAMERA_USB_MIRROR = False

# --- Cámara Pi/CSI (SECUNDARIA por defecto) ---
# Está atornillada al revés físicamente, por eso necesita 180°.
CAMERA_PI_ROTATE_180 = True
CAMERA_PI_MIRROR = False
# "recognition" -> (ahora por defecto) hace reconocimiento facial
#                   real también en esta cámara -- las 2 cámaras
#                   identifican personas de forma independiente.
# "motion"       -> solo detecta movimiento, sin identidad (más
#                   liviano; disponible si alguna vez hace falta
#                   bajar la carga de la Pi 3B+).
CAMERA_PI_MODE = "recognition"

# --- Cámara WiFi (desactivada por ahora, no está conectada) ---
CAMERA_WIFI_ENABLED = False
CAMERA_WIFI_URL = ""
CAMERA_WIFI_ROTATE_180 = False
CAMERA_WIFI_MIRROR = False

MOTION_MIN_AREA = 1500

# ---------------------------------------------------------------
# DETECCIÓN DE ROSTROS (Haar Cascade)
# ---------------------------------------------------------------
FACE_DETECTION_SCALE_FACTOR = 1.2
FACE_DETECTION_MIN_NEIGHBORS = 6
FACE_DETECTION_MIN_SIZE = (40, 40)

# ---------------------------------------------------------------
# RECONOCIMIENTO (LBPH)
# ---------------------------------------------------------------
RECOGNITION_CONFIDENCE_THRESHOLD = 150

# Imprime en la terminal el detalle de cada predicción (ID, distancia,
# umbral, resultado). Útil para calibrar RECOGNITION_CONFIDENCE_THRESHOLD.
RECOGNITION_DEBUG = True

# ---------------------------------------------------------------
# GRABACIÓN AUTOMÁTICA
# ---------------------------------------------------------------
PERSON_GRACE_SECONDS = 2       # margen de tolerancia por persona conocida
ALERT_RESUME_WINDOW_SECONDS = 60
CAPTURE_SAMPLE_TARGET = 20
CAPTURE_MIN_INTERVAL = 0.35    # segundos mínimos entre muestras (evita fotos casi idénticas)

RECORD_PEOPLE_ENABLED = True
RECORD_GENERAL_ENABLED = True
RECORD_ALERTS_ENABLED = True

# ---------------------------------------------------------------
# WEB / AUTENTICACIÓN
# ---------------------------------------------------------------
FLASK_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "cambia-esta-clave-en-produccion")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")