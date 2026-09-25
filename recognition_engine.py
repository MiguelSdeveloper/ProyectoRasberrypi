"""
=====================================================================
 RECOGNITION_ENGINE.PY -- Detección + reconocimiento facial
=====================================================================
Pipeline por cada frame:
  1) gris -> 2) Haar Cascade detecta TODAS las caras -> 3) por cada
  cara, LBPH.predict() -> 4) interpretar distancia contra el umbral
  -> 5) buscar en la base de datos (nombre/rol) -> 6) dibujar -> 7)
  devolver resultados ESTRUCTURADOS (no solo dibujo visual).

CONCURRENCIA: este motor puede ser compartido por más de una cámara
(varios CameraWorker en hilos distintos). cv2.CascadeClassifier y el
LBPHFaceRecognizer NO garantizan ser seguros ante llamadas
concurrentes desde 2 hilos a la vez -- por eso todo process_frame()
está protegido con un candado (Lock). reload() usa el mismo candado
para que nunca se recargue el modelo a la mitad de una predicción.
"""
import os
import threading

import cv2

import config
import database


class RecognitionEngine:
    def __init__(self):
        self.detector = cv2.CascadeClassifier(config.CASCADE_PATH)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.people = {}
        self.ready = False
        self._lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        if os.path.exists(config.MODEL_PATH):
            self.recognizer.read(config.MODEL_PATH)
            self.people = database.get_people()
            self.ready = True
        else:
            self.ready = False

    def reload(self):
        with self._lock:
            self._load_model()

    def process_frame(self, frame):
        with self._lock:
            return self._process_frame_locked(frame)

    def _process_frame_locked(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=config.FACE_DETECTION_SCALE_FACTOR,
            minNeighbors=config.FACE_DETECTION_MIN_NEIGHBORS,
            minSize=config.FACE_DETECTION_MIN_SIZE,
        )

        results = []
        for (x, y, w, h) in faces:
            label = "Desconocido"
            role = None
            person_id = None
            confidence = None

            if self.ready:
                predicted_id, confidence = self.recognizer.predict(gray[y:y + h, x:x + w])
                # LBPH: DISTANCIA más baja = MÁS parecido. Por eso la
                # comparación es "menor que el umbral", no al revés.
                is_match = confidence < config.RECOGNITION_CONFIDENCE_THRESHOLD
                person = self.people.get(predicted_id) if is_match else None

                if config.RECOGNITION_DEBUG:
                    print(f"[RECOGNITION] face=({x},{y},{w},{h}) predicted_id={predicted_id} "
                          f"distance={confidence:.1f} threshold={config.RECOGNITION_CONFIDENCE_THRESHOLD} "
                          f"result={'KNOWN' if person else 'UNKNOWN'}"
                          + (f" person={person['name']}" if person else ""))

                if person:
                    label = person["name"]
                    role = person["role"]
                    person_id = predicted_id

            color = (0, 200, 0) if label != "Desconocido" else (0, 0, 200)
            display_text = f"{label} ({role})" if role else label
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, display_text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            results.append({
                "person_id": person_id,
                "label": label,
                "role": role,
                "confidence": float(confidence) if confidence is not None else None,
                "box": [int(x), int(y), int(w), int(h)],
            })

        return frame, results