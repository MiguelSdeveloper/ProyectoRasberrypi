"""
=====================================================================
 RECOGNIZE_LIVE.PY -- Ventana local con reconocimiento en vivo
=====================================================================
Útil para probar rápido en la Pi con pantalla/VNC, sin pasar por la
parte web. Usa la cámara "principal" (la que definas en
config.CAMERA_BACKEND).

Uso:
    python recognize_live.py
"""
import cv2

import database
from camera import CameraStream
from recognition_engine import RecognitionEngine


def main():
    database.init_db()
    engine = RecognitionEngine()
    if not engine.ready:
        print("Aviso: no hay modelo entrenado todavía (ejecuta train_model.py).")
        print("Se mostrará la detección de rostros, pero todos aparecerán como 'Desconocido'.")

    cam = CameraStream().start()
    try:
        while True:
            frame = cam.read_frame()
            frame, _ = engine.process_frame(frame)
            cv2.imshow("FaceSec - presiona q para salir", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
