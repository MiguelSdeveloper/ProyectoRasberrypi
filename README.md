# FaceSec

Sistema de reconocimiento facial para Raspberry Pi 3B+, con panel web de
estilo centro de seguridad (login, transmisión en vivo, bitácora de eventos).

## Estructura

```
facesec/
├── config.py              # toda la configuración en un solo lugar
├── camera.py               # envoltorio sobre Picamera2
├── recognition_engine.py   # detección (Haar) + reconocimiento (LBPH)
├── capture_dataset.py      # registra una persona nueva
├── train_model.py          # entrena el modelo LBPH
├── recognize_live.py       # ventana local con reconocimiento en vivo
├── requirements.txt
└── webapp/
    ├── app.py               # Flask: login, /video_feed, /dashboard
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   └── dashboard.html
    └── static/style.css
```

## Instalación en la Raspberry Pi

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-picamera2 python3-opencv libopenblas-dev ffmpeg libcap-dev

python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

1. Registrar una persona:
   ```bash
   python capture_dataset.py
   ```
2. Entrenar el modelo (repite el paso 1 con cada persona antes de esto):
   ```bash
   python train_model.py
   ```
3. Probar en ventana local (requiere VNC/escritorio):
   ```bash
   python recognize_live.py
   ```
4. Levantar el panel web:
   ```bash
   python webapp/app.py
   ```
   Abre `http://<ip-de-la-pi>:8080` desde otro dispositivo en la misma red.

   Usuarios de ejemplo (**cámbialos antes de usar esto en serio**):
   - `admin` / `admin`
   - `viewer` / `viewer`

## Notas

- `cv2.face.LBPHFaceRecognizer_create()` requiere el módulo `contrib` de
  OpenCV. El paquete `python3-opencv` de los repositorios de Raspberry Pi OS
  lo incluye; si te da `AttributeError: module 'cv2' has no attribute 'face'`,
  avísame y lo resolvemos.
- La resolución de cámara está reducida (320x240) en `config.py` pensando en
  el rendimiento de la Pi 3B+. Súbela si tu Pi va sobrada.
- Las contraseñas de ejemplo están en texto plano solo en el diccionario
  `USERS` de `webapp/app.py` (ya guardadas como hash). Para producción real,
  usa variables de entorno (`ADMIN_PASSWORD_HASH`, `APP_SECRET_KEY`) en vez
  de los valores por defecto.
