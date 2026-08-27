"""Webhooks de estado para proveedores de mensajería.

Estos endpoints no reciben mensajes de usuarios; únicamente actualizan en la
base de datos el estado de entrega de mensajes que TRADICIÓN VIVA ya envió.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from hermandades.messaging import update_provider_status


def _twilio_expected_url(request) -> str:
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if base:
        return f"{base}{request.get_full_path()}"
    return request.build_absolute_uri()


def _twilio_signature_valid(request) -> bool:
    if not getattr(settings, "TWILIO_VALIDATE_WEBHOOKS", True):
        return True

    auth_token = (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip()
    signature = request.headers.get("X-Twilio-Signature", "")
    if not auth_token or not signature:
        return False

    payload = _twilio_expected_url(request)
    # Twilio firma URL + parámetros POST ordenados. getlist cubre claves repetidas.
    for key in sorted(request.POST.keys()):
        for value in sorted(request.POST.getlist(key)):
            payload += f"{key}{value}"
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


@csrf_exempt
def twilio_status_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido."}, status=405)
    if not _twilio_signature_valid(request):
        return HttpResponseForbidden("Firma de Twilio no válida.")

    message_sid = request.POST.get("MessageSid", "")
    status = request.POST.get("MessageStatus", "")
    error = request.POST.get("ErrorMessage", "") or request.POST.get("ErrorCode", "")
    updated = update_provider_status("twilio", message_sid, status, error)
    return JsonResponse({"ok": True, "updated": updated})


def _meta_signature_valid(request) -> bool:
    app_secret = (getattr(settings, "WHATSAPP_APP_SECRET", "") or "").strip()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), request.body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _meta_error_text(status_obj: dict) -> str:
    errors = status_obj.get("errors") or []
    parts = []
    for item in errors[:3]:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        title = item.get("title") or item.get("message")
        details = (item.get("error_data") or {}).get("details") if isinstance(item.get("error_data"), dict) else ""
        text = " - ".join(str(x) for x in (code, title, details) if x)
        if text:
            parts.append(text)
    return "; ".join(parts)[:2000]


@csrf_exempt
def whatsapp_webhook(request):
    # Verificación inicial solicitada por Meta al configurar el webhook.
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        expected = (getattr(settings, "WHATSAPP_VERIFY_TOKEN", "") or "").strip()
        if mode == "subscribe" and expected and hmac.compare_digest(token or "", expected):
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponseForbidden("Token de verificación no válido.")

    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido."}, status=405)
    if not _meta_signature_valid(request):
        return HttpResponseForbidden("Firma de Meta no válida.")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "JSON no válido."}, status=400)

    updated_count = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            for status_obj in value.get("statuses", []) or []:
                message_id = str(status_obj.get("id", ""))
                status = str(status_obj.get("status", ""))
                error = _meta_error_text(status_obj)
                if update_provider_status("meta-whatsapp", message_id, status, error):
                    updated_count += 1

    return JsonResponse({"ok": True, "updated": updated_count})
