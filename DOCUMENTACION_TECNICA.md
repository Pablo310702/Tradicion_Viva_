# TRADICIÓN VIVA — Documentación técnica del sistema

## 1. Descripción general

TRADICIÓN VIVA es una aplicación web de gestión procesional desarrollada con Django. El sistema organiza información de múltiples hermandades y cofradías y reutiliza la misma lógica para cada organización mediante el modelo `Hermandad` y su `slug` único.

Las funciones presentes en esta versión incluyen:

- Página pública por hermandad/cofradía.
- Misión, visión e información del templo.
- Agenda de actividades.
- Galería de fotografías.
- Galería fílmica mediante enlaces de YouTube/Vimeo.
- Marchas procesionales mediante archivos de audio o enlaces.
- Registro de devotos.
- Medición de hombro con cámara y resultado en centímetros/metros.
- Comprobante PDF de registro con código QR.
- Recorrido procesional y turnos georreferenciados.
- Seguimiento en mapa con Leaflet/OpenStreetMap.
- Consulta opcional de ubicación GPS mediante Traccar.
- Panel administrativo de Django.
- Editor visual de turnos restringido a usuarios `staff`.

## 2. Arquitectura

El proyecto utiliza la arquitectura MVT de Django:

- **Model (Modelo):** `hermandades/models.py`; representa las entidades y relaciones persistidas en la base de datos.
- **View (Vista/controlador):** `web/views.py`; recibe solicitudes HTTP, consulta modelos, valida permisos y prepara respuestas HTML, JSON o PDF.
- **Template (Plantilla):** `web/templates/web/`; contiene la interfaz HTML, CSS y JavaScript.
- **URL Dispatcher:** `config/urls.py` y `web/urls.py`; relaciona las URL con las funciones de vista.
- **Forms:** `web/forms.py`; validación y procesamiento del registro de devotos.
- **Admin:** `hermandades/admin.py`; gestión interna de hermandades, devotos, agenda, multimedia y turnos.

La estructura es multi-organización: los módulos funcionales se relacionan mediante una clave foránea hacia `Hermandad`. Por ello no se necesita crear un editor distinto para cada hermandad nueva.

## 3. Cambio: editor universal de turnos

El editor ahora utiliza como identificador principal el `slug` almacenado en la base de datos.

Ruta canónica:

```text
/hermandad/<slug>/editor-turnos/
```

Ejemplos:

```text
/hermandad/san-jose/editor-turnos/
/hermandad/rosario-merced/editor-turnos/
/hermandad/hermandad-nueva/editor-turnos/
```

Cuando se registra una nueva organización en `/admin/`, el enlace **Abrir editor** aparece automáticamente en la lista de hermandades. No es necesario modificar `views.py`, `urls.py` ni crear un template nuevo.

El editor también puede abrir una organización marcada como inactiva, siempre que el usuario sea `staff`; esto permite preparar sus turnos antes de publicar la organización.

Se mantienen URL antiguas y alias históricos únicamente por compatibilidad.

## 4. Lenguajes utilizados

### Backend

- **Python 3.13**: lenguaje principal del servidor.
- **Django 6.0.6**: framework web, ORM, autenticación, administración, formularios, rutas, plantillas y seguridad.

### Frontend

- **HTML5**: estructura de páginas y formularios.
- **CSS3**: diseño visual y comportamiento responsivo; gran parte del CSS está incluido dentro de las plantillas.
- **JavaScript (ES6)**: mapas, editor de turnos, consumo de API, cámara, canvas y menú responsivo.
- **Django Template Language (DTL)**: variables, ciclos, condicionales, `{% url %}`, `{% csrf_token %}` y renderizado dinámico.

### Consultas y persistencia

- **SQL**, gestionado principalmente mediante el ORM de Django.
- SQLite se utiliza de forma local y el proyecto está preparado para PostgreSQL mediante `DATABASE_URL`.

## 5. Frameworks, librerías y herramientas

