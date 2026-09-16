"""
Muestra la cámara en vivo con reconocimiento facial en una ventana local.
Requiere una sesión gráfica (VNC) para funcionar.

Uso:
    python recognize_live.py
"""
import cv2

from camera import CameraStream
from recognition_engine import RecognitionEngine


def main():
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
