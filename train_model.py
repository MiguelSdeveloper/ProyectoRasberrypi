"""
=====================================================================
 TRAIN_MODEL.PY -- Entrena el modelo LBPH con las fotos del dataset
=====================================================================
"Entrenar" aquí significa: el algoritmo LBPH mira TODAS las fotos en
data/dataset/, aprende los patrones de textura característicos de
cada cara (agrupados por su ID, sacado del nombre del archivo
"user.<id>.<numero>.jpg"), y guarda ese "conocimiento" en un solo
archivo: data/trainer.yml.

Ese trainer.yml es justo lo que recognition_engine.py carga después
para poder reconocer caras en vivo.

Uso:
    python train_model.py
"""
import os

import cv2
import numpy as np

import config
import database


def main():
    database.init_db()

    if not os.path.isdir(config.DATASET_DIR):
        print("No hay dataset. Ejecuta capture_dataset.py primero.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces, ids = [], []

    for filename in os.listdir(config.DATASET_DIR):
        if not filename.lower().endswith((".jpg", ".png")):
            continue
        try:
            # "user.3.17.jpg" -> partes = ["user", "3", "17", "jpg"] -> id = 3
            person_id = int(filename.split(".")[1])
        except (IndexError, ValueError):
            continue

        path = os.path.join(config.DATASET_DIR, filename)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        faces.append(img)
        ids.append(person_id)

    if not faces:
        print("No se encontraron imágenes válidas en el dataset.")
        return

    print(f"Entrenando con {len(faces)} imágenes de {len(set(ids))} persona(s)...")
    recognizer.train(faces, np.array(ids))

    os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
    recognizer.write(config.MODEL_PATH)
    print(f"Modelo guardado en {config.MODEL_PATH}")


if __name__ == "__main__":
    main()
