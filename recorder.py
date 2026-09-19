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


class PersonRecorder:
    def __init__(self, camera_source):
        self.camera_source = camera_source
        self.writer = None
        self.current_person = None
        self.current_role = None
        self.event_id = None
        self.video_path = None
        self.missing_count = 0
        os.makedirs(config.RECORDINGS_DIR, exist_ok=True)

    def update(self, frame, results):
        known = [r for r in results if r["label"] != "Desconocido"]
        person = known[0] if known else None

        if person is not None:
            self.missing_count = 0
            if self.current_person != person["label"]:
                self._stop()
                self._start(person["label"], person.get("role"), frame.shape)
            self._write(frame)
        else:
            if self.current_person is not None:
                self.missing_count += 1
                if self.missing_count > config.RECORDING_GRACE_FRAMES:
                    self._stop()

    def _start(self, person_name, person_role, frame_shape):
        height, width = frame_shape[0], frame_shape[1]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = person_name.replace(" ", "_")
        filename = f"{safe_name}_{self.camera_source}_{timestamp}.avi"
        self.video_path = os.path.join(config.RECORDINGS_DIR, filename)

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.writer = cv2.VideoWriter(
            self.video_path, fourcc, config.CAMERA_FRAMERATE, (width, height)
        )

        self.current_person = person_name
        self.current_role = person_role
        self.event_id = database.log_recognition_start(
            None, person_name, person_role, self.camera_source
        )
        print(f"[{self.camera_source}] Empezó grabación: {person_name} -> {self.video_path}")

    def _write(self, frame):
        if self.writer is not None:
            self.writer.write(frame)

    def _stop(self):
        if self.writer is not None:
            self.writer.release()
            database.log_recognition_end(self.event_id, self.video_path)
            print(f"[{self.camera_source}] Terminó grabación: {self.current_person}")
        self.writer = None
        self.current_person = None
        self.current_role = None
        self.event_id = None
        self.video_path = None
        self.missing_count = 0