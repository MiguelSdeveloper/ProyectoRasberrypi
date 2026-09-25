"""
=====================================================================
 RECORDER.PY -- 3 tipos de grabación, cada uno con su propósito
=====================================================================
  1) PersonRecorder    -> UN solo archivo de video por cámara
                           (eficiente), pero registra en la base de
                           datos un evento INDEPENDIENTE por cada
                           persona conocida que aparece -- así
                           "Miguel + Juan" en el mismo frame generan
                           2 eventos distintos, no se pisan entre sí.
  2) ContinuousRecorder -> graba TODO el tiempo, en bloques de N minutos.
  3) AlertRecorder      -> clip de "Desconocido" (cámara con
                           reconocimiento) o "Movimiento" (cámara sin
                           reconocimiento), con pausa/reanudación.
"""
import os
import time

import cv2

import config
import database


# ---------------------------------------------------------------
# 1) Grabación por persona(s) conocida(s) -- soporta varias a la vez
# ---------------------------------------------------------------
class PersonRecorder:
    def __init__(self, camera_source):
        self.camera_source = camera_source
        self.writer = None
        self.video_path = None
        # person_id -> {"event_id", "name", "role", "missing_since"}
        self.active_people = {}
        self.folder = os.path.join(config.RECORDINGS_PEOPLE_DIR, camera_source)
        os.makedirs(self.folder, exist_ok=True)

    def update(self, frame, results):
        known = [
            r for r in results
            if r["label"] != "Desconocido" and r.get("person_id") is not None
        ]
        present_ids = set()

        # Abrir/actualizar un evento POR CADA persona conocida presente
        for r in known:
            pid = r["person_id"]
            present_ids.add(pid)
            if pid not in self.active_people:
                if self.writer is None:
                    self._start_writer(frame.shape)
                event_id = database.log_recognition_start(pid, r["label"], r["role"], self.camera_source)
                self.active_people[pid] = {
                    "event_id": event_id, "name": r["label"],
                    "role": r["role"], "missing_since": None,
                }
            else:
                self.active_people[pid]["missing_since"] = None

        # Cerrar (con margen de tolerancia) a quienes ya no aparecen
        for pid in list(self.active_people.keys()):
            if pid in present_ids:
                continue
            info = self.active_people[pid]
            if info["missing_since"] is None:
                info["missing_since"] = time.time()
            elif time.time() - info["missing_since"] > config.PERSON_GRACE_SECONDS:
                database.log_recognition_end(info["event_id"], self.video_path or "")
                del self.active_people[pid]

        # Un solo archivo mientras haya AL MENOS una persona conocida
        # (conocida en este frame, o todavía dentro del margen de
        # tolerancia de alguna que se acaba de ir).
        if known or self.active_people:
            if self.writer is not None:
                self.writer.write(frame)
        elif self.writer is not None:
            self._stop_writer()

    def _start_writer(self, frame_shape):
        height, width = frame_shape[0], frame_shape[1]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.video_path = os.path.join(self.folder, f"{timestamp}.avi")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.writer = cv2.VideoWriter(self.video_path, fourcc, config.CAMERA_FRAMERATE, (width, height))

    def _stop_writer(self):
        if self.writer is not None:
            self.writer.release()
        # Cierra cualquier evento que haya quedado abierto (por si el
        # programa se detiene con gente todavía en cámara).
        for info in self.active_people.values():
            database.log_recognition_end(info["event_id"], self.video_path or "")
        self.active_people = {}
        self.writer = None
        self.video_path = None


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
# 3) Grabación de alertas (desconocido, o movimiento en cámaras sin
#    reconocimiento facial)
# ---------------------------------------------------------------
class AlertRecorder:
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