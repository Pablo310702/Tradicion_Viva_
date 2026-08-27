"""Asistente local para configurar SMS (Twilio) y WhatsApp (Meta).

Ejecuta:
    python configurar_mensajeria.py

El script actualiza únicamente variables de mensajería en .env y crea una
copia .env.bak antes de guardar. Las claves sensibles no se imprimen.
"""

from __future__ import annotations

from getpass import getpass
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def prompt(label: str, current: str = "", *, secret: bool = False) -> str:
    suffix = " [configurado, Enter para conservar]" if current else ""
    value = getpass(f"{label}{suffix}: ") if secret else input(f"{label}{suffix}: ")
    value = value.strip()
    return value if value else current


def update_env(path: Path, updates: dict[str, str]) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    remaining = dict(updates)
    output: list[str] = []
    for raw in lines:
        if "=" in raw and not raw.lstrip().startswith("#"):
            key = raw.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(raw)

    if remaining:
        output.extend(["", "# Comunicaciones automáticas - generado por configurar_mensajeria.py"])
        for key, value in remaining.items():
            output.append(f"{key}={value}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def yes_no(question: str, default: bool = True) -> bool:
    marker = "S/n" if default else "s/N"
    raw = input(f"{question} [{marker}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"s", "si", "sí", "y", "yes"}


def main() -> None:
    current = read_env(ENV_PATH)
    updates = {
        "DEFAULT_PHONE_COUNTRY_CODE": prompt(
            "Código de país por defecto", current.get("DEFAULT_PHONE_COUNTRY_CODE", "+502")
        ),
        "MESSAGING_HTTP_TIMEOUT": current.get("MESSAGING_HTTP_TIMEOUT", "15"),
        "PUBLIC_BASE_URL": prompt(
            "URL pública HTTPS del sistema (puede quedar vacía en local)",
            current.get("PUBLIC_BASE_URL", ""),
        ),
    }

    print("\n--- SMS con Twilio ---")
    if yes_no("¿Deseas configurar SMS con Twilio?", default=True):
        updates.update(
            {
                "TWILIO_ACCOUNT_SID": prompt("Twilio Account SID", current.get("TWILIO_ACCOUNT_SID", "")),
                "TWILIO_AUTH_TOKEN": prompt(
                    "Twilio Auth Token", current.get("TWILIO_AUTH_TOKEN", ""), secret=True
                ),
                "TWILIO_FROM_NUMBER": prompt(
                    "Número remitente Twilio en E.164 (ej. +15005550006)",
                    current.get("TWILIO_FROM_NUMBER", ""),
                ),
                "TWILIO_MESSAGING_SERVICE_SID": prompt(
                    "Messaging Service SID (opcional; si lo usas puede sustituir al número remitente)",
                    current.get("TWILIO_MESSAGING_SERVICE_SID", ""),
                ),
                "TWILIO_VALIDATE_WEBHOOKS": current.get("TWILIO_VALIDATE_WEBHOOKS", "True"),
            }
        )

    print("\n--- WhatsApp Business Cloud API de Meta ---")
    if yes_no("¿Deseas configurar WhatsApp?", default=True):
        updates.update(
            {
                "WHATSAPP_GRAPH_API_VERSION": prompt(
                    "Versión de Graph API", current.get("WHATSAPP_GRAPH_API_VERSION", "v25.0")
                ),
                "WHATSAPP_ACCESS_TOKEN": prompt(
                    "Access Token de WhatsApp", current.get("WHATSAPP_ACCESS_TOKEN", ""), secret=True
                ),
                "WHATSAPP_PHONE_NUMBER_ID": prompt(
                    "Phone Number ID de WhatsApp", current.get("WHATSAPP_PHONE_NUMBER_ID", "")
                ),
                "WHATSAPP_DEFAULT_TEMPLATE_NAME": prompt(
                    "Plantilla predeterminada",
                    current.get("WHATSAPP_DEFAULT_TEMPLATE_NAME", "tradicion_viva_comunicado"),
                ),
                "WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE": prompt(
                    "Idioma de plantilla", current.get("WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE", "es")
                ),
                "WHATSAPP_VERIFY_TOKEN": prompt(
                    "Token de verificación para webhook (elige uno privado)",
                    current.get("WHATSAPP_VERIFY_TOKEN", ""),
                    secret=True,
                ),
                "WHATSAPP_APP_SECRET": prompt(
                    "App Secret de Meta", current.get("WHATSAPP_APP_SECRET", ""), secret=True
                ),
            }
        )

    update_env(ENV_PATH, updates)
    print("\nConfiguración guardada en .env.")
    print("Se creó/actualizó la copia de seguridad .env.bak cuando ya existía .env.")
    print("Siguiente paso: python manage.py migrate")


if __name__ == "__main__":
    main()