| Tecnología | Función en el sistema |
|---|---|
| Django 6.0.6 | Backend, ORM, rutas, templates, autenticación, sesiones, admin y seguridad |
| SQLite | Base de datos local (`db.sqlite3`) |
| PostgreSQL / psycopg2-binary | Alternativa prevista para producción |
| dj-database-url | Configuración de base de datos mediante `DATABASE_URL` |
| Leaflet 1.9.4 | Mapas interactivos del editor y seguimiento |
| OpenStreetMap | Cartografía/base de tiles usada por Leaflet |
| Requests | Comunicación HTTP del servidor con Traccar |
| Traccar | Servicio externo opcional de ubicación GPS |
| ReportLab | Generación del comprobante PDF del devoto |
| ReportLab QR (`QrCodeWidget`) | Código QR dentro del comprobante |
| Pillow | Validación/procesamiento de imágenes y creación de miniaturas |
| WhiteNoise | Entrega de archivos estáticos en producción |
| Gunicorn | Servidor WSGI previsto para producción |
| Django Admin | Administración del contenido y usuarios |
| Git/.gitignore | Estructura preparada para control de versiones |
| Batch (`.bat`) | Inicio automatizado en Windows |
| Bash (`.sh`) | Script de construcción/despliegue |

## 6. Base de datos

La base principal de desarrollo es:

```text
db.sqlite3
```

El ORM de Django crea y mantiene las tablas mediante migraciones ubicadas en:

```text
hermandades/migrations/
```

### Entidades propias del sistema

#### `Hermandad`
Entidad central del sistema.

Campos principales:

- `nombre`
- `templo`
- `ciudad`
- `slug` único
- `descripcion_corta`
- `mision`
- `vision`
- `informacion_templo`
- `color_primario`
- `color_acento`
- `logo`
- `portada`
- `email_contacto`
- `facebook`
- `instagram`
- `activa`

#### `TurnoRecorrido`
Cada turno pertenece a una hermandad.

Campos:

- `hermandad_id` (FK)
- `numero`
- `nombre_turno`
- `pieza`
- `genero`
- `compositor`
- `direccion`
- `latitud`
- `longitud`
- `orden_ruta`
- `activa`

Restricción relevante: combinación única de hermandad, número y orden de ruta.

#### `EventoAgenda`
Actividades y fechas de cada organización.

Campos principales:

- `hermandad_id` (FK)
- `titulo`
- `descripcion`
- `lugar`
- `inicio`
- `fin`
- `todo_el_dia`
- `activo`

#### `Devoto`
Registro de personas asociadas a una organización.

Campos actuales del modelo:

- `hermandad_id` (FK)
- `dpi`
- `primer_nombre`
- `otros_nombres`
- `primer_apellido`
- `otros_apellidos`
- `fecha_nacimiento`
- `departamento`
- `municipio`
- `celular`
- `correo`
- `medida_hombro_cm`
- `comprobante_codigo` (UUID)
- `acepta_privacidad`
- `creado_en`
- `actualizado_en`

El DPI es único dentro de cada hermandad mediante una restricción compuesta `hermandad + dpi`.

#### `ImagenHermandad`
Imágenes institucionales y galería fotográfica. Genera miniaturas mediante Pillow.

#### `VideoHermandad`
Videos de YouTube/Vimeo. El modelo convierte las URL aceptadas a URL de inserción (`embed`).

#### `MarchaProcesional`
Marchas procesionales en archivo de audio o mediante un enlace externo.

### Relación principal

```text
Hermandad 1 ───── N TurnoRecorrido
          1 ───── N EventoAgenda
          1 ───── N Devoto
          1 ───── N ImagenHermandad
          1 ───── N VideoHermandad
          1 ───── N MarchaProcesional
```

Además existen las tablas estándar de Django para usuarios, grupos, permisos, sesiones, migraciones y bitácora del administrador.

## 7. Editor de turnos

Archivo de lógica:

```text
web/views.py
```

Plantilla:

```text
web/templates/web/editor_turnos.html
```

Modelo:

```text
hermandades.models.TurnoRecorrido
```

Tecnologías utilizadas:

