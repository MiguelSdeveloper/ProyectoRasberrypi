VIGIA — Sistema de Vigilancia Inteligente

Sistema de videovigilancia inteligente desarrollado sobre una Raspberry Pi 3B+, utilizando cámaras, reconocimiento facial, detección de movimiento, grabación continua y una interfaz web para administración y monitoreo.

El proyecto fue desarrollado para la asignatura de Sistemas Embebidos de la Facultad de Ingeniería de Sistemas Computacionales de la Universidad Tecnológica de Panamá.

---

🎯 Objetivo

VIGIA busca proporcionar un sistema de vigilancia capaz de:

- Monitorear cámaras en tiempo real.
- Detectar rostros.
- Identificar personas registradas mediante reconocimiento facial.
- Diferenciar personas conocidas de desconocidas.
- Registrar eventos de reconocimiento.
- Grabar continuamente el contenido de las cámaras.
- Generar grabaciones de alerta.
- Administrar personas y usuarios desde una interfaz web.
- Trabajar de forma independiente aunque una cámara presente problemas de conexión.

---

🧠 Reconocimiento facial

El reconocimiento facial utiliza:

- OpenCV
- Haar Cascade para detección facial.
- LBPH (Local Binary Patterns Histograms) para reconocimiento.
- Imágenes de entrenamiento almacenadas en escala de grises.
- Un umbral configurable para determinar si una coincidencia es suficientemente similar.

Las personas registradas pueden ser identificadas automáticamente por el sistema.

Cuando una persona no coincide con el modelo entrenado, el sistema la clasifica como desconocida.

---

📷 Cámaras

El sistema está preparado para trabajar con diferentes fuentes de vídeo.

Cámara principal

La cámara principal puede utilizar:

- Cámara USB.
- Cámara CSI de Raspberry Pi mediante Picamera2.

Esta cámara es utilizada para:

- Videovigilancia.
- Detección facial.
- Reconocimiento facial.
- Grabación.

Cámara WiFi

El proyecto también contempla una segunda cámara WiFi.

Esta cámara se utiliza principalmente para:

- Detección de movimiento.
- Generación de alertas.
- Grabación.

La cámara WiFi no necesita realizar reconocimiento facial, reduciendo la carga de procesamiento de la Raspberry Pi.

Si la cámara WiFi no está disponible, el resto del sistema puede continuar funcionando.

---

🖥️ Panel web

VIGIA cuenta con una interfaz web desarrollada con Flask.

Desde el panel se pueden realizar diferentes operaciones:

- Visualizar las cámaras.
- Ver el estado de las cámaras.
- Registrar personas.
- Consultar personas registradas.
- Administrar usuarios.
- Consultar información de personas detectadas.
- Visualizar eventos de reconocimiento.
- Cerrar sesión.

El sistema utiliza diferentes niveles de acceso.

Administrador

Puede acceder a las funciones administrativas y consultar la información completa de las personas registradas.

Usuario / Viewer

Dispone de acceso limitado a las funciones del sistema.

---

👤 Registro de personas

El registro web permite almacenar información de las personas, incluyendo campos personales y datos relacionados con su rol.

Durante el registro se generan las muestras utilizadas posteriormente para entrenar el modelo de reconocimiento facial.

Las imágenes utilizadas por LBPH se almacenan en escala de grises.

Además, el sistema puede conservar una imagen de referencia a color para visualización.

---

🎥 Sistema de grabación

VIGIA cuenta con diferentes tipos de grabación:

data/recordings/
├── general/
├── people/
└── alerts/

Grabación general

Registra continuamente las cámaras en bloques de tiempo.

Grabación de personas

Guarda grabaciones relacionadas con personas reconocidas.

Grabación de alertas

Puede almacenar:

- Personas desconocidas.
- Movimiento detectado por la cámara secundaria.

Las grabaciones de alerta utilizan información temporal para identificar el momento en que ocurrió el evento.

---

🗄️ Base de datos

El sistema utiliza SQLite como base de datos local.

Archivo principal:

data/facesec.db

La base de datos contiene información relacionada con:

- Personas.
- Usuarios.
- Eventos de reconocimiento.

Puede visualizarse utilizando:

sqlitebrowser data/facesec.db

---

📁 Estructura del proyecto

ProyectoRasberrypi/
│
├── data/
│   ├── facesec.db
│   ├── dataset/
│   ├── recordings/
│   └── previews/
│
├── webapp/
│   ├── app.py
│   ├── templates/
│   └── static/
│
├── camera.py
├── camera_worker.py
├── config.py
├── database.py
├── menu.py
├── motion.py
├── recognition_engine.py
├── recorder.py
├── train_model.py
├── requirements.txt
└── README.md

---

⚙️ Componentes principales

Archivo| Función
"config.py"| Configuración general del sistema
"database.py"| Administración de SQLite
"camera.py"| Abstracción de las cámaras
"camera_worker.py"| Ejecución y reconexión de cámaras
"recognition_engine.py"| Detección y reconocimiento facial
"motion.py"| Detección de movimiento
"recorder.py"| Sistema de grabación
"train_model.py"| Entrenamiento del modelo LBPH
"menu.py"| Punto de entrada principal
"webapp/app.py"| Servidor web Flask
"webapp/templates/"| Interfaz HTML
"webapp/static/"| CSS y recursos de la interfaz

---

🛠️ Tecnologías

Hardware

- Raspberry Pi 3B+
- Cámara CSI de Raspberry Pi
- Cámara USB
- Cámara WiFi
- Almacenamiento USB

Software

- Python
- Flask
- OpenCV
- Picamera2
- SQLite
- Werkzeug
- Imutils

Inteligencia artificial / visión

- Haar Cascade
- LBPH
- OpenCV

---

📦 Instalación

Actualizar el sistema:

sudo apt update
sudo apt full-upgrade -y

Instalar dependencias principales:

sudo apt install -y python3-picamera2 python3-opencv libopenblas-dev ffmpeg libcap-dev sqlitebrowser

Crear el entorno virtual:

python3 -m venv --system-site-packages venv

Activarlo:

source venv/bin/activate

Instalar dependencias Python:

pip install flask werkzeug imutils

---

▶️ Ejecución

El sistema puede iniciarse mediante:

python menu.py

El sistema inicia el entorno de vigilancia y proporciona acceso al panel web.

---

🔐 Seguridad y usuarios

VIGIA utiliza autenticación para controlar el acceso al panel.

El sistema diferencia entre usuarios con permisos administrativos y usuarios con permisos limitados.

La información personal de las personas registradas se encuentra restringida según el nivel de acceso.

---

🔄 Reconexión de cámaras

Cada cámara funciona mediante su propio "CameraWorker".

Si una cámara pierde conexión, el sistema intenta reconectarla automáticamente.

Una cámara desconectada no debería detener todo el sistema de vigilancia.

---

🧹 Archivos antiguos

Durante el desarrollo se reemplazaron herramientas independientes de captura y reconocimiento por el flujo integrado dentro del panel web.

Entre los archivos que ya no forman parte del flujo principal se encuentran:

recognize_live.py
capture_dataset.py

La administración y registro se realizan actualmente desde la aplicación web.

---

👨‍💻 Equipo

VIGIA — Sistema de Vigilancia Inteligente

- Miguel Sánchez — Coordinador
- Greyce Sandoval
- Joseph Franco
- Mario Barsallo
- Ana Patiño

---

🎓 Contexto académico

Proyecto desarrollado para:

Universidad Tecnológica de Panamá

Facultad de Ingeniería de Sistemas Computacionales

Asignatura: Sistemas Embebidos

---

📌 Estado del proyecto

VIGIA es un prototipo funcional de videovigilancia inteligente basado en Raspberry Pi.

Actualmente integra:

- Videovigilancia.
- Dos fuentes principales de cámara USB/CSI.
- Cámara WiFi para detección de movimiento.
- Reconocimiento facial.
- Registro de personas.
- Gestión de usuarios.
- Base de datos SQLite.
- Grabación continua.
- Grabaciones de personas.
- Grabaciones de alerta.
- Interfaz web.
- Sistema de autenticación.
- Reconexión automática de cámaras.

El proyecto continúa en desarrollo y optimización del reconocimiento facial entre diferentes cámaras y condiciones de iluminación.