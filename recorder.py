"""
=====================================================================
 RECORDER.PY -- Graba video SOLO mientras una persona está en cámara
=====================================================================
CONCEPTO CLAVE: esto es una "máquina de estados" pequeñita.

En cualquier momento, un PersonRecorder está en uno de 2 estados:

    [SIN GRABAR] --(aparece alguien conocido)--> [GRABANDO]
    [GRABANDO]   --(desaparece por N frames)-->  [SIN GRABAR]

Cada frame que llega, llamamos a update(frame, resultados) y el
objeto decide solo si debe empezar, seguir, o cortar la grabación.
Así el resto del programa (app.py) no necesita saber CÓMO se graba,
solo le entrega cada frame y listo -- esto se llama "encapsulamiento".

¿Por qué un "margen de tolerancia" (RECORDING_GRACE_FRAMES)?
Porque la detección de rostros no es perfecta: en un frame puede
fallar por un parpadeo, un giro de cabeza, etc. Si cortáramos la
grabación en el primer frame donde no se detecta a nadie, tendríamos
videos cortados en pedacitos en vez de un video continuo.
"""
import os
import time

import cv2

import config
import database


class PersonRecorder:
    def __init__(self, camera_source):
        # camera_source es un texto como "pi" o "wifi", para saber
        # de qué cámara viene cada grabación (útil con 2 cámaras).
        self.camera_source = camera_source
        self.writer = None            # objeto de OpenCV que escribe el video
        self.current_person = None    # nombre de a quién estamos grabando ahora mismo
        self.current_role = None
        self.event_id = None          # fila en la base de datos que estamos llenando
        self.video_path = None
        self.missing_count = 0        # cuántos frames seguidos llevamos SIN verla
        os.makedirs(config.RECORDINGS_DIR, exist_ok=True)

    def update(self, frame, results):
        """
        Se llama UNA VEZ POR CADA FRAME de la cámara.
        'results' es la lista que devuelve RecognitionEngine.process_frame():
        cada elemento tiene "label" (nombre o "Desconocido") y "role".

        Regla simple: si hay una o más personas CONOCIDAS en el frame,
        grabamos a la primera de ellas. (Se puede hacer más complejo
        -- un video por persona simultánea -- pero para un proyecto
        de clase, un video a la vez es más que suficiente y más fácil
        de explicar.)
        """
        known = [r for r in results if r["label"] != "Desconocido"]
        person = known[0] if known else None

        if person is not None:
            self.missing_count = 0  # la volvimos a ver, resetea el contador de ausencia

            if self.current_person != person["label"]:
                # O es la primera vez que la vemos, o cambió la persona
                # sin que hubiéramos cortado el video anterior todavía.
                self._stop()
                self._start(person["label"], person.get("role"), frame.shape)

            self._write(frame)

        else:
            # Nadie conocido en este frame.
            if self.current_person is not None:
                self.missing_count += 1
                if self.missing_count > config.RECORDING_GRACE_FRAMES:
                    # Ya pasó el margen de tolerancia: cortamos de verdad.
                    self._stop()

    def _start(self, person_name, person_role, frame_shape):
        height, width = frame_shape[0], frame_shape[1]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = person_name.replace(" ", "_")
        filename = f"{safe_name}_{self.camera_source}_{timestamp}.avi"
        self.video_path = os.path.join(config.RECORDINGS_DIR, filename)

        # "XVID" es un códec de video ampliamente soportado y liviano
        # para la CPU de la Pi (comparado con códecs más modernos).
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
