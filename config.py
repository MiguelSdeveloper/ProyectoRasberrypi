"""
=====================================================================
 CONFIG.PY -- Configuración central de FaceSec
=====================================================================
Toda la configuración del sistema vive aquí. Cambia valores AQUÍ,
no en los demás archivos.
"""
import os
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")
MODEL_PATH = os.path.join(BASE_DIR, "data", "trainer.yml")
DB_PATH = os.path.join(BASE_DIR, "data", "facesec.db")
LABELS_PATH = os.path.join(BASE_DIR, "data", "labels.json")  # ya no se usa, solo compatibilidad

# ---------------------------------------------------------------
# GRABACIÓN -- 3 carpetas separadas, con 3 propósitos distintos:
# ---------------------------------------------------------------
RECORDINGS_PEOPLE_DIR = os.path.join(BASE_DIR, "data", "recordings", "people")
RECORDINGS_GENERAL_DIR = os.path.join(BASE_DIR, "data", "recordings", "general")
GENERAL_SEGMENT_SECONDS = 600  # 10 minutos por archivo
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
    known_paths = [
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
    ]
    for path in known_paths:
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
# CÁMARA PRINCIPAL
# ---------------------------------------------------------------
CAMERA_RESOLUTION = (320, 240)
CAMERA_FRAMERATE = 15
CAMERA_MIRROR = True
CAMERA_ROTATE_180 = True

CAMERA_BACKEND = "auto"
CAMERA_USB_INDEX = 0
CAMERA_IP_URL = ""

CAMERA_WIFI_ENABLED = False
CAMERA_WIFI_URL = ""

# ---------------------------------------------------------------
# DETECCIÓN DE ROSTROS (Haar Cascade)
# ---------------------------------------------------------------
FACE_DETECTION_SCALE_FACTOR = 1.2
FACE_DETECTION_MIN_NEIGHBORS = 6
FACE_DETECTION_MIN_SIZE = (60, 60)

# ---------------------------------------------------------------
# RECONOCIMIENTO (LBPH)
# ---------------------------------------------------------------
RECOGNITION_CONFIDENCE_THRESHOLD = 65

# ---------------------------------------------------------------
# GRABACIÓN AUTOMÁTICA
# ---------------------------------------------------------------
RECORDING_GRACE_FRAMES = 15

RECORD_PEOPLE_ENABLED = True
RECORD_GENERAL_ENABLED = True
RECORD_ALERTS_ENABLED = True

# ---------------------------------------------------------------
# WEB / AUTENTICACIÓN
# ---------------------------------------------------------------
FLASK_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "cambia-esta-clave-en-produccion")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