- Django y ORM para guardar/editar/eliminar.
- `staff_member_required` para restringir el acceso.
- CSRF de Django para proteger formularios POST.
- Leaflet para seleccionar coordenadas.
- OpenStreetMap como mapa base.
- JavaScript para cargar turnos existentes en el mapa y editar el formulario.
- JSON embebido mediante `json_script` para transferir los turnos del backend al navegador con escape seguro.

Flujo:

```text
Usuario staff
   ↓
/hermandad/<slug>/editor-turnos/
   ↓
Django localiza Hermandad por slug
   ↓
Consulta TurnoRecorrido
   ↓
Template + Leaflet
   ↓
Usuario marca coordenadas / llena formulario
   ↓
POST + CSRF
   ↓
Validación
   ↓
SQLite/PostgreSQL
```

## 8. Registro de devotos y PDF

Formulario:

```text
web/forms.py -> DevotoForm
```

Modelo:

```text
hermandades.models.Devoto
```

Generación PDF:

```text
web/pdf_utils.py -> generar_comprobante_devoto()
```

Flujo:

```text
Devoto llena formulario
   ↓
DevotoForm valida DPI, correo, fecha, celular y medida
   ↓
Django guarda Devoto
   ↓
Se genera UUID de comprobante
   ↓
ReportLab crea PDF A4
   ↓
Se agrega logo/colores de la hermandad
   ↓
Se genera QR con la URL del comprobante
   ↓
Navegador recibe application/pdf
```

La medición del hombro se almacena como centímetros (`DecimalField`) y la interfaz puede mostrar, por ejemplo:

```text
1.48 m (148.0 cm)
```

## 9. Cámara y medición

La interfaz de registro utiliza APIs nativas del navegador:

- `navigator.mediaDevices.getUserMedia()` para obtener la cámara.
- `<video>` para mostrar la imagen.
- `<canvas>` para marcar los puntos de medición.
- JavaScript para calcular la escala a partir de una altura de referencia conocida.

El sistema no interpreta píxeles como centímetros directamente; utiliza una referencia introducida por el usuario para establecer la proporción física.

## 10. Mapas y recorrido

El editor y el seguimiento utilizan:

```text
Leaflet 1.9.4
OpenStreetMap
latitud / longitud
```

Los puntos se guardan en `TurnoRecorrido`. El orden se determina mediante `orden_ruta`.

El seguimiento GPS consulta opcionalmente Traccar mediante una API del backend. Las credenciales globales (`TRACCAR_BASE_URL`, `TRACCAR_USERNAME` y `TRACCAR_PASSWORD`) no están codificadas en el repositorio; se leen desde variables de entorno.

Cada `Hermandad` guarda su propia configuración dinámica mediante `gps_activo`, `traccar_device_id` y `nombre_dispositivo_gps`. El ID del dispositivo se asigna desde Django Admin, por lo que una hermandad o cofradía creada posteriormente puede habilitar seguimiento sin modificar `views.py`, `settings.py` ni las URLs.

**Importante:** tanto el editor de turnos como la asignación de GPS son universales para nuevas hermandades. El dispositivo puede ser Traccar Client, un Teltonika u otro equipo compatible con Traccar.

## 11. Formatos manejados

### Código/configuración

- `.py` — Python/Django
- `.html` — plantillas Django y HTML
- CSS embebido en templates
- JavaScript embebido en templates
- `.env` — variables de entorno
- `.txt` / `.md` — documentación
- `.bat` — automatización Windows
- `.sh` — automatización Linux/producción

### Base de datos/datos

- `.sqlite3` — base local
- SQL — persistencia relacional
- JSON — respuesta de la API GPS y datos enviados al JavaScript del mapa
- UUID — identificación del comprobante del devoto

### Multimedia

Imágenes permitidas:

- JPG/JPEG
- PNG
- WEBP

Audio permitido:

- MP3
- M4A
- OGG
- WAV

Documento generado:

- PDF A4

## 12. Seguridad implementada

