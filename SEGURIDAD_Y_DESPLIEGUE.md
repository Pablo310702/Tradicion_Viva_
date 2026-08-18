# Seguridad y despliegue

## Desarrollo local

```powershell
py configurar_local.py
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py test
py manage.py runserver
```

El script `configurar_local.py` crea `.env` con una `SECRET_KEY` aleatoria. El archivo `.env` está excluido por `.gitignore`.

## Variables mínimas de producción

```text
SECRET_KEY=<clave larga y aleatoria>
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com,https://www.tu-dominio.com
DATABASE_URL=postgresql://usuario:clave@servidor:5432/base
```

Configura también las variables `TRACCAR_*` cuando actives el seguimiento GPS. No guardes credenciales ni identificadores reales en el repositorio.

## Comandos de despliegue

```bash
python manage.py check --deploy
python manage.py collectstatic --no-input
python manage.py migrate --noinput
gunicorn config.wsgi:application
```

WhiteNoise sirve los archivos estáticos compilados. Los archivos subidos por administradores (`MEDIA_ROOT`) requieren almacenamiento persistente en producción; en plataformas con disco efímero debe usarse un disco persistente o almacenamiento de objetos.

## Datos personales

El registro almacena DPI, fecha de nacimiento y datos de contacto. Limita el acceso al panel de administración, utiliza HTTPS, crea copias de seguridad cifradas y define una política de conservación y eliminación de datos acorde con las reglas aplicables a la organización.

## HSTS

El proyecto activa HSTS durante una hora en producción. `SECURE_HSTS_INCLUDE_SUBDOMAINS` y `SECURE_HSTS_PRELOAD` permanecen desactivados por defecto para evitar bloquear subdominios que aún no tengan HTTPS. Actívalos únicamente después de verificar todo el dominio.
