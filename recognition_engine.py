"""
=====================================================================
 RECOGNITION_ENGINE.PY
 Detección + reconocimiento facial con LBPH
=====================================================================
"""

import os
import threading

import cv2

import config
import database


class RecognitionEngine:

    def __init__(self):

        self.detector = cv2.CascadeClassifier(
            config.CASCADE_PATH
        )

        self.recognizer = cv2.face.LBPHFaceRecognizer_create()

        self.people = {}

        self.ready = False

        self.model_status = "NOT_TRAINED"

        self.model_error = None

        self._lock = threading.Lock()

        self._load_model()


    # ==============================================================
    # CARGAR MODELO
    # ==============================================================

    def _load_model(self):

        if not os.path.exists(config.MODEL_PATH):

            self.ready = False
            self.model_status = "NOT_TRAINED"
            self.model_error = None

            return

        try:

            self.recognizer.read(
                config.MODEL_PATH
            )

            self.people = database.get_people()

            self.ready = True

            self.model_status = "READY"

            self.model_error = None

        except Exception as e:

            self.ready = False

            self.model_status = "ERROR"

            self.model_error = str(e)

            print(
                f"[RECOGNITION] ERROR cargando "
                f"el modelo: {e}"
            )


    # ==============================================================
    # RECARGAR MODELO
    # ==============================================================

    def reload(self):

        with self._lock:

            self._load_model()


    # ==============================================================
    # PROCESAR FRAME
    # ==============================================================

    def process_frame(
        self,
        frame,
        camera_source=None
    ):

        with self._lock:

            return self._process_frame_locked(
                frame,
                camera_source
            )


    # ==============================================================
    # PROCESAMIENTO INTERNO
    # ==============================================================

    def _process_frame_locked(
        self,
        frame,
        camera_source
    ):

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )


        # Detectar caras

        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=config.FACE_DETECTION_SCALE_FACTOR,
            minNeighbors=config.FACE_DETECTION_MIN_NEIGHBORS,
            minSize=config.FACE_DETECTION_MIN_SIZE
        )


        results = []


        for (x, y, w, h) in faces:

            label = "Desconocido"

            role = None

            person_id = None

            confidence = None


            if self.ready:

                # Recortar rostro

                face_roi = gray[
                    y:y + h,
                    x:x + w
                ]


                # ==================================================
                # RECONOCIMIENTO LBPH
                #
                # USB Y PI UTILIZAN EL MISMO PROCESAMIENTO.
                # ==================================================

                predicted_id, confidence = (
                    self.recognizer.predict(
                        face_roi
                    )
                )


                # Menor distancia = mayor similitud

                is_match = (
                    confidence
                    < config.RECOGNITION_CONFIDENCE_THRESHOLD
                )


                person = (
                    self.people.get(predicted_id)
                    if is_match
                    else None
                )


                # ==================================================
                # DEBUG
                # ==================================================

                if config.RECOGNITION_DEBUG:

                    if person:

                        print(
                            f"[RECOGNITION] "
                            f"camera={camera_source or '?'} "
                            f"face=({x},{y},{w},{h}) "
                            f"predicted_id={predicted_id} "
                            f"distance={confidence:.1f} "
                            f"threshold="
                            f"{config.RECOGNITION_CONFIDENCE_THRESHOLD} "
                            f"result=KNOWN "
                            f"person={person['name']} "
                            f"role={person['role']}"
                        )

                    else:

                        print(
                            f"[RECOGNITION] "
                            f"camera={camera_source or '?'} "
                            f"face=({x},{y},{w},{h}) "
                            f"predicted_id={predicted_id} "
                            f"distance={confidence:.1f} "
                            f"threshold="
                            f"{config.RECOGNITION_CONFIDENCE_THRESHOLD} "
                            f"result=UNKNOWN"
                        )


                # ==================================================
                # PERSONA CONOCIDA
                # ==================================================

                if person:

                    label = person["name"]

                    role = person["role"]

                    person_id = predicted_id


            # ======================================================
            # COLOR DEL RECTÁNGULO
            # ======================================================

            if label != "Desconocido":

                color = (0, 200, 0)

            else:

                color = (0, 0, 200)


            # ======================================================
            # TEXTO
            # ======================================================

            if role:

                display_text = (
                    f"{label} ({role})"
                )

            else:

                display_text = label


            # ======================================================
            # RECTÁNGULO
            # ======================================================

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                color,
                2
            )


            # ======================================================
            # NOMBRE
            # ======================================================

            cv2.putText(
                frame,
                display_text,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )


            # ======================================================
            # RESULTADO
            # ======================================================

            results.append({

                "person_id": person_id,

                "label": label,

                "role": role,

                "confidence": (
                    float(confidence)
                    if confidence is not None
                    else None
                ),

                "box": [
                    int(x),
                    int(y),
                    int(w),
                    int(h)
                ]

            })


        return frame, results