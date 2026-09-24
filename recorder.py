"""
=====================================================================
 RECORDER.PY -- 3 tipos de grabación, cada uno con su propósito
=====================================================================

  1) PersonRecorder    -> clip corto SOLO mientras ve a alguien
                           CONOCIDO. Carpeta: data/recordings/people/

  2) ContinuousRecorder -> graba TODO el tiempo, sin importar nada,
                           en bloques de N minutos. Es tu respaldo
                           tipo CCTV tradicional.
                           Carpeta: data/recordings/general/

  3) AlertRecorder      -> clip corto SOLO del fragmento donde
                           aparece alguien NO reconocido, con
                           nombre de archivo con fecha y rango de
                           horas real, y dispara una alerta. Si el
                           desconocido/movimiento desaparece y
                           reaparece dentro de ALERT_RESUME_WINDOW_SECONDS,
                           sigue en el MISMO archivo (no se fragmenta).
                           Carpeta: data/recordings/alerts/
"""
import os
import time

import cv2

import config
import database


# ---------------------------------------------------------------
# 1) Grabación por persona conocida
# ---------------------------------------------------------------
class PersonRecorder:
    def __init__(self, camera_source):
        self.camera_source = camera_source
        self.writer = None
        self.current_person = None
        self.current_role = None
        self.event_id = None
        self.video_path = None
        self.missing_count = 0
        self.folder = os.path.join(config.RECORDINGS_PEOPLE_DIR, camera_source)
        os.makedirs(self.folder, exist_ok=True)

    def update(self, frame, results):
        known = [r for r in results if r["label"] != "Desconocido"]
        person = known[0] if known else None

        if person is not None:
            self.missing_count = 0
            if self.current_person != person["label"]:
                self._stop()
                self._start(person["label"], person.get("role"), person.get("person_id"), frame.shape)
            self._write(frame)
        else:
            if self.current_person is not None:
                self.missing_count += 1
                if self.missing_count > config.RECORDING_GRACE_FRAMES:
                    self._stop()

    def _start(self, person_name, person_role, person_id, frame_shape):
        height, width = frame_shape[0], frame_shape[1]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = person_name.replace(" ", "_")
        filename = f"{safe_name}_{timestamp}.avi"
        self.video_path = os.path.join(self.folder, filename)

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.writer = cv2.VideoWriter(self.video_path, fourcc, config.CAMERA_FRAMERATE, (width, height))

        self.current_person = person_name
        self.current_role = person_role
        self.event_id = database.log_recognition_start(person_id, person_name, person_role, self.camera_source)

    def _write(self, frame):
        if self.writer is not None:
            self.writer.write(frame)

    def _stop(self):
        if self.writer is not None:
            self.writer.release()
            database.log_recognition_end(self.event_id, self.video_path)
        self.writer = None
        self.current_person = None
        self.current_role = None
        self.event_id = None
        self.video_path = None
        self.missing_count = 0


# ---------------------------------------------------------------
# 2) Grabación continua (CCTV tradicional, siempre encendida)
# ---------------------------------------------------------------
class ContinuousRecorder:
    def __init__(self, camera_source, segment_seconds=None):
        self.camera_source = camera_source
        self.segment_seconds = segment_seconds or config.GENERAL_SEGMENT_SECONDS
        self.writer = None
        self.segment_start = None
        self.frame_size = None
        self.folder = os.path.join(config.RECORDINGS_GENERAL_DIR, camera_source)
        os.makedirs(self.folder, exist_ok=True)

    def write(self, frame):
        height, width = frame.shape[0], frame.shape[1]
        now = time.time()
        needs_new_segment = (
            self.writer is None
            or (now - self.segment_start) >= self.segment_seconds
            or self.frame_size != (width, height)
        )
        if needs_new_segment:
            self._start_new_segment(width, height)
        self.writer.write(frame)

    def _start_new_segment(self, width, height):
        if self.writer is not None:
            self.writer.release()
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(self.folder, f"{timestamp}.avi")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.writer = cv2.VideoWriter(path, fourcc, config.CAMERA_FRAMERATE, (width, height))
        self.segment_start = time.time()
        self.frame_size = (width, height)

    def stop(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None


# ---------------------------------------------------------------
# 3) Grabación de alertas (solo el fragmento con un desconocido/movimiento)
# ---------------------------------------------------------------
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