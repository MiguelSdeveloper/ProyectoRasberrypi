"""
Motor de detección + reconocimiento facial, reutilizado tanto por los
scripts de línea de comandos como por la aplicación web.
"""
import os
import json
import cv2
import config


class RecognitionEngine:
    def __init__(self):
        self.detector = cv2.CascadeClassifier(config.CASCADE_PATH)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.labels = {}
        self.ready = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(config.MODEL_PATH) and os.path.exists(config.LABELS_PATH):
            self.recognizer.read(config.MODEL_PATH)
            with open(config.LABELS_PATH) as f:
                self.labels = json.load(f)
            self.ready = True

    def reload(self):
        self._load_model()

    def process_frame(self, frame):
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
            confidence = None
            if self.ready:
                user_id, confidence = self.recognizer.predict(gray[y:y + h, x:x + w])
                if confidence < config.RECOGNITION_CONFIDENCE_THRESHOLD:
                    label = self.labels.get(str(user_id), "Desconocido")
            color = (0, 200, 0) if label != "Desconocido" else (0, 0, 200)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            results.append({"label": label, "confidence": confidence, "box": [int(x), int(y), int(w), int(h)]})
        return frame, results
