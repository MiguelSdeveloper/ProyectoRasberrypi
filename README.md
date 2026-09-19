# FaceSec — Guía completa del proyecto

Sistema de reconocimiento facial para Raspberry Pi con: base de datos,
roles por persona, grabación automática por presencia, y soporte para
2 cámaras simultáneas (Pi/USB + WiFi).

## 1. Arquitectura general (para explicar a tus compañeros)

```
config.py              -> TODA la configuración en un solo lugar
database.py             -> guarda personas (con rol) y eventos de reconocimiento
camera.py                -> abstrae la cámara (picamera2 / usb / wifi), misma interfaz para las 3
recognition_engine.py    -> detecta caras (Haar) + reconoce quién es (LBPH) + busca su rol en la BD
recorder.py               -> "máquina de estados": graba SOLO mientras ve a alguien conocido
capture_dataset.py        -> registra una persona nueva (nombre + rol + fotos)
train_model.py             -> entrena el modelo LBPH con las fotos guardadas
recognize_live.py          -> prueba rápida en ventana local (sin web)
webapp/app.py                -> panel Flask: login, 2 streams de video, dashboard
webapp/templates/            -> HTML de las páginas
webapp/static/style.css       -> diseño visual, incluye la posición de las cámaras
```

**Flujo de datos, de principio a fin:**

1. `capture_dataset.py` guarda a una persona en la BD (`people`) y toma fotos → `data/dataset/`
2. `train_model.py` lee esas fotos y "aprende" → genera `data/trainer.yml`
3. `webapp/app.py` arranca 1 o 2 cámaras. Cada frame que llega:
   - pasa por `recognition_engine.py` → sabe si hay caras y de quién son
   - pasa por `recorder.py` → decide si debe grabar ese frame o no
   - se envía al navegador como parte del video en vivo
4. Todo reconocimiento con inicio/fin queda guardado en `recognition_events` (BD)
5. El dashboard mezcla esos eventos con los de login y los muestra en el log

## 2. La base de datos

Es un solo archivo, `data/facesec.db` (SQLite — no hay que instalar ni
configurar ningún servidor). Tiene 2 tablas:

- **`people`**: id, name, role → quién es cada persona y su rol (Admin, Estudiante, Invitado)
- **`recognition_events`**: cada vez que la cámara reconoció a alguien, con hora de inicio, hora de fin, cámara usada, y el video guardado

Puedes explorarla a mano así (útil para la demo con tus compañeros):
```bash
sqlite3 data/facesec.db
sqlite> SELECT * FROM people;
sqlite> SELECT * FROM recognition_events ORDER BY id DESC LIMIT 10;
sqlite> .quit
```
(si no tienes el comando `sqlite3`, instálalo con `sudo apt install sqlite3`)

## 3. Roles

Al correr `python capture_dataset.py`, ahora te pide elegir un rol
(Admin / Estudiante / Invitado) para la persona que registras. Ese
rol se muestra junto al nombre en el video en vivo y en el log de
eventos. Para agregar más roles, edita la lista `ROLES_DISPONIBLES`
al inicio de `capture_dataset.py`.

## 4. Grabación automática

`recorder.py` implementa una máquina de estados simple:
```
SIN GRABAR --(aparece persona conocida)--> GRABANDO
GRABANDO   --(no la ve por 15 frames seguidos)--> SIN GRABAR
```
Los videos quedan en `data/recordings/`, con nombre
`<nombre>_<camara>_<fecha_hora>.avi`. El margen de 15 frames
(`config.RECORDING_GRACE_FRAMES`) evita que un parpadeo corte el
video en pedacitos — ajústalo si quieres más o menos tolerancia.

## 5. Instalación en la Raspberry Pi

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-picamera2 python3-opencv libopenblas-dev ffmpeg libcap-dev

python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install flask imutils
```
(numpy y opencv ya vienen del sistema por `--system-site-packages`)

Si `cv2.data` no existe en tu build de OpenCV, descarga el cascade a mano:
```bash
wget -O data/haarcascade_frontalface_default.xml \
  https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml
```

## 6. Uso

```bash
python capture_dataset.py     # registra a cada compañero (nombre + rol + fotos)
python train_model.py         # entrena el modelo con todos los registrados
python webapp/app.py          # levanta el panel en http://<ip-de-la-pi>:8080
```
Login de ejemplo: `admin` / `admin` (¡cámbialo antes de usar esto en serio!)

## 7. Activar la segunda cámara (WiFi)

En `config.py`:
```python
CAMERA_WIFI_ENABLED = True
CAMERA_WIFI_URL = "http://192.168.0.50:81/stream"   # la URL que dé tu cámara
```
El dashboard mostrará automáticamente un segundo panel de video
("CÁMARA 2 (WiFi)") apenas actives esto.

## 8. Cámara principal: Pi / USB / WiFi

En `config.py`, la variable `CAMERA_BACKEND` decide qué usa la
cámara "1" (la principal):
```python
CAMERA_BACKEND = "auto"       # usa Picamera2 si está disponible, si no cae a USB
CAMERA_BACKEND = "picamera2"  # fuerza el módulo CSI
CAMERA_BACKEND = "usb"        # fuerza una webcam USB
CAMERA_BACKEND = "ip"         # fuerza otra cámara WiFi como "principal"
```

## 9. Dónde mover/redimensionar las cámaras en la página web

Archivo: `webapp/static/style.css`, sección `.grid` y `.feed-panel`
(están comentadas dentro del archivo con instrucciones exactas):

- **Ancho relativo de las columnas** → `.grid { grid-template-columns: 2fr 1fr; }`
  (la primera columna, con las cámaras, ocupa 2 partes; el log, 1 parte)
- **Tamaño del video dentro de su panel** → `.feed-panel img { width: 100%; }`
- **Cámaras una debajo de otra en vez de lado a lado** → cambia
  `grid-template-columns` a `1fr` (ya pasa automático en pantallas
  angostas gracias al `@media` al final del archivo)

El HTML (`webapp/templates/dashboard.html`) solo decide QUÉ se
muestra (2 `<section>`, una por cámara); el CSS decide DÓNDE y de
qué TAMAÑO se ve cada una.

## 10. Notas importantes

- `cv2.face.LBPHFaceRecognizer_create()` requiere el módulo `contrib`
  de OpenCV. El paquete de Raspberry Pi OS lo incluye; en pip usa
  `opencv-contrib-python` (no `opencv-python`) si pruebas en laptop.
- Cambia las contraseñas de ejemplo (`admin`/`admin`, `viewer`/`viewer`
  en `webapp/app.py`) antes de mostrar esto como algo "en producción".
- Si agregas a alguien nuevo con `capture_dataset.py`, siempre vuelve
  a correr `train_model.py` después, o el modelo no lo va a reconocer.
