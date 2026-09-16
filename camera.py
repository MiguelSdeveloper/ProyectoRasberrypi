"""
Envoltorio propio sobre Picamera2, con la configuración de FaceSec.
"""
import cv2
from picamera2 import Picamera2
import config


class CameraStream:
    def __init__(self, resolution=None, framerate=None):
        self.picam2 = Picamera2()
        resolution = resolution or config.CAMERA_RESOLUTION
        video_config = self.picam2.create_video_configuration(
            main={"size": resolution, "format": "RGB888"},
            controls={"FrameRate": framerate or config.CAMERA_FRAMERATE},
        )
        self.picam2.configure(video_config)

    def start(self):
        self.picam2.start()
        return self

    def read_frame(self):
        frame = self.picam2.capture_array()
        if config.CAMERA_MIRROR:
            frame = cv2.flip(frame, 1)
        return frame

    def stop(self):
        self.picam2.stop()
        self.picam2.close()
