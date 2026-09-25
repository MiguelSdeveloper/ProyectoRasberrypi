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
        print("No hay dataset. Registra a alguien primero desde el panel web.")
        return False

    # Solo entrenamos con IDs que SIGUEN existiendo en la base de
    # datos -- si alguien fue eliminado pero sus fotos quedaron
    # huérfanas en disco por alguna razón, no queremos que el modelo
    # las siga usando.
    valid_ids = set(database.get_people().keys())

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces, ids = [], []
    omitidas = 0

    for filename in os.listdir(config.DATASET_DIR):
        if not filename.lower().endswith((".jpg", ".png")):
            continue
        try:
            # "user.3.17.jpg" -> partes = ["user", "3", "17", "jpg"] -> id = 3
            person_id = int(filename.split(".")[1])
        except (IndexError, ValueError):
            omitidas += 1
            continue

        if person_id not in valid_ids:
            omitidas += 1
            continue

        path = os.path.join(config.DATASET_DIR, filename)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            # archivo corrupto/ilegible -- se omite, no rompe el entrenamiento
            omitidas += 1
            continue

        faces.append(img)
        ids.append(person_id)

    if not faces:
        print("No se encontraron imágenes válidas en el dataset.")
        return False

    print(f"Entrenando con {len(faces)} imágenes de {len(set(ids))} persona(s) "
          f"({omitidas} imagen(es) omitidas por ser inválidas o de personas eliminadas).")

    try:
        recognizer.train(faces, np.array(ids))

        os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)

        # Escritura ATÓMICA: primero se escribe en un archivo TEMPORAL, y
        # solo cuando terminó de escribirse por completo, se renombra al
        # nombre final. os.replace() es instantáneo a nivel de sistema de
        # archivos, así que nunca queda un trainer.yml "a medias" -- esto
        # evita la corrupción si 2 entrenamientos corren a la vez.
        tmp_path = config.MODEL_PATH + ".tmp"
        recognizer.write(tmp_path)
        os.replace(tmp_path, config.MODEL_PATH)
    except Exception as e:
        print(f"ERROR entrenando el modelo: {e}")
        print("El trainer.yml anterior (si existía) NO se tocó -- el sistema sigue funcionando con ese.")
        return False

    print(f"Modelo guardado en {config.MODEL_PATH}")
    return True


if __name__ == "__main__":
    main()
