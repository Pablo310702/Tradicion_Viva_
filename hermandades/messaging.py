"""Servicios de comunicaciones para TRADICIÓN VIVA.

Canales soportados:
- Correo electrónico mediante el backend SMTP de Django.
- SMS mediante Twilio Programmable Messaging.
- WhatsApp mediante la API oficial WhatsApp Business Cloud de Meta.

Las credenciales nunca se almacenan en la base de datos ni en este módulo; se
leen desde variables de entorno definidas en ``config.settings``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

import requests
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Comunicado, Devoto, EnvioComunicado

logger = logging.getLogger(__name__)


class MessagingError(Exception):
    """Error base de mensajería."""


class MessagingConfigurationError(MessagingError):
    """Falta una credencial o parámetro requerido para un proveedor."""


class MessagingProviderError(MessagingError):
    """El proveedor rechazó o no pudo procesar el envío."""


@dataclass(slots=True)
class ProviderResult:
    provider: str
    message_id: str = ""
    status: str = "accepted"


def _known_placeholders(text: str, comunicado: Comunicado, devoto: Devoto) -> str:
    """Sustituye solo marcadores conocidos sin interpretar otras llaves del texto."""
    replacements = {
        "{nombre}": devoto.nombre_completo,
        "{primer_nombre}": devoto.primer_nombre,
        "{organizacion}": devoto.hermandad.nombre,
        "{tipo_organizacion}": devoto.hermandad.etiqueta_organizacion,
        "{asunto}": comunicado.asunto,
    }
    result = text or ""
    for marker, value in replacements.items():
        result = result.replace(marker, value or "")
    return result.strip()


def render_message(comunicado: Comunicado, devoto: Devoto) -> str:
    return _known_placeholders(comunicado.mensaje, comunicado, devoto)


def render_subject(comunicado: Comunicado, devoto: Devoto) -> str:
    return _known_placeholders(comunicado.asunto, comunicado, devoto)


def normalizar_telefono_e164(raw: str, default_country_code: str | None = None) -> str:
    """Normaliza un número a E.164.

    Para números locales de 8 dígitos usa +502 por defecto. Si el usuario ya
    ingresó un código de país se conserva.
    """
    default_country_code = default_country_code or settings.DEFAULT_PHONE_COUNTRY_CODE
    default_digits = "".join(ch for ch in default_country_code if ch.isdigit())

    value = (raw or "").strip()
    if not value:
        raise ValueError("El número de celular está vacío.")

    had_plus = value.startswith("+")
    digits = "".join(ch for ch in value if ch.isdigit())
    if value.startswith("00") and digits.startswith("00"):
        digits = digits[2:]
        had_plus = True

    # Guatemala: los números locales tienen 8 dígitos. Para otros países, el
    # prefijo puede venir explícitamente en el registro.
    if len(digits) == 8 and default_digits:
        digits = f"{default_digits}{digits}"
    elif not had_plus and default_digits and digits.startswith(default_digits):
        pass

    if not (8 <= len(digits) <= 15):
        raise ValueError("El número no puede convertirse a formato internacional E.164.")
    return f"+{digits}"


def _public_callback_url(route_name: str) -> str:
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{reverse(route_name)}"


def send_email(to: str, subject: str, body: str, connection=None) -> ProviderResult:
    if not to:
        raise MessagingProviderError("El destinatario no tiene correo electrónico.")
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
        connection=connection,
    )
    sent = message.send(fail_silently=False)
    if sent != 1:
        raise MessagingProviderError("El servidor SMTP no confirmó el envío del correo.")
    return ProviderResult(provider="smtp", status="sent")


def _twilio_auth() -> tuple[str, str]:
    account_sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
    if not account_sid:
        raise MessagingConfigurationError("Falta TWILIO_ACCOUNT_SID en el archivo .env.")

    api_key_sid = (settings.TWILIO_API_KEY_SID or "").strip()
    api_key_secret = (settings.TWILIO_API_KEY_SECRET or "").strip()
    auth_token = (settings.TWILIO_AUTH_TOKEN or "").strip()
    if api_key_sid and api_key_secret:
        return api_key_sid, api_key_secret
    if auth_token:
        return account_sid, auth_token
    raise MessagingConfigurationError(
        "Configura TWILIO_AUTH_TOKEN o TWILIO_API_KEY_SID/TWILIO_API_KEY_SECRET en el archivo .env."
    )


def _request_error(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text[:300]}"

    if not isinstance(data, dict):
        return f"HTTP {response.status_code}: {str(data)[:300]}"

    provider_error = data.get("error")
    if isinstance(provider_error, dict):
        provider_error = provider_error.get("message") or provider_error.get("error_user_msg")

    return str(
        data.get("message")
        or provider_error
        or data.get("detail")
        or f"HTTP {response.status_code}"
    )[:500]


def _post_with_retries(session: requests.Session, url: str, *, retries: int = 2, **kwargs) -> requests.Response:
    timeout = getattr(settings, "MESSAGING_HTTP_TIMEOUT", 15)
    last_response = None
    last_exception = None
    for attempt in range(retries + 1):
        try:
            response = session.post(url, timeout=timeout, **kwargs)
            last_response = response
            if response.status_code != 429 and response.status_code < 500:
                return response
        except requests.RequestException as exc:
            last_exception = exc
        if attempt < retries:
            time.sleep(1.0 * (attempt + 1))

    if last_response is not None:
        return last_response
    raise MessagingProviderError(f"No fue posible conectar con el proveedor: {last_exception}")


def send_sms_twilio(
    to: str,
    body: str,
    *,
    session: requests.Session | None = None,
) -> ProviderResult:
    account_sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
    username, password = _twilio_auth()
    from_number = (settings.TWILIO_FROM_NUMBER or "").strip()
    messaging_service_sid = (settings.TWILIO_MESSAGING_SERVICE_SID or "").strip()
    if not from_number and not messaging_service_sid:
        raise MessagingConfigurationError(
            "Configura TWILIO_FROM_NUMBER o TWILIO_MESSAGING_SERVICE_SID en el archivo .env."
        )

    data = {"To": to, "Body": body}
    if messaging_service_sid:
        data["MessagingServiceSid"] = messaging_service_sid
    else:
        data["From"] = from_number

    callback = (settings.TWILIO_STATUS_CALLBACK_URL or "").strip() or _public_callback_url(
        "web:twilio_status_webhook"
    )
    if callback:
        data["StatusCallback"] = callback

    own_session = session is None
    session = session or requests.Session()
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        response = _post_with_retries(session, url, data=data, auth=(username, password))
        if not response.ok:
            raise MessagingProviderError(_request_error(response))
        payload = response.json()
        return ProviderResult(
            provider="twilio",
            message_id=str(payload.get("sid", "")),
            status=str(payload.get("status", "queued")),
        )
    finally:
        if own_session:
            session.close()


def send_whatsapp_meta(
    to: str,
    body: str,
    *,
    first_name: str,
    mode: str,
    template_name: str = "",
    template_language: str = "es",
    template_param_mode: str = Comunicado.WHATSAPP_PARAM_NOMBRE_MENSAJE,
    session: requests.Session | None = None,
) -> ProviderResult:
    token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
    phone_number_id = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
    if not token:
        raise MessagingConfigurationError("Falta WHATSAPP_ACCESS_TOKEN en el archivo .env.")
    if not phone_number_id:
        raise MessagingConfigurationError("Falta WHATSAPP_PHONE_NUMBER_ID en el archivo .env.")

    digits = "".join(ch for ch in to if ch.isdigit())
    payload: dict = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": digits,
    }

    if mode == Comunicado.WHATSAPP_MODO_PLANTILLA:
        template = (template_name or settings.WHATSAPP_DEFAULT_TEMPLATE_NAME or "").strip()
        if not template:
            raise MessagingConfigurationError(
                "Falta el nombre de la plantilla de WhatsApp. Configúralo en el comunicado "
                "o en WHATSAPP_DEFAULT_TEMPLATE_NAME."
            )
        template_payload = {
            "name": template,
            "language": {"code": template_language or settings.WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE},
        }
        if template_param_mode == Comunicado.WHATSAPP_PARAM_NOMBRE_MENSAJE:
            parameters = [
                {"type": "text", "text": (first_name or "Devoto")[:80]},
                {"type": "text", "text": body[:4096]},
            ]
        elif template_param_mode == Comunicado.WHATSAPP_PARAM_MENSAJE:
            parameters = [{"type": "text", "text": body[:4096]}]
        else:
            parameters = []
        if parameters:
            template_payload["components"] = [{"type": "body", "parameters": parameters}]

        payload.update({"type": "template", "template": template_payload})
    else:
        payload.update(
            {
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            }
        )

    version = (settings.WHATSAPP_GRAPH_API_VERSION or "v25.0").strip()
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    own_session = session is None
    session = session or requests.Session()
    try:
        response = _post_with_retries(session, url, json=payload, headers=headers)
        if not response.ok:
            raise MessagingProviderError(_request_error(response))
        data = response.json()
        messages = data.get("messages") or []
        message_id = str(messages[0].get("id", "")) if messages else ""
        return ProviderResult(provider="meta-whatsapp", message_id=message_id, status="accepted")
    finally:
        if own_session:
            session.close()


def _unique_devotos(devotos: Iterable[Devoto], channel: str) -> list[tuple[Devoto, str]]:
    result: list[tuple[Devoto, str]] = []
    seen: set[str] = set()
    for devoto in devotos:
        if channel == EnvioComunicado.CANAL_EMAIL:
            target = (devoto.correo or "").strip().lower()
            key = target
        else:
            try:
                target = normalizar_telefono_e164(devoto.celular)
            except ValueError:
                target = (devoto.celular or "").strip()
            key = "".join(ch for ch in target if ch.isdigit())
        if target and key and key not in seen:
            seen.add(key)
            result.append((devoto, target))
    return result


def _create_log(
    comunicado: Comunicado,
    devoto: Devoto,
    channel: str,
    target: str,
    *,
    result: ProviderResult | None = None,
    error: Exception | str | None = None,
) -> None:
    if error:
        EnvioComunicado.objects.create(
            comunicado=comunicado,
            devoto=devoto,
            canal=channel,
            destinatario=target,
            proveedor=(result.provider if result else ""),
            estado=EnvioComunicado.ESTADO_FALLIDO,
            proveedor_message_id=(result.message_id if result else ""),
            proveedor_estado=(result.status if result else ""),
            detalle_error=str(error)[:2000],
        )
        return

    EnvioComunicado.objects.create(
        comunicado=comunicado,
        devoto=devoto,
        canal=channel,
        destinatario=target,
        proveedor=result.provider if result else "",
        estado=EnvioComunicado.ESTADO_ACEPTADO,
        proveedor_message_id=result.message_id if result else "",
        proveedor_estado=result.status if result else "accepted",
    )


def _base_devotos(comunicado: Comunicado):
    qs = Devoto.objects.select_related("hermandad").filter(acepta_privacidad=True)
    if comunicado.hermandad_id:
        qs = qs.filter(hermandad_id=comunicado.hermandad_id)
    return qs


def enviar_comunicado(comunicado: Comunicado, canales: Iterable[str] | None = None) -> dict[str, dict[str, int]]:
    """Envía un comunicado a todos los devotos que autorizaron cada canal.

    La función registra un ``EnvioComunicado`` por destinatario y devuelve
    contadores por canal. Un envío se considera exitoso cuando el proveedor lo
    acepta; los webhooks pueden actualizarlo luego a entregado o fallido.
    """
    selected = set(canales or [])
    if not selected:
        if comunicado.enviar_email:
            selected.add(EnvioComunicado.CANAL_EMAIL)
        if comunicado.enviar_sms:
            selected.add(EnvioComunicado.CANAL_SMS)
        if comunicado.enviar_whatsapp:
            selected.add(EnvioComunicado.CANAL_WHATSAPP)

    if not selected:
        raise MessagingConfigurationError("Selecciona al menos un canal de envío en el comunicado.")

    stats = {
        EnvioComunicado.CANAL_EMAIL: {"enviados": 0, "fallidos": 0},
        EnvioComunicado.CANAL_SMS: {"enviados": 0, "fallidos": 0},
        EnvioComunicado.CANAL_WHATSAPP: {"enviados": 0, "fallidos": 0},
    }
    base = _base_devotos(comunicado)

    # Email: una sola conexión SMTP para todo el lote.
    if EnvioComunicado.CANAL_EMAIL in selected:
        recipients = _unique_devotos(base.filter(acepta_email=True).exclude(correo=""), EnvioComunicado.CANAL_EMAIL)
        connection = None
        try:
            connection = get_connection(fail_silently=False)
            connection.open()
            for devoto, target in recipients:
                try:
                    result = send_email(target, render_subject(comunicado, devoto), render_message(comunicado, devoto), connection=connection)
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_EMAIL, target, result=result)
                    stats[EnvioComunicado.CANAL_EMAIL]["enviados"] += 1
                except Exception as exc:  # se registra cada destinatario y el lote continúa
                    logger.exception("Fallo de correo para comunicado %s", comunicado.pk)
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_EMAIL, target, error=exc)
                    stats[EnvioComunicado.CANAL_EMAIL]["fallidos"] += 1
        except Exception as exc:
            # Si no se pudo abrir SMTP, todos los destinatarios quedan marcados como fallidos.
            for devoto, target in recipients:
                _create_log(comunicado, devoto, EnvioComunicado.CANAL_EMAIL, target, error=exc)
            stats[EnvioComunicado.CANAL_EMAIL]["fallidos"] += len(recipients)
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    if EnvioComunicado.CANAL_SMS in selected:
        recipients = _unique_devotos(base.filter(acepta_sms=True).exclude(celular=""), EnvioComunicado.CANAL_SMS)
        with requests.Session() as session:
            for devoto, target in recipients:
                try:
                    normalized = normalizar_telefono_e164(target)
                    result = send_sms_twilio(normalized, render_message(comunicado, devoto), session=session)
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_SMS, normalized, result=result)
                    stats[EnvioComunicado.CANAL_SMS]["enviados"] += 1
                except Exception as exc:
                    logger.warning("Fallo SMS para comunicado %s: %s", comunicado.pk, exc)
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_SMS, target, error=exc)
                    stats[EnvioComunicado.CANAL_SMS]["fallidos"] += 1

    if EnvioComunicado.CANAL_WHATSAPP in selected:
        recipients = _unique_devotos(
            base.filter(acepta_whatsapp=True).exclude(celular=""),
            EnvioComunicado.CANAL_WHATSAPP,
        )
        with requests.Session() as session:
            for devoto, target in recipients:
                try:
                    normalized = normalizar_telefono_e164(target)
                    result = send_whatsapp_meta(
                        normalized,
                        render_message(comunicado, devoto),
                        first_name=devoto.primer_nombre,
                        mode=comunicado.whatsapp_modo,
                        template_name=comunicado.whatsapp_template_name,
                        template_language=comunicado.whatsapp_template_language,
                        template_param_mode=comunicado.whatsapp_template_param_mode,
                        session=session,
                    )
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_WHATSAPP, normalized, result=result)
                    stats[EnvioComunicado.CANAL_WHATSAPP]["enviados"] += 1
                except Exception as exc:
                    logger.warning("Fallo WhatsApp para comunicado %s: %s", comunicado.pk, exc)
                    _create_log(comunicado, devoto, EnvioComunicado.CANAL_WHATSAPP, target, error=exc)
                    stats[EnvioComunicado.CANAL_WHATSAPP]["fallidos"] += 1

    comunicado.total_email_enviados = stats[EnvioComunicado.CANAL_EMAIL]["enviados"]
    comunicado.total_email_fallidos = stats[EnvioComunicado.CANAL_EMAIL]["fallidos"]
    comunicado.total_sms_enviados = stats[EnvioComunicado.CANAL_SMS]["enviados"]
    comunicado.total_sms_fallidos = stats[EnvioComunicado.CANAL_SMS]["fallidos"]
    comunicado.total_whatsapp_enviados = stats[EnvioComunicado.CANAL_WHATSAPP]["enviados"]
    comunicado.total_whatsapp_fallidos = stats[EnvioComunicado.CANAL_WHATSAPP]["fallidos"]
    comunicado.total_enviados = sum(item["enviados"] for item in stats.values())
    comunicado.total_fallidos = sum(item["fallidos"] for item in stats.values())
    comunicado.enviado_en = timezone.now()
    comunicado.save(
        update_fields=[
            "total_email_enviados",
            "total_email_fallidos",
            "total_sms_enviados",
            "total_sms_fallidos",
            "total_whatsapp_enviados",
            "total_whatsapp_fallidos",
            "total_enviados",
            "total_fallidos",
            "enviado_en",
        ]
    )
    return stats


def update_provider_status(provider: str, message_id: str, provider_status: str, error: str = "") -> bool:
    """Actualiza el último log conocido para un ID de proveedor."""
    if not message_id:
        return False
    envio = EnvioComunicado.objects.filter(proveedor_message_id=message_id).order_by("-creado_en").first()
    if not envio:
        return False

    status = (provider_status or "").lower()
    if provider == "twilio":
        if status == "delivered":
            envio.estado = EnvioComunicado.ESTADO_ENTREGADO
        elif status in {"failed", "undelivered"}:
            envio.estado = EnvioComunicado.ESTADO_FALLIDO
    elif provider == "meta-whatsapp":
        if status in {"delivered", "read"}:
            envio.estado = EnvioComunicado.ESTADO_ENTREGADO
        elif status == "failed":
            envio.estado = EnvioComunicado.ESTADO_FALLIDO

    envio.proveedor_estado = provider_status[:80]
    if error:
        envio.detalle_error = error[:2000]
    envio.save(update_fields=["estado", "proveedor_estado", "detalle_error", "actualizado_en"])
    return True
