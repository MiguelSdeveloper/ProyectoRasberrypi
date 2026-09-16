"""
Registra a una persona nueva: captura ~40 muestras de su rostro
y las guarda en data/dataset/, actualizando data/labels.json.

Uso:
    python capture_dataset.py
"""
import os
import sys
import json
import cv2

import config
from camera import CameraStream


def load_labels():
    if os.path.exists(config.LABELS_PATH):
        with open(config.LABELS_PATH) as f:
            return json.load(f)
    return {}


def save_labels(labels):
    os.makedirs(os.path.dirname(config.LABELS_PATH), exist_ok=True)
    with open(config.LABELS_PATH, "w") as f:
        json.dump(labels, f, indent=2)


def next_user_id(labels):
    return max([int(k) for k in labels.keys()], default=0) + 1


def main():
    name = input("Nombre de la persona a registrar: ").strip()
    if not name:
        print("Nombre inválido.")
        sys.exit(1)

    labels = load_labels()
    user_id = next_user_id(labels)
    labels[str(user_id)] = name
    save_labels(labels)

    os.makedirs(config.DATASET_DIR, exist_ok=True)
    detector = cv2.CascadeClassifier(config.CASCADE_PATH)

    cam = CameraStream().start()
    print(f"Capturando rostro para '{name}' (ID {user_id}). Mira a la cámara...")
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
                filename = os.path.join(config.DATASET_DIR, f"user.{user_id}.{count}.jpg")
                cv2.imwrite(filename, face_img)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

            cv2.imshow("Registro de rostro - presiona q para salir", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.stop()
        cv2.destroyAllWindows()

    print(f"Listo. {count} muestras guardadas para '{name}'.")


if __name__ == "__main__":
    main()
