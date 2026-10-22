"""Configuración de Django para TRADICIÓN VIVA.

Las credenciales y opciones de despliegue se leen desde variables de entorno.
Para desarrollo local ejecuta primero: ``python configurar_local.py``.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Carga un archivo .env local sin sobrescribir variables ya definidas."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]



SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Falta SECRET_KEY. Ejecuta 'python configurar_local.py' para desarrollo "
        "o configura la variable de entorno en producción."
    )

DEBUG = env_bool("DEBUG", default=False)
TESTING = "test" in sys.argv

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY).strip()

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "hermandades",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "web.security.AbuseRateLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "web.middleware.OrganizationContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "web.session_timeout.InactivityTimeoutMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "hermandades" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

database_url = os.environ.get("DATABASE_URL", "").strip()
postgres_database = os.environ.get("PGDATABASE", "").strip()

if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=env_bool("DATABASE_SSL_REQUIRE", default=not DEBUG),
        )
    }
elif postgres_database:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": postgres_database,
            "USER": os.environ.get("PGUSER", "").strip(),
            "PASSWORD": os.environ.get("PGPASSWORD", ""),
            "HOST": os.environ.get("PGHOST", "127.0.0.1").strip(),
            "PORT": os.environ.get("PGPORT", "5432").strip(),
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "sslmode": os.environ.get("PGSSLMODE", "prefer").strip(),
            },
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

LANGUAGE_CODE = "es-gt"
TIME_ZONE = "America/Guatemala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
media_storage_backend = os.environ.get("MEDIA_STORAGE_BACKEND", "filesystem").strip().lower()
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}
if media_storage_backend == "s3":
    media_bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
    if not media_bucket:
        raise ImproperlyConfigured("Falta AWS_STORAGE_BUCKET_NAME para usar almacenamiento S3.")
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": media_bucket,
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "").strip() or None,
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None,
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN", "").strip() or None,
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID", "").strip() or None,
            "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip() or None,
            "default_acl": None,
            "file_overwrite": False,
            "querystring_auth": env_bool("AWS_QUERYSTRING_AUTH", default=True),
            "querystring_expire": int(os.environ.get("AWS_QUERYSTRING_EXPIRE", "3600")),
        },
    }
elif media_storage_backend != "filesystem":
    raise ImproperlyConfigured("MEDIA_STORAGE_BACKEND debe ser 'filesystem' o 's3'.")
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_IMAGE_UPLOAD_MB = int(os.environ.get("MAX_IMAGE_UPLOAD_MB", "20"))
MAX_VIDEO_UPLOAD_MB = int(os.environ.get("MAX_VIDEO_UPLOAD_MB", "250"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
elif not DEBUG:
    raise ImproperlyConfigured(
        "Falta REDIS_URL en produccion. Configura Redis administrado antes de publicar."
    )
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "tradicion-viva-local",
        }
    }

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if render_hostname:
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

# Cabeceras y cookies seguras. En desarrollo local se mantienen compatibles con HTTP.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS", "180"))

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Configuración explícita de encabezados para reducir exposición en navegadores.
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"

# Correo electrónico. Por defecto se imprime en consola para desarrollo.
# Para envíos reales configura un servidor SMTP en el archivo .env.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "TRADICIÓN VIVA <no-reply@tradicionviva.local>")

# Comunicaciones SMS / WhatsApp.
# SMS se envía con Twilio Programmable Messaging y WhatsApp con la API oficial
# WhatsApp Business Cloud de Meta. Todas las credenciales se mantienen en .env.
DEFAULT_PHONE_COUNTRY_CODE = os.environ.get("DEFAULT_PHONE_COUNTRY_CODE", "+502")
MESSAGING_HTTP_TIMEOUT = int(os.environ.get("MESSAGING_HTTP_TIMEOUT", "15"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
TRUST_CLOUDFLARE_IP_HEADER = env_bool("TRUST_CLOUDFLARE_IP_HEADER", default=False)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_API_KEY_SID = os.environ.get("TWILIO_API_KEY_SID", "")
TWILIO_API_KEY_SECRET = os.environ.get("TWILIO_API_KEY_SECRET", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")
TWILIO_STATUS_CALLBACK_URL = os.environ.get("TWILIO_STATUS_CALLBACK_URL", "")
TWILIO_VALIDATE_WEBHOOKS = env_bool("TWILIO_VALIDATE_WEBHOOKS", default=True)

WHATSAPP_GRAPH_API_VERSION = os.environ.get("WHATSAPP_GRAPH_API_VERSION", "v25.0")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_DEFAULT_TEMPLATE_NAME = os.environ.get("WHATSAPP_DEFAULT_TEMPLATE_NAME", "tradicion_viva_comunicado")
WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE = os.environ.get("WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE", "es")
WHATSAPP_RECEIPT_TEMPLATE_NAME = os.environ.get("WHATSAPP_RECEIPT_TEMPLATE_NAME", "")
WHATSAPP_RECEIPT_TEMPLATE_LANGUAGE = os.environ.get("WHATSAPP_RECEIPT_TEMPLATE_LANGUAGE", "es")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")

# Traccar: no se incluyen usuarios, contraseñas ni identificadores reales en el código.
TRACCAR_BASE_URL = os.environ.get("TRACCAR_BASE_URL", "https://demo.traccar.org").rstrip("/")
TRACCAR_USERNAME = os.environ.get("TRACCAR_USERNAME", "")
TRACCAR_PASSWORD = os.environ.get("TRACCAR_PASSWORD", "")
GPS_API_RATE_LIMIT_PER_MINUTE = int(os.environ.get("GPS_API_RATE_LIMIT_PER_MINUTE", "60"))
GPS_MAX_POSITION_AGE_MINUTES = int(os.environ.get("GPS_MAX_POSITION_AGE_MINUTES", "5"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(BASE_DIR / "backups"))).resolve()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "web": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
}
