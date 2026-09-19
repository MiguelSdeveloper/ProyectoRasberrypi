"""
=====================================================================
 CAPTURE_DATASET.PY -- Registra a una persona nueva (con su rol)
=====================================================================
Este script hace 2 cosas:
  1) Guarda en la BASE DE DATOS quién es esta persona y qué rol tiene
     (tabla "people" -- ver database.py).
  2) Toma ~40 fotos de su cara y las guarda en data/dataset/, con un
     nombre de archivo tipo "user.<id>.<numero>.jpg". Ese <id> es el
     mismo ID que queda guardado en la base de datos -- así es como
     luego train_model.py y recognition_engine.py "conectan" las
     fotos con el nombre/rol correcto.

Uso:
    python capture_dataset.py
"""
import os
import sys

import cv2

import config
import database
from camera import CameraStream

ROLES_DISPONIBLES = ["Admin", "Estudiante", "Invitado"]


def preguntar_rol():
    print("Roles disponibles:")
    for i, rol in enumerate(ROLES_DISPONIBLES, start=1):
        print(f"  {i}. {rol}")
    while True:
        opcion = input("Elige el número del rol: ").strip()
        if opcion.isdigit() and 1 <= int(opcion) <= len(ROLES_DISPONIBLES):
            return ROLES_DISPONIBLES[int(opcion) - 1]
        print("Opción inválida, intenta de nuevo.")


def main():
    database.init_db()  # crea las tablas si es la primera vez que se corre

    name = input("Nombre de la persona a registrar: ").strip()
    if not name:
        print("Nombre inválido.")
        sys.exit(1)

    role = preguntar_rol()

    # El ID es un número simple que va subiendo: 1, 2, 3... Se calcula
    # mirando qué IDs ya existen en la base de datos.
    person_id = database.next_person_id()
    database.add_person(person_id, name, role)

    os.makedirs(config.DATASET_DIR, exist_ok=True)
    detector = cv2.CascadeClassifier(config.CASCADE_PATH)

    cam = CameraStream().start()
    print(f"Capturando rostro para '{name}' ({role}, ID {person_id}). Mira a la cámara...")
    count = 0
    try:
        while count < 40:
            frame = cam.read_frame()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=config.FACE_DETECTION_SCALE_FACTOR,
                minNeighbors=config.FACE_DETECTION_MIN_NEIGHBORS,
                minSize=config.FACE_DETECTION_MIN_SIZE,
            )
            for (x, y, w, h) in faces:
                count += 1
                face_img = gray[y:y + h, x:x + w]
                filename = os.path.join(config.DATASET_DIR, f"user.{person_id}.{count}.jpg")
                cv2.imwrite(filename, face_img)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

            cv2.imshow("Registro de rostro - presiona q para salir", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.stop()
        cv2.destroyAllWindows()

    print(f"Listo. {count} muestras guardadas para '{name}' ({role}).")
    print("Recuerda correr 'python train_model.py' para que el modelo aprenda esta cara nueva.")


if __name__ == "__main__":
    main()
