"""
=====================================================================
 CAMERA.PY -- Envoltorio de cámara con 3 "backends" posibles
=====================================================================
Un "backend" es simplemente DE DÓNDE vienen los frames de video.
Soportamos 3:

  "picamera2" -> el módulo de cámara oficial conectado por cable CSI
  "usb"       -> cualquier webcam USB normal
  "ip"        -> una cámara WiFi que transmite un stream por red

Lo importante para entender: sin importar cuál backend uses, la
CLASE CameraStream siempre expone los mismos 3 métodos:
    .start()       -- enciende la cámara
    .read_frame()  -- te da la imagen más reciente
    .stop()        -- apaga la cámara

Esto se llama una "interfaz común". Gracias a esto, el resto del
programa (recognition_engine.py, app.py) NUNCA necesita saber si
está hablando con la cámara de la Pi o con la WiFi -- para ellos,
ambas se usan exactamente igual. Es lo que nos permite tener 2
cámaras corriendo a la vez sin duplicar código.
"""
import cv2
import config

try:
    from picamera2 import Picamera2
    _HAS_PICAMERA2 = True
except ImportError:
    # En una laptop normal no existe este módulo -- no es un error,
    # simplemente significa "esta backend no está disponible aquí".
    _HAS_PICAMERA2 = False


class CameraStream:
    def __init__(self, resolution=None, framerate=None, backend=None, url=None, usb_index=None):
        """
        Todos los parámetros son OPCIONALES: si no los pasas, se usan
        los valores de config.py. Esto nos permite crear la cámara
        "principal" con CameraStream() a secas, y una segunda cámara
        WiFi con CameraStream(backend="ip", url="http://...").
        """
        self.resolution = resolution or config.CAMERA_RESOLUTION
        self.framerate = framerate or config.CAMERA_FRAMERATE
        self._backend = backend or self._resolve_default_backend()
        self._url = url or config.CAMERA_IP_URL
        self._usb_index = usb_index if usb_index is not None else config.CAMERA_USB_INDEX

        if self._backend == "picamera2":
            if not _HAS_PICAMERA2:
                raise RuntimeError("picamera2 no está instalado en este sistema.")
            self.picam2 = Picamera2()
            video_config = self.picam2.create_video_configuration(
                main={"size": self.resolution, "format": "RGB888"},
                controls={"FrameRate": self.framerate},
            )
            self.picam2.configure(video_config)

        elif self._backend == "usb":
            self.cap = cv2.VideoCapture(self._usb_index)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            if not self.cap.isOpened():
                raise RuntimeError(f"No se pudo abrir la webcam USB (índice {self._usb_index}).")

        elif self._backend == "ip":
            if not self._url:
                raise RuntimeError("Backend 'ip' pero no se dio ninguna URL de cámara.")
            self.cap = cv2.VideoCapture(self._url)
            if not self.cap.isOpened():
                raise RuntimeError(f"No se pudo conectar a la cámara IP: {self._url}")

        else:
            raise ValueError(f"Backend de cámara desconocido: {self._backend!r}")

    @staticmethod
    def _resolve_default_backend():
        choice = config.CAMERA_BACKEND
        if choice == "auto":
            return "picamera2" if _HAS_PICAMERA2 else "usb"
        return choice

    def start(self):
        if self._backend == "picamera2":
            self.picam2.start()
        return self

    def read_frame(self):
        if self._backend == "picamera2":
            frame = self.picam2.capture_array()
        else:
            ok, frame = self.cap.read()
            if not ok:
                raise RuntimeError(f"No se pudo leer un frame (backend={self._backend}).")

        # Todos los backends terminan entregando el frame en orden BGR:
        # cv2.VideoCapture nativamente, y Picamera2 por el quirk conocido
        # de su formato "RGB888" (a pesar del nombre, entrega BGR).
        if config.CAMERA_MIRROR:
            frame = cv2.flip(frame, 1)
        return frame

    def stop(self):
        if self._backend == "picamera2":
            self.picam2.stop()
            self.picam2.close()
        else:
            self.cap.release()
