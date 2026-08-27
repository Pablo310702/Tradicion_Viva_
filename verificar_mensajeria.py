"""Verifica la configuración de mensajería sin enviar mensajes.

Uso:
    python verificar_mensajeria.py
    python verificar_mensajeria.py --network

Sin --network solo valida variables. Con --network consulta Twilio y Meta para
comprobar credenciales, pero NO crea mensajes ni realiza envíos.
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import requests  # noqa: E402
from django.conf import settings  # noqa: E402


def present(value) -> bool:
    return bool(str(value or "").strip())


def mark(ok: bool) -> str:
    return "OK" if ok else "FALTA"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", action="store_true", help="Comprueba las credenciales contra las APIs sin enviar mensajes.")
    args = parser.parse_args()

    print("TRADICIÓN VIVA - Verificación de mensajería\n")
    twilio_sender = present(settings.TWILIO_FROM_NUMBER) or present(settings.TWILIO_MESSAGING_SERVICE_SID)
    twilio_auth = present(settings.TWILIO_AUTH_TOKEN) or (
        present(settings.TWILIO_API_KEY_SID) and present(settings.TWILIO_API_KEY_SECRET)
    )
    twilio_ok = present(settings.TWILIO_ACCOUNT_SID) and twilio_auth and twilio_sender
    whatsapp_ok = present(settings.WHATSAPP_ACCESS_TOKEN) and present(settings.WHATSAPP_PHONE_NUMBER_ID)

    print(f"SMS / Twilio: {mark(twilio_ok)}")
    print(f"  Account SID: {mark(present(settings.TWILIO_ACCOUNT_SID))}")
    print(f"  Autenticación: {mark(twilio_auth)}")
    print(f"  Remitente o Messaging Service: {mark(twilio_sender)}")
    print(f"WhatsApp / Meta: {mark(whatsapp_ok)}")
    print(f"  Access Token: {mark(present(settings.WHATSAPP_ACCESS_TOKEN))}")
    print(f"  Phone Number ID: {mark(present(settings.WHATSAPP_PHONE_NUMBER_ID))}")
    print(f"  Plantilla predeterminada: {mark(present(settings.WHATSAPP_DEFAULT_TEMPLATE_NAME))}")
    print(f"URL pública para webhooks: {mark(present(settings.PUBLIC_BASE_URL))}")

    if not args.network:
        print("\nNo se hicieron conexiones externas. Usa --network para validar credenciales sin enviar mensajes.")
        return 0 if (twilio_ok or whatsapp_ok) else 1

    print("\nComprobación de red (sin envíos):")
    timeout = settings.MESSAGING_HTTP_TIMEOUT

    if twilio_ok:
        username = settings.TWILIO_API_KEY_SID or settings.TWILIO_ACCOUNT_SID
        password = settings.TWILIO_API_KEY_SECRET or settings.TWILIO_AUTH_TOKEN
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}.json"
        try:
            r = requests.get(url, auth=(username, password), timeout=timeout)
            print(f"  Twilio: {'OK' if r.ok else 'ERROR HTTP ' + str(r.status_code)}")
        except requests.RequestException as exc:
            print(f"  Twilio: ERROR DE RED ({exc})")

    if whatsapp_ok:
        version = settings.WHATSAPP_GRAPH_API_VERSION
        url = f"https://graph.facebook.com/{version}/{settings.WHATSAPP_PHONE_NUMBER_ID}"
        try:
            r = requests.get(
                url,
                params={"fields": "display_phone_number,verified_name"},
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
                timeout=timeout,
            )
            print(f"  Meta WhatsApp: {'OK' if r.ok else 'ERROR HTTP ' + str(r.status_code)}")
        except requests.RequestException as exc:
            print(f"  Meta WhatsApp: ERROR DE RED ({exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
