"""Controles de abuso aplicados antes de ejecutar vistas costosas."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.crypto import salted_hmac


class AbuseRateLimitMiddleware:
    """Rate limiting sencillo y distribuible cuando se configura Redis.

    El proxy/CDN debe aplicar límites adicionales para tráfico volumétrico.
    """

    RULES = {
        ("POST", "/iniciar-sesion/devoto/"): (10, 300),
        ("POST", "/iniciar-sesion/administrativo/"): (10, 300),
        ("POST", "/devoto/recuperar-contrasena/"): (5, 900),
        ("POST", "/api/auth/login/"): (20, 60),
        ("POST", "/api/auth/refresh/"): (60, 60),
        ("POST", "/api/auth/logout/"): (60, 60),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rule = self.RULES.get((request.method, request.path_info))
        if not rule:
            return self.get_response(request)

        limit, window = rule
        client_ip = request.META.get("REMOTE_ADDR", "unknown")
        # Solo confiar en el encabezado de Cloudflare cuando el despliegue lo
        # habilita explícitamente. Así no se puede falsificar desde Internet
        # cuando la aplicación está expuesta directamente.
        if getattr(settings, "TRUST_CLOUDFLARE_IP_HEADER", False):
            client_ip = request.META.get("HTTP_CF_CONNECTING_IP", client_ip)
        key = f"abuse-rate:{request.method}:{request.path_info}:{client_ip}"
        try:
            if cache.add(key, 1, timeout=window):
                count = 1
            else:
                count = cache.incr(key)
        except Exception:
            # No se permite que una falla de Redis deje inutilizable el sitio.
            count = 0

        if count > limit:
            response = JsonResponse(
                {"error": "Demasiadas solicitudes. Intenta de nuevo más tarde."},
                status=429,
            )
            response["Retry-After"] = str(window)
            return response

        return self.get_response(request)


LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_SECONDS = 15 * 60


def _login_lock_key(scope, identifier, request):
    ip = request.META.get("REMOTE_ADDR", "unknown") if request else "unknown"
    value = f"{scope}:{identifier.strip().casefold()}:{ip}"
    return f"auth-lock:{salted_hmac('tradicion-viva', value).hexdigest()}"


def esta_bloqueado(scope, identifier, request):
    return bool(cache.get(_login_lock_key(scope, identifier, request)))


def registrar_fallo_login(scope, identifier, request):
    key = _login_lock_key(scope, identifier, request)
    try:
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=LOGIN_LOCK_SECONDS)
        return count >= LOGIN_FAILURE_LIMIT
    except Exception:
        return False


def limpiar_fallos_login(scope, identifier, request):
    try:
        cache.delete(_login_lock_key(scope, identifier, request))
    except Exception:
        pass
