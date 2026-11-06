from hermandades.models import CuentaDevoto


def sesion_actual(request):
    """Expone el nombre de la sesión activa para la barra superior."""
    if request.user.is_authenticated:
        nombre = request.user.get_full_name().strip() or request.user.get_username()
        return {"nombre_sesion": nombre, "tipo_sesion": "administrativo"}

    cuenta_id = request.session.get("cuenta_devoto_id")
    if not cuenta_id:
        return {"nombre_sesion": "", "tipo_sesion": ""}

    cuenta = (
        CuentaDevoto.objects.filter(pk=cuenta_id, activa=True)
        .prefetch_related("inscripciones")
        .first()
    )
    if not cuenta:
        return {"nombre_sesion": "", "tipo_sesion": ""}

    devoto = cuenta.inscripciones.order_by("creado_en").first()
    nombre = devoto.nombre_completo if devoto else cuenta.correo
    return {"nombre_sesion": nombre, "tipo_sesion": "devoto"}