- `SECRET_KEY` por variable de entorno.
- `DEBUG` configurable por entorno.
- `ALLOWED_HOSTS` configurable.
- Protección CSRF.
- Cookies de sesión `HttpOnly`.
- `SameSite=Lax`.
- `X_FRAME_OPTIONS = DENY`.
- `SECURE_CONTENT_TYPE_NOSNIFF`.
- Redirección HTTPS y HSTS en producción.
- Acceso al editor restringido con `staff_member_required`.
- Validación de extensiones y tamaños de imágenes/audio.
- DPI validado a 13 dígitos.
- Honeypot oculto (`website`) en el formulario de devotos.
- Credenciales globales de Traccar por variables de entorno y dispositivo GPS asignado dinámicamente por hermandad desde Django Admin.
- WhiteNoise con `CompressedManifestStaticFilesStorage` fuera de desarrollo/pruebas.

## 13. Estructura de carpetas

```text
TRADICION_VIVA_MODIFICADO/
│
├── manage.py
├── db.sqlite3
├── requirements.txt
├── iniciar_local.bat
├── build.sh
├── configurar_local.py
├── .env.example
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── hermandades/
│   ├── models.py
│   ├── admin.py
│   ├── validators.py
│   └── migrations/
│
├── web/
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── pdf_utils.py
│   ├── sitemaps.py
│   ├── tests.py
│   └── templates/web/
│       ├── base.html
│       ├── home.html
│       ├── hermandad_detalle.html
│       ├── seccion.html
│       ├── _agenda.html
│       ├── _hermandad_navigation.html
│       ├── editor_turnos.html
│       └── seguimiento.html
│
└── media/
    ├── logos/
    ├── portadas/
    ├── galeria/
    ├── miniaturas/
    └── marchas/
```

## 14. Rutas principales

| Ruta | Función |
|---|---|
| `/` | Inicio |
| `/admin/` | Administración Django |
| `/hermandad/<slug>/` | Página de la organización |
| `/hermandad/<slug>/<seccion>/` | Sección institucional |
| `/hermandad/<slug>/editor-turnos/` | Editor universal de turnos (staff) |
| `/<slug>/seguimiento/` | Seguimiento del recorrido |
| `/api/<slug>/ubicacion/` | API JSON de posición GPS |
| `/hermandad/<slug>/devoto/comprobante/<uuid>/` | PDF del devoto |
| `/sitemap.xml` | Sitemap SEO |
| `/robots.txt` | Reglas para rastreadores |

## 15. Dependencias declaradas

El archivo `requirements.txt` contiene:

```text
Django==6.0.6
dj-database-url==3.1.2
gunicorn==25.1.0
Pillow==11.2.1
psycopg2-binary==2.9.10
requests==2.32.5
whitenoise==6.12.0
reportlab==4.4.9
```

## 16. Inicio local

Opción automática en Windows:

```text
iniciar_local.bat
```

O manual:

```powershell
python -m pip install -r requirements.txt
python configurar_local.py
python manage.py migrate
python manage.py check
python manage.py runserver
```

La migración `0006_devoto_comprobante_medicion.py` debe aplicarse para que la base de datos coincida con el modelo actual de `Devoto` (sin género y con medida en centímetros + UUID de comprobante).

## 17. Despliegue

El proyecto incluye `build.sh` y configuración para:

- instalar dependencias;
- ejecutar `manage.py check --deploy`;
- recolectar archivos estáticos;
- aplicar migraciones;
- utilizar PostgreSQL cuando se define `DATABASE_URL`;
- utilizar Gunicorn como servidor WSGI.

La presencia de `RENDER_EXTERNAL_HOSTNAME` en la configuración indica que el proyecto está preparado para un entorno compatible con Render, aunque esta documentación no presupone que exista un despliegue activo.

## 18. Pruebas

`web/tests.py` contiene pruebas para:

- página principal;
- agenda;
- secciones;
- registro del devoto;
- generación PDF;
- ausencia de género en el formulario;
- medición en centímetros;
- seguridad del editor;
- editor universal para una organización nueva;
- editor para una organización todavía inactiva;
- enlace canónico del editor para usuarios staff;
- compatibilidad con URL histórica de la Hermandad de Soledad;
- sitemap y robots.txt.

