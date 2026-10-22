from django.contrib import messages
from django.contrib.auth import logout
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone


class InactivityTimeoutMiddleware:
    """Cierra sesiones administrativas y de devoto tras un periodo sin actividad."""

    session_key = "tradicion_viva_last_activity"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_time = timezone.now().timestamp()
        last_activity = request.session.get(self.session_key)
        timeout = max(1, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 180)))

        is_admin_session = bool(request.user.is_authenticated and request.user.is_staff)
        is_devotee_session = bool(request.session.get("cuenta_devoto_id"))
        has_protected_session = is_admin_session or is_devotee_session

        if has_protected_session and last_activity is not None:
            try:
                elapsed = current_time - float(last_activity)
            except (TypeError, ValueError):
                elapsed = 0
            if elapsed >= timeout:
                if is_admin_session:
                    logout(request)
                    messages.info(request, "Tu sesión administrativa se cerró por 3 minutos de inactividad.")
                    return redirect("web:administrativo_login")
                request.session.flush()
                messages.info(request, "Tu sesión de devoto se cerró por 3 minutos de inactividad.")
                return redirect("web:devoto_login")

        if has_protected_session:
            request.session[self.session_key] = current_time

        return self.get_response(request)
