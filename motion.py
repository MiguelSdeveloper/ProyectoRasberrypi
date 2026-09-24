"""
=====================================================================
 MOTION.PY -- Detección de movimiento (función de la cámara WiFi)
=====================================================================
A diferencia de recognition_engine.py, esto NO intenta reconocer
caras -- solo detecta si algo se movió en la escena, comparando cada
frame contra un "fondo" que aprende automáticamente con el tiempo.

Por qué la cámara WiFi usa esto en vez de reconocimiento facial:
correr LBPH + detección de caras en 2 cámaras a la vez sería
demasiada carga para una Pi 3B+. Además, tiene sentido que cada
cámara cumpla un rol distinto: la principal identifica personas de
cerca, la WiFi vigila una zona general y solo avisa "aquí hubo
actividad" sin necesitar saber quién es.
"""
import cv2

import config


class MotionDetector:
    def __init__(self, min_area=None):
        # MOG2 = Mixture of Gaussians: un método clásico de OpenCV que
        # aprende cómo se ve el fondo "quieto" y resalta lo que cambia.
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=40, detectShadows=False
        )
        self.min_area = min_area or config.MOTION_MIN_AREA

    def process_frame(self, frame):
        mask = self.bg_subtractor.apply(frame)
        # Limpia ruido pequeño de la máscara (puntitos sueltos que no son movimiento real)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            motion_detected = True
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 2)
            cv2.putText(frame, "Movimiento", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        # Mismo "shape" de resultado que recognition_engine.py, para que
        # el resto del sistema (recorder.py, camera_worker.py) no tenga
        # que saber la diferencia entre una cámara y otra.
        results = []
        if motion_detected:
            results.append({
                "label": "Movimiento", "role": None,
                "person_id": None, "confidence": None,
            })
        return frame, results