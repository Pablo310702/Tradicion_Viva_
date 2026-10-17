import secrets
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from hermandades.models import CuentaDevoto, SesionApiDevoto


class AuthenticationError(Exception):
    pass


def _jwt_secret():
    return getattr(settings, "JWT_SECRET_KEY", "") or settings.SECRET_KEY


def _encode_token(account, token_type, lifetime, session_id, jti=None):
    now = timezone.now()
    return jwt.encode(
        {
            "sub": str(account.pk),
            "type": token_type,
            "sid": str(session_id),
            "iat": now,
            "exp": now + lifetime,
            "jti": jti or secrets.token_urlsafe(32),
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def issue_tokens(account):
    refresh_jti = secrets.token_urlsafe(32)
    session = SesionApiDevoto.objects.create(cuenta=account, refresh_jti=refresh_jti)
    return {
        "accessToken": _encode_token(account, "access", timedelta(minutes=15), session.pk),
        "refreshToken": _encode_token(
            account,
            "refresh",
            timedelta(days=30),
            session.pk,
            jti=refresh_jti,
        ),
    }


def _decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
        raise AuthenticationError("Token inválido o expirado.") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise AuthenticationError("Tipo de token no válido.")
    account = CuentaDevoto.objects.filter(pk=payload["sub"], activa=True).first()
    if not account:
        raise AuthenticationError("Cuenta no encontrada o inactiva.")
    session = SesionApiDevoto.objects.filter(
        pk=payload.get("sid"),
        cuenta=account,
        revocado_en__isnull=True,
    ).first()
    if not session:
        raise AuthenticationError("La sesión fue cerrada o ya no existe.")
    if expected_type == "refresh" and session.refresh_jti != payload.get("jti"):
        raise AuthenticationError("El refresh token ya fue utilizado.")
    return account, session, payload


def _json_body(request):
    try:
        import json

        payload = json.loads(request.body or "{}")
        return payload if isinstance(payload, dict) else None
    except (TypeError, ValueError):
        return None


def _account_data(account):
    registration = account.inscripciones.order_by("creado_en").first()
    return {
        "id": account.pk,
        "email": account.correo,
        "name": registration.nombre_completo if registration else account.correo,
    }


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    data = _json_body(request)
    email = str((data or {}).get("email", "")).strip().lower()
    password = str((data or {}).get("password", ""))
    account = CuentaDevoto.objects.filter(correo__iexact=email, activa=True).first()
    if not email or not password or not account or not account.check_password(password):
        return JsonResponse({"error": "Credenciales incorrectas."}, status=401)

    account.ultimo_acceso = timezone.now()
    account.save(update_fields=["ultimo_acceso"])
    return JsonResponse({"user": _account_data(account), "tokens": issue_tokens(account)})


@csrf_exempt
@require_http_methods(["POST"])
def api_refresh(request):
    data = _json_body(request) or {}
    token = data.get("refreshToken") or request.COOKIES.get("refresh_token")
    if not token:
        return JsonResponse({"error": "Falta el refresh token."}, status=401)
    try:
        account, session, payload = _decode_token(token, "refresh")
    except AuthenticationError as exc:
        return JsonResponse({"error": str(exc)}, status=401)

    next_refresh_jti = secrets.token_urlsafe(32)
    with transaction.atomic():
        rotated = SesionApiDevoto.objects.filter(
            pk=session.pk,
            revocado_en__isnull=True,
            refresh_jti=payload["jti"],
        ).update(refresh_jti=next_refresh_jti, actualizado_en=timezone.now())
    if rotated != 1:
        return JsonResponse({"error": "El refresh token ya fue utilizado."}, status=401)

    tokens = {
        "accessToken": _encode_token(account, "access", timedelta(minutes=15), session.pk),
        "refreshToken": _encode_token(
            account,
            "refresh",
            timedelta(days=30),
            session.pk,
            jti=next_refresh_jti,
        ),
    }
    return JsonResponse({"user": _account_data(account), "tokens": tokens})


@require_GET
def api_me(request):
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return JsonResponse({"error": "Falta el token Bearer."}, status=401)
    try:
        account, _, _ = _decode_token(token, "access")
    except AuthenticationError as exc:
        return JsonResponse({"error": str(exc)}, status=401)
    return JsonResponse({"user": _account_data(account)})


@csrf_exempt
@require_http_methods(["POST"])
def api_logout(request):
    data = _json_body(request) or {}
    authorization = request.headers.get("Authorization", "")
    scheme, _, bearer_token = authorization.partition(" ")
    token = (
        data.get("refreshToken")
        or data.get("accessToken")
        or request.COOKIES.get("refresh_token")
        or request.COOKIES.get("access_token")
        or (bearer_token if scheme.lower() == "bearer" else "")
    )
    if not token:
        return JsonResponse({"error": "Envía el access o refresh token para cerrar la sesión."}, status=401)
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        payload = {}
    session_id = payload.get("sid")
    if session_id and payload.get("sub"):
        SesionApiDevoto.objects.filter(
            pk=session_id,
            cuenta_id=payload["sub"],
            revocado_en__isnull=True,
        ).update(revocado_en=timezone.now(), actualizado_en=timezone.now())

    response = JsonResponse({"message": "Sesión cerrada correctamente."})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


