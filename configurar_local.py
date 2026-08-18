"""Genera una configuración .env segura para desarrollo local."""

from pathlib import Path
import secrets

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    print(f"Ya existe {env_path.name}; no se modificó.")
else:
    secret = secrets.token_urlsafe(64)
    env_path.write_text(
        "\n".join(
            [
                f"SECRET_KEY={secret}",
                "DEBUG=True",
                "ALLOWED_HOSTS=127.0.0.1,localhost",
                "CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000",
                "TRACCAR_BASE_URL=https://demo.traccar.org",
                "TRACCAR_USERNAME=",
                "TRACCAR_PASSWORD=",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("Se creó .env con una SECRET_KEY aleatoria y configuración local segura.")

print("Siguiente paso: python manage.py migrate")
print("Para usar GPS, completa TRACCAR_USERNAME y TRACCAR_PASSWORD en .env con tu cuenta de Traccar.")
print("El identificador visible en Traccar Client se asigna a cada hermandad desde Django Admin.")
