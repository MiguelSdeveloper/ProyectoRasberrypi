# FaceSec — Proyecto completo (2 cámaras, CCTV 24/7)

Sistema de reconocimiento facial + vigilancia para Raspberry Pi. Este
README refleja el estado FINAL del proyecto.

## 1. Archivos — cuáles sirven, cuáles se eliminan

| Archivo | Estado | Por qué |
|---|---|---|
| `config.py` | ✅ Activo | Configuración central |
| `database.py` | ✅ Activo | Personas, usuarios, eventos (SQLite) |
| `camera.py` | ✅ Activo | Abstrae UNA cámara física (usb / picamera2 / wifi) |
| `camera_worker.py` | ✅ Activo | Cámara grabando 24/7, con reconexión automática |
| `recognition_engine.py` | ✅ Activo | Detección + reconocimiento (cámara 1) |
| `motion.py` | ✅ **Nuevo** | Detección de movimiento (cámara 2, WiFi) |
| `recorder.py` | ✅ Activo | 3 grabadores (persona/general/alerta) |
| `train_model.py` | ✅ Activo | Entrena LBPH (botón web) |
| `menu.py` | ✅ Activo | Punto de entrada único en la Pi |
| `webapp/app.py` + `templates/` + `static/` | ✅ Activo | Panel web completo |
| `requirements.txt` | ✅ Activo | Dependencias pip |
| ~~`recognize_live.py`~~ | ❌ **Elimínalo** | Ya no aporta nada que el panel web no haga mejor, y puede chocar con la cámara si lo corres junto al panel |
| ~~`capture_dataset.py`~~ | ❌ **Elimínalo** | Reemplazado por registro web (`/register`) |
| ~~`db_tool.py`~~ | ❌ Ya eliminado (decisión tuya) | Reemplazado por DB Browser for SQLite |
| `data/labels.json` | 🗑️ Bórralo si existe | Ya no se usa |

**Comando para terminar la limpieza:**
```bash
rm -f capture_dataset.py recognize_live.py data/labels.json
```

## 2. Arquitectura — 2 cámaras, cada una con un rol distinto

CÁMARA 1 (principal, USB/Pi) CÁMARA 2 (WiFi)
│ │
recognition_engine.py motion.py
(detecta + RECONOCE caras) (solo detecta movimiento,
│ no identidad -- más liviano)
└──────────────┬─────────────────────┘
│
camera_worker.py
(graba 24/7 en segundo plano,
reconecta solo si se cae la señal)
│
recorder.py
PersonRecorder · ContinuousRecorder · AlertRecorder


Cada `CameraWorker` corre en su propio hilo, sin importar si alguien
está viendo el panel. Si una cámara no está disponible (apagada, mal
configurada, sin red), el worker reintenta conectar cada 5 segundos
solo, y la web muestra **"SIN SEÑAL"** en vez de romperse.

## 3. Instalación

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-picamera2 python3-opencv libopenblas-dev ffmpeg libcap-dev sqlitebrowser

python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install flask werkzeug imutils
```
Ninguna dependencia nueva para esta ronda de cambios -- `motion.py`
usa solo OpenCV, que ya tenías instalado.

## 4. Configurar la cámara 2 (WiFi)

```python
CAMERA_WIFI_ENABLED = True
CAMERA_WIFI_URL = "http://192.168.0.50:81/stream"   # la URL de tu cámara
```
Si `CAMERA_WIFI_URL` queda vacío, o la cámara no responde, el panel
simplemente muestra "CÁMARA 2" con **SIN SEÑAL** -- no rompe nada del
resto del sistema.

## 5. Uso

```bash
python menu.py
```
Login inicial generado al azar la primera vez (se imprime en la
terminal, una sola vez). Desde el panel: **"registrar persona"**,
**"personas"**, **"usuarios"**.

## 6. Reconocimiento facial — aclaración sobre blanco y negro

Las fotos de entrenamiento se guardan en escala de grises **a
propósito** — el modelo LBPH compara patrones de textura, no color,
así que el color no aporta nada y solo haría todo más lento. **Esto
no afecta la detección de ninguna forma.** Como referencia visual
extra (no se usa para reconocer), ahora también se guarda una foto a
color de la primera muestra de cada persona en `data/previews/`.

## 7. Grabación — 3 sistemas por cámara

| Carpeta | Qué graba |
|---|---|
| `data/recordings/general/<cámara>/` | Todo, siempre, en bloques de 10 min |
| `data/recordings/people/<cámara>/` | Solo personas conocidas (cámara 1) |
| `data/recordings/alerts/<cámara>/` | Desconocidos (cámara 1) o movimiento (cámara 2) |

Los clips de alerta usan nombre con fecha y rango real de horas, y
NO se fragmentan: si la persona/movimiento reaparece dentro de 60
segundos (`ALERT_RESUME_WINDOW_SECONDS`), sigue en el mismo archivo.

## 8. Base de datos

3 tablas en `data/facesec.db` (`people` con datos personales
opcionales, `recognition_events`, `users`). Adminístrala con:
```bash
sqlitebrowser data/facesec.db
```

## 9. Dependencias instaladas (acumulado del proyecto completo)

**apt:** `python3-picamera2 python3-opencv libopenblas-dev ffmpeg libcap-dev sqlitebrowser`

**pip (venv):** `flask werkzeug imutils`

Sin dlib, sin TensorFlow/PyTorch -- decisión deliberada por las
limitaciones de la Pi 3B+.

## 10. Dónde mover/redimensionar las cámaras en la web

`webapp/static/style.css`, sección `.grid` y `.feed-panel`.