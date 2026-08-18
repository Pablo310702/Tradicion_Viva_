"""Configura de forma local las credenciales de Traccar en el archivo .env."""

from getpass import getpass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def leer_env():
    if not ENV_PATH.exists():
        return [], {}
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    values = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return lines, values


def actualizar_lineas(lines, changes):
    seen = set()
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in changes:
                output.append(f"{key}={changes[key]}")
                seen.add(key)
                continue
        output.append(line)
    if output and output[-1].strip():
        output.append("")
    for key, value in changes.items():
        if key not in seen:
            output.append(f"{key}={value}")
    return output


lines, current = leer_env()
if not ENV_PATH.exists():
    print("No existe .env. Ejecuta primero: python configurar_local.py")
    raise SystemExit(1)

print("Configuración de Traccar para TRADICIÓN VIVA")
print("La URL de la API NO es la URL :5055 de Traccar Client.")
print("Para el demo de tu captura usa: https://demo.traccar.org")

base_url = input(f"TRACCAR_BASE_URL [{current.get('TRACCAR_BASE_URL', 'https://demo.traccar.org')}]: ").strip()
if not base_url:
    base_url = current.get("TRACCAR_BASE_URL", "https://demo.traccar.org")

username = input(f"Correo de tu cuenta Traccar [{current.get('TRACCAR_USERNAME', '')}]: ").strip()
if not username:
    username = current.get("TRACCAR_USERNAME", "")

password = getpass("Contraseña de tu cuenta Traccar (Enter para conservar la actual): ")
if not password:
    password = current.get("TRACCAR_PASSWORD", "")

if not username or not password:
    print("Falta el correo o la contraseña. No se modificó .env.")
    raise SystemExit(1)

changes = {
    "TRACCAR_BASE_URL": base_url.rstrip("/"),
    "TRACCAR_USERNAME": username,
    "TRACCAR_PASSWORD": password,
}
ENV_PATH.write_text("\n".join(actualizar_lineas(lines, changes)) + "\n", encoding="utf-8")
print("Traccar quedó configurado en .env.")
print("Reinicia Django con: python manage.py runserver")
