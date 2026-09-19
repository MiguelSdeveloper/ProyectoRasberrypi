"""
=====================================================================
 RECOGNITION_ENGINE.PY -- Detección + reconocimiento facial
=====================================================================
Este archivo hace 2 cosas, en 2 pasos distintos (¡no son lo mismo!):

  1) DETECCIÓN: "¿hay una cara en esta imagen y en qué posición
     (x, y, ancho, alto)?" -- esto lo hace el Haar Cascade, un
     algoritmo clásico de visión por computadora que NO sabe de
     quién es la cara, solo que ES una cara.

  2) RECONOCIMIENTO: "de las caras que detecté, ¿A QUIÉN
     pertenecen?" -- esto lo hace LBPH (Local Binary Patterns
     Histograms), el modelo que entrenamos con train_model.py a
     partir de las fotos en data/dataset/.

Por eso el flujo siempre es: primero detectar, LUEGO (con cada cara
detectada) preguntarle al reconocedor "¿quién es esta?".
"""
import cv2

import config
import database


class RecognitionEngine:
    def __init__(self):
        # El detector de caras (no sabe nombres, solo encuentra caras)
        self.detector = cv2.CascadeClassifier(config.CASCADE_PATH)

        # El reconocedor (si sabe entrenó, sabe traducir una cara a un ID numérico)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()

        # Diccionario { id_numerico: {"name": ..., "role": ...} },
        # que viene de la base de datos (ver database.py)
        self.people = {}

        self.ready = False  # True solo si ya existe un modelo entrenado
        self._load_model()

    def _load_model(self):
        """
        Carga el modelo LBPH ya entrenado (trainer.yml) y la lista de
        personas conocidas desde la base de datos. Si el modelo
        todavía no existe (no has corrido train_model.py), self.ready
        se queda en False y el sistema detecta caras pero las marca
        todas como "Desconocido".
        """
        import os
        if os.path.exists(config.MODEL_PATH):
            self.recognizer.read(config.MODEL_PATH)
            self.people = database.get_people()
            self.ready = True

    def reload(self):
        """Se puede llamar para releer el modelo después de re-entrenar
        sin tener que reiniciar todo el programa."""
        self._load_model()

    def process_frame(self, frame):
        """
        Recibe un frame de video (una imagen), y devuelve:
          - el mismo frame, pero con rectángulos y nombres dibujados encima
          - una lista de resultados: [{"label": "Miguel", "role": "Admin",
             "confidence": 42.1, "box": [x, y, w, h]}, ...]

        La lista de resultados es lo que usa recorder.py para decidir
        si debe grabar o no.
        """
        # 1) Convertir a escala de grises: el detector Haar y el
        #    reconocedor LBPH trabajan en blanco y negro, no en color
        #    (así son más rápidos y el color no aporta información
        #    útil para reconocer la FORMA de una cara).
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 2) Detectar TODAS las caras en la imagen. Devuelve una lista
        #    de rectángulos (x, y, ancho, alto), uno por cara encontrada.
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
            confidence = None

            if self.ready:
                # Le pasamos SOLO el recorte de la cara (no la imagen
                # completa) al reconocedor. Devuelve el ID numérico
                # más parecido, y qué tan "lejos" está (confidence:
                # MÁS BAJO = más parecido, ojo que es al revés de lo
                # que uno esperaría de una "confianza").
                person_id, confidence = self.recognizer.predict(gray[y:y + h, x:x + w])

                if confidence < config.RECOGNITION_CONFIDENCE_THRESHOLD:
                    person = self.people.get(person_id)
                    if person:
                        label = person["name"]
                        role = person["role"]

            # Dibujar el rectángulo y el texto sobre la imagen a color
            # (no sobre la de escala de grises, que es solo para
            # cálculo interno).
            color = (0, 200, 0) if label != "Desconocido" else (0, 0, 200)
            display_text = f"{label} ({role})" if role else label
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, display_text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            results.append({
                "label": label,
                "role": role,
                "confidence": confidence,
                "box": [int(x), int(y), int(w), int(h)],
            })

        return frame, results
