"""
=====================================================================
 CAMERA_WORKER.PY -- Cámara grabando SIEMPRE, con 2 modos posibles
=====================================================================
Cada CameraWorker corre en su propio hilo de segundo plano, lee
frames sin parar, y los procesa según su "modo":

  mode="recognition" -> detecta y RECONOCE caras (LBPH). Lo usa la
                         cámara principal (Pi/USB).
  mode="motion"       -> solo detecta MOVIMIENTO, sin intentar saber
                         quién es. Lo usa la cámara WiFi -- así no
                         corremos reconocimiento facial en 2 cámaras
                         a la vez (muy pesado para una Pi 3B+), y
                         cada cámara cumple un rol distinto.

RECONEXIÓN AUTOMÁTICA: si la cámara no está disponible al arrancar
(por ejemplo la WiFi está apagada o mal configurada), el worker NO
detiene el programa -- se queda reintentando conectar cada 5
segundos en segundo plano, y expone self.connected para que la web
pueda mostrar "SIN SEÑAL" mientras tanto.
"""
import threading
import time

import cv2
import numpy as np

import config
from camera import CameraStream
from recorder import PersonRecorder, ContinuousRecorder, AlertRecorder


class CameraWorker(threading.Thread):
    def __init__(self, camera_source, mode="recognition", engine=None,
                 backend=None, url=None, on_alert=None):
        super().__init__(daemon=True)
        self.camera_source = camera_source
        self.mode = mode
        self.engine = engine
        self._backend = backend
        self._url = url

        self.camera = None
        self.connected = False

        self.general_recorder = ContinuousRecorder(camera_source)

        if mode == "recognition":
            self.person_recorder = PersonRecorder(camera_source)
            self.alert_recorder = AlertRecorder(
                camera_source, on_alert=on_alert,
                trigger_label="Desconocido", alert_prefix="ALERTA",
            )
            self._processor = engine
        elif mode == "motion":
            from motion import MotionDetector
            self.person_recorder = None
            self.alert_recorder = AlertRecorder(
                camera_source, on_alert=on_alert,
                trigger_label="Movimiento", alert_prefix="MOVIMIENTO",
            )
            self._processor = MotionDetector()
        else:
            raise ValueError(f"Modo de cámara desconocido: {mode!r}")

        self._lock = threading.Lock()
        self._latest_raw_frame = None
        self._latest_display_frame = None
        self._running = False

    def run(self):
        self._running = True
        delay = 1.0 / config.CAMERA_FRAMERATE

        while self._running:
            if self.camera is None:
                try:
                    self.camera = CameraStream(backend=self._backend, url=self._url)
                    self.camera.start()
                    self.connected = True
                    print(f"[{self.camera_source}] Cámara conectada.")
                except Exception as e:
                    self.connected = False
                    print(f"[{self.camera_source}] Sin señal ({e}). Reintentando en 5s...")
                    time.sleep(5)
                    continue

            try:
                raw_frame = self.camera.read_frame()
            except Exception as e:
                print(f"[{self.camera_source}] Se perdió la señal ({e}).")
                self.connected = False
                try:
                    self.camera.stop()
                except Exception:
                    pass
                self.camera = None
                time.sleep(2)
                continue

            with self._lock:
                self._latest_raw_frame = raw_frame.copy()

            display_frame, results = self._processor.process_frame(raw_frame)

            if self.mode == "recognition" and config.RECORD_PEOPLE_ENABLED and self.person_recorder:
                self.person_recorder.update(display_frame, results)
            if config.RECORD_ALERTS_ENABLED:
                self.alert_recorder.update(display_frame, results)
            if config.RECORD_GENERAL_ENABLED:
                self.general_recorder.write(display_frame)

            with self._lock:
                self._latest_display_frame = display_frame

            time.sleep(delay)

    def get_display_jpeg(self):
        if not self.connected:
            return None
        with self._lock:
            frame = self._latest_display_frame
        if frame is None:
            return None
        ok, buffer = cv2.imencode(".jpg", frame)
        return buffer.tobytes() if ok else None

    def get_raw_frame(self):
        with self._lock:
            frame = self._latest_raw_frame
        return frame.copy() if frame is not None else None

    def stop(self):
        self._running = False
        self.general_recorder.stop()
        if self.camera is not None:
            self.camera.stop()


def no_signal_jpeg(width=320, height=240):
    """Genera una imagen 'SIN SEÑAL' para mostrar cuando una cámara
    no está conectada (o no existe/está deshabilitada)."""
    img = np.zeros((height, width, 3), dtype="uint8")
    cv2.putText(img, "SIN SENAL", (int(width * 0.12), height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 200), 2)
    ok, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes() if ok else b""