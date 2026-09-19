"""
=====================================================================
 CONFIG.PY -- Configuración central de FaceSec
=====================================================================
Este archivo NO tiene lógica "activa" (no hace nada por sí solo).
Es solo un lugar único donde guardamos números y rutas que el resto
del programa necesita. La idea pedagógica: si mañana quieres cambiar
la resolución de cámara, o el umbral de reconocimiento, lo cambias
AQUÍ UNA VEZ, y automáticamente afecta a todo el proyecto (porque
todos los demás archivos hacen "import config" y leen estos valores).

Esto se llama "centralizar la configuración" y es una buena práctica:
evita tener el mismo número mágico copiado y pegado en 5 archivos
distintos.
"""
import os
import glob

# BASE_DIR = la carpeta donde vive este mismo archivo config.py.
# Lo calculamos así (en vez de escribirlo a mano) para que el proyecto
# funcione sin importar en qué computadora o carpeta lo pongas.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")        # fotos de caras para entrenar
MODEL_PATH = os.path.join(BASE_DIR, "data", "trainer.yml")     # el modelo LBPH ya entrenado
RECORDINGS_DIR = os.path.join(BASE_DIR, "data", "recordings")  # videos grabados
DB_PATH = os.path.join(BASE_DIR, "data", "facesec.db")         # base de datos SQLite

# Se mantiene solo por compatibilidad con versiones anteriores del
# proyecto (ya NO se usa para guardar nombres; ahora eso vive en la
# base de datos, ver database.py).
LABELS_PATH = os.path.join(BASE_DIR, "data", "labels.json")


def _find_cascade_path():
    """
    Busca haarcascade_frontalface_default.xml sin depender de cv2.data
    (algunos builds de python3-opencv en Raspberry Pi OS no lo exponen).

    Prueba varias ubicaciones EN ORDEN y usa la primera que exista.
    """
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


CASCADE_PATH = _find_cascade_path()

# ---------------------------------------------------------------
# CÁMARA PRINCIPAL (la que va conectada físicamente a la Pi:
# módulo CSI, o una webcam USB)
# ---------------------------------------------------------------
CAMERA_RESOLUTION = (320, 240)   # ancho, alto -- reducido por el rendimiento de la Pi 3B+
CAMERA_FRAMERATE = 15
CAMERA_MIRROR = True             # True = espejo horizontal (como selfie)

# "auto" -> usa Picamera2 si está disponible, si no cae a webcam USB
# "picamera2" -> fuerza el módulo CSI
# "usb"       -> fuerza una webcam USB (índice CAMERA_USB_INDEX)
# "ip"        -> cámara WiFi (usa CAMERA_IP_URL)
CAMERA_BACKEND = "auto"
CAMERA_USB_INDEX = 0
CAMERA_IP_URL = ""

# ---------------------------------------------------------------
# SEGUNDA CÁMARA (tu cámara WiFi). Es completamente opcional:
# si CAMERA_WIFI_ENABLED = False, el sistema funciona con una sola
# cámara igual que antes.
# ---------------------------------------------------------------
CAMERA_WIFI_ENABLED = False
# URL del stream de tu cámara WiFi. Depende del modelo:
#   ESP32-CAM típico:      "http://192.168.0.50:81/stream"
#   Cámara IP con RTSP:    "rtsp://usuario:clave@192.168.0.51:554/stream1"
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
# Cuanto más BAJO, más estricto (más difícil que reconozca a alguien).
RECOGNITION_CONFIDENCE_THRESHOLD = 65

# ---------------------------------------------------------------
# GRABACIÓN AUTOMÁTICA
# ---------------------------------------------------------------
# Cuántos frames seguidos SIN ver a la persona hay que esperar antes
# de cortar la grabación (evita que un parpadeo/mala detección corte
# el video en pedacitos). A 15 fps, 15 frames ~= 1 segundo.
RECORDING_GRACE_FRAMES = 15

# ---------------------------------------------------------------
# WEB / AUTENTICACIÓN
# ---------------------------------------------------------------
FLASK_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "cambia-esta-clave-en-produccion")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
