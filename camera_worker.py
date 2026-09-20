"""
=====================================================================
 CAMERA_WORKER.PY -- Mantiene la cámara encendida y grabando SIEMPRE
=====================================================================
CONCEPTO CLAVE: antes, la cámara solo se encendía cuando alguien
abría la página web (/video_feed). Eso significa que si nadie estaba
viendo el panel, NO SE GRABABA NADA -- mal para un sistema tipo CCTV.

Este archivo soluciona eso con un "hilo en segundo plano" (background
thread): un CameraWorker arranca la cámara UNA vez cuando el programa
inicia, y se queda leyendo frames y grabando EN UN BUCLE INFINITO,
en paralelo, sin importar si hay alguien viendo la web o no.

La página web (/video_feed) ya NO lee la cámara directamente -- solo
le pide al worker "dame el último frame que tengas", como quien mira
por una ventana en vez de operar la cámara él mismo. Esto también
evita un problema técnico: la cámara solo permite UN lector a la vez,
así que si tanto la web como el registro de personas intentaran leer
la cámara por su cuenta, chocarían entre sí.
"""
import threading
import time

import cv2

import config
from camera import CameraStream
from recorder import PersonRecorder, ContinuousRecorder, AlertRecorder


class CameraWorker(threading.Thread):
    def __init__(self, camera_source, engine, backend=None, url=None, on_alert=None):
        super().__init__(daemon=True)
        self.camera_source = camera_source
        self.engine = engine

        self.camera = CameraStream(backend=backend, url=url)

        self.person_recorder = PersonRecorder(camera_source)
        self.general_recorder = ContinuousRecorder(camera_source)
        self.alert_recorder = AlertRecorder(camera_source, on_alert=on_alert)

        self._lock = threading.Lock()
        self._latest_raw_frame = None
        self._latest_display_frame = None
        self._running = False

    def run(self):
        self.camera.start()
        self._running = True
        delay = 1.0 / config.CAMERA_FRAMERATE

        while self._running:
            raw_frame = self.camera.read_frame()

            with self._lock:
                self._latest_raw_frame = raw_frame.copy()

            display_frame, results = self.engine.process_frame(raw_frame)

            if config.RECORD_PEOPLE_ENABLED:
                self.person_recorder.update(display_frame, results)
            if config.RECORD_ALERTS_ENABLED:
                self.alert_recorder.update(display_frame, results)
            if config.RECORD_GENERAL_ENABLED:
                self.general_recorder.write(display_frame)

            with self._lock:
                self._latest_display_frame = display_frame

            time.sleep(delay)

    def get_display_jpeg(self):
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
        self.camera.stop()