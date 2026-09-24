"""
=====================================================================
 RECORDER.PY -- Graba video SOLO mientras una persona está en cámara
=====================================================================
Máquina de estados:
    [SIN GRABAR] --(aparece alguien conocido)--> [GRABANDO]
    [GRABANDO]   --(desaparece por N frames)-->  [SIN GRABAR]
"""
import os
import time

import cv2

import config
import database


class AlertRecorder:
    """
    Graba SOLO el fragmento donde se cumple una condición de alerta
    (por defecto: aparece alguien "Desconocido"; en la cámara WiFi se
    usa para "Movimiento" en su lugar -- ver trigger_label).

    Espera hasta ALERT_RESUME_WINDOW_SECONDS (60s por defecto) antes
    de cerrar el archivo de verdad. Mientras tanto queda "pausado": no
    escribe frames vacíos ni crea un archivo nuevo. Si la condición
    vuelve a cumplirse dentro de esa ventana, sigue en el MISMO
    archivo -- así evitamos decenas de videítos fragmentados.
    """
    def __init__(self, camera_source, on_alert=None, trigger_label="Desconocido", alert_prefix="ALERTA"):
        self.camera_source = camera_source
        self.on_alert = on_alert
        self.trigger_label = trigger_label
        self.alert_prefix = alert_prefix
        self.writer = None
        self.start_epoch = None
        self.missing_since = None
        self.video_path = None
        self.event_id = None
        self.folder = os.path.join(config.RECORDINGS_ALERTS_DIR, camera_source)
        os.makedirs(self.folder, exist_ok=True)

    def update(self, frame, results):
        triggered = any(r["label"] == self.trigger_label for r in results)

        if triggered:
            self.missing_since = None
            if self.writer is None:
                self._start(frame.shape)
            self.writer.write(frame)
        else:
            if self.writer is not None:
                if self.missing_since is None:
                    self.missing_since = time.time()
                elapsed = time.time() - self.missing_since
                if elapsed > config.ALERT_RESUME_WINDOW_SECONDS:
                    self._stop()

    def _start(self, frame_shape):
        height, width = frame_shape[0], frame_shape[1]
        self.start_epoch = time.time()
        start_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(self.start_epoch))

        self.video_path = os.path.join(self.folder, f"{self.alert_prefix}_{start_str}_en-curso.avi")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.writer = cv2.VideoWriter(self.video_path, fourcc, config.CAMERA_FRAMERATE, (width, height))

        self.event_id = database.log_recognition_start(None, self.trigger_label, None, self.camera_source)

        if self.on_alert:
            fecha_hora = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_epoch))
            descripcion = "Persona NO reconocida" if self.trigger_label == "Desconocido" else self.trigger_label
            self.on_alert(f"{descripcion} detectado (cámara {self.camera_source}) - {fecha_hora}")

    def _stop(self):
        self.writer.release()

        start_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(self.start_epoch))
        end_str = time.strftime("%H-%M-%S")
        final_path = os.path.join(self.folder, f"{self.alert_prefix}_{start_str}_hasta_{end_str}.avi")
        os.rename(self.video_path, final_path)

        database.log_recognition_end(self.event_id, final_path)

        self.writer = None
        self.start_epoch = None
        self.video_path = None
        self.event_id = None
        self.missing_since = None