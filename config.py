"""
Configuración central de FaceSec.
Modifica estos valores según tu hardware y preferencias.
"""
import os
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")
MODEL_PATH = os.path.join(BASE_DIR, "data", "trainer.yml")
LABELS_PATH = os.path.join(BASE_DIR, "data", "labels.json")


def _find_cascade_path():
    """
    Busca haarcascade_frontalface_default.xml sin depender de cv2.data
    (algunos builds de python3-opencv en Raspberry Pi OS no lo exponen).
    """
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
        "No se encontró haarcascade_frontalface_default.xml en el sistema.\n"
        "Ejecuta en la Pi: find / -name 'haarcascade_frontalface_default.xml' 2>/dev/null\n"
        "y define CASCADE_PATH manualmente en config.py con la ruta que te devuelva."
    )


CASCADE_PATH = os.path.join(BASE_DIR, "data", "haarcascade_frontalface_default.xml")

# --- Cámara ---
# Resolución reducida a propósito: la Pi 3B+ tiene menos CPU que la Pi 4
# en la que se basaba el proyecto original.
CAMERA_RESOLUTION = (320, 240)
CAMERA_FRAMERATE = 15
CAMERA_MIRROR = True
# --- Detección de rostros (Haar Cascade) ---
FACE_DETECTION_SCALE_FACTOR = 1.2
FACE_DETECTION_MIN_NEIGHBORS = 6
FACE_DETECTION_MIN_SIZE = (60, 60)

# --- Reconocimiento (LBPH) ---
# Cuanto más BAJO, más estricto (más difícil que reconozca a alguien).
RECOGNITION_CONFIDENCE_THRESHOLD = 65

# --- Web / autenticación ---
FLASK_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "cambia-esta-clave-en-produccion")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# Si defines ADMIN_PASSWORD_HASH como variable de entorno, se usa esa.
# Si no, la contraseña por defecto es "admin" (¡cámbiala!).
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
